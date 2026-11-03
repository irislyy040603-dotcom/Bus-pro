from flask import Flask, jsonify, render_template, request
from collector import fetch, request_data, fetch_page_title
from concurrent.futures import ThreadPoolExecutor
import math
import re
from datetime import datetime, timezone, timedelta
import threading
import time

app = Flask(__name__)
lock = threading.Lock()
states = {
    direction: dict(cache=None, last_attempt=None, error=None)
    for direction in ("0", "1")
}
geometries = {}
station_cache = {}
STATION_TTL = 600
source_lock = threading.Lock()
source_title = None
source_attempt = None


def coordinates(item):
    lat, lon = float(item["latitude"]), float(item["longitude"])
    if not (
        math.isfinite(lat)
        and math.isfinite(lon)
        and -90 <= lat <= 90
        and -180 <= lon <= 180
    ):
        raise ValueError("Invalid coordinates")
    return [lat, lon]


def normalize_speed(value):
    """空值、负数和非数值表示未知；0 是有效速度。"""
    try:
        speed = float(value)
    except (TypeError, ValueError):
        return None
    return speed if math.isfinite(speed) and speed >= 0 else None


def parse_route_points(text):
    """正则提取经纬度两组；数值转换与范围检查复用 coordinates。"""
    points = []
    for point in text.split(";"):
        if not point:
            continue
        match = re.fullmatch(r"([^,]+),([^,]+)", point)
        if match is None:
            raise ValueError("Invalid route coordinate pair")
        longitude, latitude = match.groups()
        points.append(coordinates(dict(latitude=latitude, longitude=longitude)))
    return points


def get_geometry(direction):
    """路线几何变化较少，缓存一小时；每段保留原有边界。"""
    geometry_cache, geometry_time = geometries.get(direction, (None, 0))
    if geometry_cache is None or time.monotonic() - geometry_time > 3600:
        result = request_data(
            "/ddbus/common/supermap/route/traffic",
            dict(
                lang="zh_tw",
                routeCode="00102",
                direction=direction,
                indexType="00",
                device="web",
                categoryIds="",
            ),
        )
        if result.get("header", {}).get("status") != "000":
            raise ValueError("Route unavailable")
        segments = []
        for segment in result["data"]:
            points = parse_route_points(segment["routeCoordinates"])
            if len(points) >= 2:
                segments.append(points)
        if not segments:
            raise ValueError("Empty route")
        geometries[direction] = segments, time.monotonic()
        geometry_cache = segments
    return geometry_cache


def get_stations(direction):
    """每个方向的站点资料缓存10分钟，不缓存失败结果。"""
    cached, fetched_at = station_cache.get(direction, (None, 0))
    if cached is None or time.monotonic() - fetched_at >= STATION_TTL:
        cached = fetch("getRouteData.html", "sd", direction)
        if cached.get("header") != "000" or not cached.get("data", {}).get("routeInfo"):
            raise ValueError("站点资料暂不可用")
        station_cache[direction] = cached, time.monotonic()
    return cached


def collect(direction="0"):
    # 站点使用缓存；日常仅采集车辆状态与定位两个接口。
    with ThreadPoolExecutor(max_workers=3) as pool:
        route_task = pool.submit(get_stations, direction)
        bus_task = pool.submit(fetch, "routestation/bus", "dy", direction)
        location_task = pool.submit(
            request_data,
            "/macauweb/routestation/location",
            dict(
                routeName="102",
                dir=direction,
                lang="zh-tw",
                routeCode="00102",
                device="web",
            ),
        )
        route, live, location = (
            route_task.result(),
            bus_task.result(),
            location_task.result(),
        )
    if location.get("header") != "000":
        raise ValueError("Location unavailable")
    segments = get_geometry(direction)
    # 临时改线造成站序不一致时，丢弃站点缓存，下次刷新重新获取。
    route_codes = [stop["staCode"] for stop in route["data"]["routeInfo"]]
    live_codes = [stop["staCode"] for stop in live.get("data", {}).get("routeInfo", [])]
    map_codes = [stop["stationCode"] for stop in location["data"].get("stationInfoList", [])]
    if route_codes != live_codes or route_codes != map_codes:
        station_cache.pop(direction, None)
        raise ValueError("站序发生变化，下一次刷新重新获取站点")
    data = merge_data(route, live, location, segments)
    data["direction"] = direction
    return data


