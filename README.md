# 澳门 701X 巴士实时看板

Python + Flask + 原生 HTML/CSS/JavaScript。无地图、无历史回放、无数据库。

## 启动（Python 3.10+）

```powershell
python -m pip install -r requirements.txt
python app.py
```

打开 http://127.0.0.1:5000 。按 Ctrl+C 停止。
需要联网访问 bis.dsat.gov.mo:37812；电脑时间需准确。

## 数据流程

官方巴士报站 → collector.py 请求 → app.py 校验与匹配 → /api/route → 网页。
静态接口为 /macauweb/getRouteData.html（action=sd），动态接口为 /macauweb/routestation/bus（action=dy）。
请求参数为 routeName=701X、dir=0、lang=zh-tw、device=web。
请求 token 按官方网页公开 JavaScript 的 MD5 与分钟时间格式生成，不涉及账户登录。
本项目使用标准库 urllib，保留 TLS 验证与 15 秒超时。

接口成功码为 000。站点按顺序和编号同时校验；循环线总站重复出现，不使用站名做唯一键。
页面每 30 秒请求一次，后端共享缓存限制源站请求频率；仅在有访问时采集。
失败时显示上一次结果并提示过期；首次失败显示空状态。只保存内存中的最新结果。
车辆展示在接口关联的站点，不等于精确位置，不计算到站分钟数，也不把没有车辆等同于停运。
时间为澳门 UTC+8 采集时间，不是上游 GPS 时间。当前接口属于网页内部接口，未来可能变化。

## 文件

- collector.py：HTTP 请求及官方网页 token 算法；直接运行可导出当前响应用于排查。
- app.py：服务、字段校验、缓存和异常处理。
- templates/index.html：网页结构。
- static/：样式和自动刷新逻辑。

## 20 分钟展示建议

背景 2 分钟；接口与采集 5 分钟；清洗和缓存 4 分钟；网页演示 5 分钟；限制与总结 4 分钟。
讲解重复总站的匹配、真实数据与缺失数据的区分，以及请求失败时的处理。

数据来源：https://bis.dsat.gov.mo:37812/macauweb/index.html
仅供课程学习，非官方服务。未发布到公网。
