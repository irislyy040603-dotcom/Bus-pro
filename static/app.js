const REFRESH_INTERVAL = 10000;
const $ = (id) => document.getElementById(id);
let busy = false,
  direction = "0",
  currentData = null,
  selected = 0;
function element(tag, text, cls) {
  const node = document.createElement(tag);
  node.textContent = text;
  if (cls) node.className = cls;
  return node;
}
async function refresh(manual = false) {
  if (busy) return;
  busy = true;
  for (const id of ["refresh", "map-refresh", "switch-direction"])
    $(id).disabled = true;
  try {
    const response = await fetch(
      "/api/route?direction=" + direction + (manual ? "&refresh=1" : ""),
      { signal: AbortSignal.timeout(40000) },
    );
    const data = await response.json();
    if (!Array.isArray(data.stops)) throw Error("Invalid response");
    currentData = data;
    $("count").textContent = data.stops.length || "—";
    $("vehicles").textContent = data.updated_at ? data.vehicle_count : "—";
    $("updated").textContent = data.updated_at
      ? formatTime(data.updated_at)
      : "—";
    $("status").textContent = data.error
      ? data.error + (data.updated_at ? " 保留旧数据，已过期。" : "")
      : "● 官方数据 · 每10秒刷新";
    if (data.stops.length)
      $("direction-title").textContent =
        data.stops[0].name + " → " + data.stops.at(-1).name;
    selected = Math.min(selected, Math.max(0, data.stops.length - 1));
    $("station").replaceChildren();
    for (const [index, stop] of data.stops.entries()) {
      const option = element(
        "option",
        stop.code + " · " + stop.name + (stop.suspended ? "（暂不停靠）" : ""),
      );
      option.value = index;
      $("station").append(option);
    }
    $("station").value = selected;
    renderStops();
    updateMap(data);
  } catch (error) {
    $("status").textContent = "连接失败，已有数据可能过期。";
    if (currentData) {
      currentData.stale = true;
      renderStops();
    }
  } finally {
    busy = false;
    for (const id of ["refresh", "map-refresh", "switch-direction"])
      $(id).disabled = false;
  }
}
function renderStops() {
  const data = currentData;
  if (!data) return;
  const target = data.stops[selected];
  let candidates = [];
  data.stops.forEach((stop, index) => {
    if (index <= selected && !stop.suspended)
      for (const bus of stop.buses) {
        if (index === selected && bus.status !== "1") continue;
        candidates.push({
          distance: data.stops
            .slice(index + 1, selected + 1)
            .filter((s) => !s.suspended).length,
          plate: bus.plate,
        });
      }
  });
  candidates.sort((a, b) => a.distance - b.distance);
  $("arrival").textContent = data.stale
    ? "数据已过期，暂不估算候车站数"
    : target?.suspended
      ? "所选站点暂不停靠"
      : candidates.length
        ? candidates[0].distance === 0
          ? "车辆已关联到本站：" + candidates[0].plate
          : "下一辆车约还有 " +
            candidates[0].distance +
            " 站 · " +
            candidates[0].plate
        : "暂未检测到本方向驶向本站的车辆";
  // 记录真实车辆的旧位置，让下一次站点关联变化平滑过渡。
  const oldPositions = new Map(
    [...$("stops").querySelectorAll("[data-plate]")].map(node =>
      [node.dataset.plate, node.getBoundingClientRect().top])
  );
  const previousScroll = $("stops").scrollTop;
  $("stops").replaceChildren();
  for (const [index, stop] of data.stops.entries()) {
    const row = element(
      "li",
      "",
      "stop" + (index === selected ? " selected" : ""),
    );
    const rail = element("div", "", "rail");
    rail.append(element("div", "", "dot"), element("div", "", "track"));
    const body = element("div", "", "body"),
      info = element("div", "");
    const name = element(
      "button",
      stop.code + " · " + stop.name,
      "photo-button",
    );
    name.onclick = () => {
      selected = index;
      $("station").value = index;
      renderStops();
      showPhoto(stop);
    };
    info.append(
      name,
      element(
        "div",
        [stop.lane, stop.suspended ? "暂不停靠" : "", index === selected ? "我的候车站" : ""].filter(Boolean).join(" · "),
        "idx",
      ),
    );
    body.append(info);
    const cars = element("div", "", "rail-vehicles");
    for (const bus of stop.buses) {
      const vehicle = data.vehicles.find((v) => v.plate === bus.plate);
      const car = element("div", "", "rail-vehicle");
      car.dataset.plate = bus.plate;
      car.title = "官方关联站点：" + stop.code + "（非精确道路位置）";
      const label = element("div", "", "vehicle-label");
      label.append(element("strong", bus.code || bus.plate),
        element("span", vehicle?.speed != null ? vehicle.speed + " km/h" : "速度暂无数据"));
      car.append(label, element("span", "🚌", "rail-bus-icon"));
      cars.append(car);
    }
    row.style.minHeight = Math.max(108, stop.buses.length * 58 + 24) + "px";
    row.append(cars, rail, body);
    $("stops").append(row);
  }
  $("stops").scrollTop = previousScroll;
  if (!data.stale && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    for (const node of $("stops").querySelectorAll("[data-plate]")) {
      const previous = oldPositions.get(node.dataset.plate);
      if (previous !== undefined) {
        const distance = previous - node.getBoundingClientRect().top;
        if (Math.abs(distance) > 1) node.animate(
          [{transform: `translateY(${distance}px)`}, {transform: "translateY(0)"}],
          {duration: 650, easing: "ease-out"}
        );
      }
    }
  }
}
function showPhoto(stop) {
  $("photo-title").textContent = stop.code + " · " + stop.name;
  $("photo-status").textContent = "正在加载官方站点照片…";
  const image = $("station-photo");
  image.hidden = true;
  image.onload = () => {
    image.hidden = false;
    $("photo-status").textContent = "官方站点实景照片";
  };
  image.onerror = () => {
    $("photo-status").textContent = "官方暂未提供该站照片或图片加载失败。";
  };
  image.src = "/api/photo/" + encodeURIComponent(stop.code);
  const name = stop.code.toLowerCase().includes("/")
    ? stop.code.toLowerCase().replace("/", "_")
    : stop.code.toLowerCase() + "_1";
  if ($("photo-source")) $("photo-source").href =
    "https://www.dsat.gov.mo/bres/bus_stop_img/" + name + ".jpg";
  if (!$("photo-dialog").open) $("photo-dialog").showModal();
}
function toggleFull() {
  $("map-card").classList.toggle("full");
  $("full-map").textContent = $("map-card").classList.contains("full")
    ? "✕ 返回"
    : "⛶ 全图";
  setTimeout(() => map?.invalidateSize(), 0);
}
$("full-map").onclick = toggleFull;
$("close-photo").onclick = () => $("photo-dialog").close();
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && $("map-card").classList.contains("full"))
    toggleFull();
});
$("station").onchange = () => {
  selected = Number($("station").value);
  renderStops();
};
$("switch-direction").onclick = () => {
  direction = direction === "0" ? "1" : "0";
  selected = 0;
  currentData = null;
  fitted = false;
  staticMapSignature = "";
  routeLayer?.clearLayers();
  stopLayer?.clearLayers();
  for (const marker of vehicleMarkers.values()) map.removeLayer(marker);
  vehicleMarkers.clear();
  $("stops").replaceChildren();
  $("station").replaceChildren();
  $("arrival").textContent = "正在切换方向…";
  $("direction-title").textContent = "正在切换方向…";
  refresh();
};
let map,
  routeLayer,
  stopLayer,
  fitted = false;