def merge_data(route, live, location, segments):
    """按站序和站点编号合并；车牌用于跨接口匹配车辆编号。"""
    for result in (route, live):
        if result.get("header") != "000" or not isinstance(result.get("data"), dict):
            raise ValueError("官方数据源暂不可用")
    stops = route["data"].get("routeInfo", [])
    states = live["data"].get("routeInfo", [])
    if not stops or len(stops) != len(states):
        raise ValueError("站点数据不完整，等待下次更新")
    merged = []
    for index, (stop, state) in enumerate(zip(stops, states), 1):
        if stop["staCode"] != state["staCode"]:
            raise ValueError("站点顺序变化，暂时无法匹配实时信息")
        merged.append(
            dict(
                number=index,
                name=stop["staName"],
                code=stop["staCode"],
                lane=stop.get("laneName", ""),
                suspended=stop.get("suspendState") == "1",
                buses=[
                    dict(
                        plate=b.get("busPlate", ""),
                        code=b.get("busCode", ""),
                        status=b.get("status"),
                    )
                    for b in state.get("busInfo", [])
                ],
            )
        )
    positions = location["data"].get("stationInfoList", [])
    if len(positions) != len(merged):
        raise ValueError("Map stations mismatch")
    for stop, position in zip(merged, positions):
        if stop["code"] != position["stationCode"]:
            raise ValueError("Map station order mismatch")
        stop.update(position=coordinates(position), metro=position.get("metro") == "1")
    codes = {b["plate"]: b["code"] for s in merged for b in s["buses"]}
    vehicles = []
    for bus in location["data"].get("busInfoList", []):
        vehicles.append(
            dict(
                plate=bus["busPlate"],
                code=codes.get(bus["busPlate"], ""),
                position=coordinates(bus),
                speed=normalize_speed(bus.get("speed")),
            )
        )
    return dict(
        stops=merged,
        vehicles=vehicles,
        segments=segments,
        vehicle_count=len(vehicles),
        updated_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),
    )


@app.get("/api/source")
def source():
    """HTML 标题独立采集，失败不会影响实时巴士数据。"""
    global source_title, source_attempt
    with source_lock:
        if source_attempt is None or time.monotonic() - source_attempt >= 3600:
            source_attempt = time.monotonic()
            try:
                source_title = fetch_page_title()
            except Exception:
                app.logger.exception("官方 HTML 采集失败")
                source_title = None
        return jsonify(title=source_title), 200 if source_title else 503


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/route")
def route():
    direction = request.args.get("direction", "0")
    if direction not in states:
        return jsonify(error="无效方向"), 400
    with lock:
        state = states[direction]
        interval = 5 if request.args.get("refresh") == "1" else 10
        if (
            state["last_attempt"] is None
            or time.monotonic() - state["last_attempt"] >= interval
        ):
            state["last_attempt"] = time.monotonic()
            try:
                state["cache"] = collect(direction)
                state["error"] = None
            except Exception:
                app.logger.exception("102 collection failed")
                state["error"] = "暂时无法获取官方数据，请稍后刷新。"
        data = dict(
            state["cache"]
            or dict(
                stops=[], vehicles=[], segments=[], vehicle_count=0, updated_at=None
            )
        )
        data.update(
            direction=direction,
            stale=bool(state["error"]),
            error=state["error"],
            refresh_seconds=10,
        )
    response = jsonify(data)
    response.headers["Cache-Control"] = "no-store"
    return response, 200 if state["cache"] else 503


@app.get("/api/photo/<path:code>")
def photo(code):
    from urllib.request import urlopen
    from flask import Response

    if not re.fullmatch(r"[MTLC]\d+(?:/\d+)?", code):
        return "", 400
    name = code.lower().replace("/", "_") if "/" in code else code.lower() + "_1"
    try:
        with urlopen(
            "https://www.dsat.gov.mo/bres/bus_stop_img/" + name + ".jpg", timeout=12
        ) as upstream:
            if not upstream.headers.get("Content-Type", "").startswith("image/"):
                return "", 404
            return Response(
                upstream.read(),
                mimetype="image/jpeg",
                headers={"Cache-Control": "public, max-age=86400"},
            )
    except Exception:
        return "", 404


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, threaded=True)
