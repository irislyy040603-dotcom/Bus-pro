from flask import Flask, jsonify, render_template
from collector import fetch
from datetime import datetime, timezone, timedelta
import threading
import time

app = Flask(__name__)
lock = threading.Lock()
cache = None
last_attempt = 0
error = None

def collect():
    route = fetch('getRouteData.html', 'sd')
    live = fetch('routestation/bus', 'dy')
    for result in (route, live):
        if result.get('header') != '000' or not isinstance(result.get('data'), dict):
            raise ValueError('官方数据源暂不可用')
    stops = route['data'].get('routeInfo', [])
    states = live['data'].get('routeInfo', [])
    if not stops or len(stops) != len(states):
        raise ValueError('站点数据不完整，等待下次更新')
    merged = []
    for index, (stop, state) in enumerate(zip(stops, states), 1):
        if stop['staCode'] != state['staCode']:
            raise ValueError('站点顺序变化，暂时无法匹配实时信息')
        merged.append(dict(number=index, name=stop['staName'], code=stop['staCode'],
                           lane=stop.get('laneName', ''), suspended=stop.get('suspendState') == '1',
                           buses=[dict(plate=b.get('busPlate', ''), code=b.get('busCode', ''))
                                  for b in state.get('busInfo', [])]))
    vehicles = {b['plate'] or b['code'] for s in merged for b in s['buses']}
    return dict(stops=merged, vehicle_count=len(vehicles),
                updated_at=datetime.now(timezone(timedelta(hours=8))).isoformat())

@app.get('/')
def index():
    return render_template('index.html')

@app.get('/api/route')
def route():
    global cache, last_attempt, error
    with lock:
        if time.monotonic() - last_attempt >= 30:
            last_attempt = time.monotonic()
            try:
                cache = collect()
                error = None
            except Exception:
                app.logger.exception('701X collection failed')
                error = '暂时无法获取官方数据，请稍后刷新。'
        data = dict(cache or dict(stops=[], vehicle_count=0, updated_at=None))
        data.update(stale=bool(error), error=error, refresh_seconds=30)
    response = jsonify(data)
    response.headers['Cache-Control'] = 'no-store'
    return response, 200 if cache else 503

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, threaded=True)
