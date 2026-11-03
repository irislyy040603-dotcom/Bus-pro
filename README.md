# 澳门102巴士实时可视化

Python + Flask + 原生JavaScript + Leaflet。本地课程项目，包含双向路线、候车点、车辆定位与速度、官方站点照片和固定班次表。

## 启动

需要Python 3.10+及网络。

```powershell
python -m pip install -r requirements.txt
python app.py
```

打开 http://127.0.0.1:5000 。Ctrl+C停止；代码修改后重启服务，浏览器Ctrl+F5。

## 文档

- [完整项目说明](IMPLEMENTATION.md)：功能、技术、数据字段、三条正则、代码流程与限制。
- [四人分工和10分钟展示](PRESENTATION.md)：任务交付、时间分配、逐段讲稿、现场操作和问答。
- [官方班次原图](docs/official-102-timetable.jpg)：固定表格的核对依据，原表日期2026-09-19。

## 数据与验证

自动刷新10秒，手动最短5秒；站点缓存10分钟、路线缓存1小时，两方向隔离。没有数据库和历史回放。官方照片非直播，剩余站数为估算，具体车型未知。
HTML正则提取官方标题；动态站点及车辆从JSON接口取得，不应称为全部使用HTML正则采集。

```powershell
python -m unittest -v
```

第三方Leaflet库与许可证保留在static/vendor。下载的官网脚本、旧701X快照与一次性research文件已清理。浏览器实际操作仍需演示前检查。