let staticMapSignature = "";
function formatTime(value) {
  return new Date(value).toLocaleTimeString("zh-CN", {
    timeZone: "Asia/Macau",
    hour12: false,
  });
}
const vehicleMarkers = new Map();
function popup(title, lines) {
  const box = element("div", "", "map-popup");
  box.append(element("h3", title));
  for (const line of lines) box.append(element("p", line));
  return box;
}
function updateMap(data) {
  if (!window.L) {
    $("map-note").textContent = "地图库加载失败，请刷新网页。";
    return;
  }
  if (!map) {
    map = L.map("map").setView([22.143, 113.56], 14);
    map.on("click", () => {
      if (!$("map-card").classList.contains("full")) toggleFull();
    });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    })
      .on("tileerror", () => {
        $("map-note").textContent =
          "部分地图底图加载失败，请检查网络；路线和车辆数据仍可显示。";
      })
      .addTo(map);
    routeLayer = L.featureGroup().addTo(map);
    stopLayer = L.layerGroup().addTo(map);
    $("fit-route").onclick = () => {
      if (routeLayer.getLayers().length)
        map.fitBounds(routeLayer.getBounds(), { padding: [35, 35] });
    };
  }
  if (!data.segments) return;
  const signature = JSON.stringify([
    data.segments,
    data.stops.map(({ buses, ...station }) => station),
  ]);
  if (signature !== staticMapSignature) {
    staticMapSignature = signature;
    routeLayer.clearLayers();
    for (const segment of data.segments)
      L.polyline(segment, { color: "#128334", weight: 5 }).addTo(routeLayer);
    stopLayer.clearLayers();
    const grouped = new Map();
    for (const stop of data.stops) {
      const key = stop.code + stop.position.join(",");
      if (!grouped.has(key)) grouped.set(key, { ...stop, numbers: [] });
      grouped.get(key).numbers.push(stop.number);
    }
    for (const stop of grouped.values())
      L.circleMarker(stop.position, {
        radius: 7,
        color: "white",
        weight: 2,
        fillColor: "#188aca",
        fillOpacity: 1,
      })
        .addTo(stopLayer)
        .on("click", () => showPhoto(stop))
        .bindPopup(
          popup(
            stop.name,
            [
              stop.code,
              stop.lane || "",
              stop.metro ? "可换乘澳门轻轨" : "",
              stop.suspended ? "暂不停靠" : "",
            ].filter(Boolean),
          ),
        );
  }
  updateVehicles(data);
  if (!fitted && routeLayer.getLayers().length) {
    map.fitBounds(routeLayer.getBounds(), { padding: [35, 35] });
    fitted = true;
  }
}
function updateVehicles(data) {
  const seen = new Set();
  for (const bus of data.vehicles || []) {
    seen.add(bus.plate);
    let marker = vehicleMarkers.get(bus.plate);
    if (!marker) {
      marker = L.marker(bus.position, {
        icon: L.divIcon({
          className: "vehicle-icon",
          html: "▣",
          iconSize: [30, 30],
        }),
        zIndexOffset: 1000,
      }).addTo(map);
      vehicleMarkers.set(bus.plate, marker);
    } else marker.setLatLng(bus.position);
    const speed = bus.speed === null ? "速度暂无数据" : bus.speed + " km/h";
    const label = element("span", speed);
    if (marker.getTooltip()) marker.setTooltipContent(label);
    else
      marker.bindTooltip(label, {
        permanent: true,
        direction: "right",
        className: "speed-label",
      });
    const details = popup(bus.code || bus.plate, [
      "车牌：" + bus.plate,
      "时速：" + speed,
      "纬度：" + bus.position[0],
      "经度：" + bus.position[1],
      "车辆型号：暂无资料",
      "采集时间：" + formatTime(data.updated_at),
      data.stale ? "数据已过期" : "",
    ]);
    if (marker.getPopup()) marker.setPopupContent(details);
    else marker.bindPopup(details);
  }
  for (const [plate, marker] of vehicleMarkers)
    if (!seen.has(plate)) {
      map.removeLayer(marker);
      vehicleMarkers.delete(plate);
    }
}
$("refresh").addEventListener("click", () => refresh(true));
$("map-refresh").addEventListener("click", () => refresh(true));
refresh();
setInterval(() => {
  if (!document.hidden) refresh();
}, REFRESH_INTERVAL);

// HTML 正则提取结果使用 textContent 展示，不作为 HTML 插入页面。
async function loadSource() {
  try {
    const response = await fetch("/api/source", {
      signal: AbortSignal.timeout(45000),
    });
    if (!response.ok) throw new Error("HTML unavailable");
    const data = await response.json();
    $("source-title").textContent = "澳门交通事务局 · " + data.title;
    $("source-status").textContent = "来源名称提取自官方 HTML 页面标题";
  } catch {
    $("source-status").textContent =
      "HTML 标题暂未取得；上方来源名称为预设名称";
  }
}
loadSource();
