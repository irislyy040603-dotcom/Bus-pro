# 澳门102巴士实时可视化：完整项目说明

本文对应当前代码，不包含已删除的701X旧方案与研究脚本。

## 1. 项目目标与定位

为澳门102路线制作可运行的候车信息网页，完成“网络采集—解析—校验—缓存—可视化”的链路。重点解决：两个方向如何区分、车辆在哪里、候车点前方还有几站、站点现场长什么样。

本项目是本地课程演示系统：Python启动Flask，浏览器访问 http://127.0.0.1:5000 。没有数据库、用户登录或历史回放，不需要前端构建工具。

不能将系统描述为“全部信息通过正则从HTML提取”。当前HTML正则只提取官方页面标题，动态站点和车辆通过JSON接口获取。若评分要求主要业务数据必须来自HTML正则，该项仍未满足，需要与老师确认；不要隐瞒数据来源。

## 2. 功能分析

| 功能 | 输入与处理 | 用户看到的结果 |
|---|---|---|
| 双向路线 | direction=0或1，分别请求和缓存 | 对应方向的站名、站序及道路路线 |
| 候车点选择 | 用数组索引定位选中站点 | 候车站高亮、估算剩余站数 |
| 路线条 | 按官方顺序生成站点列表 | 官方站号、站名、暂停信息和车辆栏 |
| 车辆更新 | 用车牌关联定位与车辆编号 | 速度、车牌、车辆编号、地图位置 |
| 路线图 | 解析官方路线折线 | 绿色真实道路路线，不代表畅通 |
| 路线全图 | 切换CSS布局并调用invalidateSize | 地图展开；Escape返回 |
| 站点照片 | 站号转官方图片文件名 | 弹窗照片；失败时提示 |
| 班次表 | 按官方2026-09-19原表固定录入 | 工作日和周末/公众假期班次 |
| 更新与异常 | 10秒自动轮询、手动刷新、缓存 | 更新时间、失败/过期提示 |

照片是站点实景图片。固定班次间隔不是指定车辆的到站时间。车辆具体型号和每车GPS更新时间未取得，界面不编造。此前联调的两个方向为24和20个站点记录，这不是永久常量，以接口当前返回为准。

## 3. 文件与技术职责

```text
Bus-pro/
├── collector.py              请求、签名、HTML标题正则
├── app.py                    Flask路由、缓存、校验、合并
├── test_app.py               关键后端单元测试
├── requirements.txt          Flask依赖
├── templates/index.html      三板块HTML与固定班次表
├── static/app.js             刷新、候车计算、地图、照片交互
├── static/style.css          卡片、路线条、车辆栏、响应式布局
├── static/vendor/            Leaflet本地文件和许可证
├── docs/official-102-timetable.jpg  固定班次的官方原图依据
├── IMPLEMENTATION.md         本说明
├── PRESENTATION.md           四人分工、10分钟流程和讲稿
└── README.md                 安装与启动入口
```

后端只用Flask和Python标准库。urllib负责HTTP；json负责JSON；re负责局部正则；hashlib负责官方网页请求token格式中的MD5；threading防止同时重复采集；ThreadPoolExecutor并行等待独立接口。
前端使用原生JavaScript和Leaflet；OpenStreetMap提供底图。Leaflet负责地图展示，不提供巴士数据。vendor里的压缩库不是小组业务代码，不需要逐行解释。

## 4. 采集数据来源

基址：https://bis.dsat.gov.mo:37812
路线名称102，内部routeCode为00102；方向不是把数组反转，而是传不同参数请求。

| 路径 | 参数重点 | 返回及用途 |
|---|---|---|
| /macauweb/getRouteData.html | action=sd，routeName=102，dir | routeInfo：站名、站号、车道、停靠状态 |
| /macauweb/routestation/bus | action=dy，routeName=102，dir | 每站busInfo：车牌、车辆编号、状态 |
| /macauweb/routestation/location | routeCode=00102，dir | stationInfoList与busInfoList：经纬度、速度 |
| /ddbus/common/supermap/route/traffic | direction，routeCode | 分段routeCoordinates |
| /macauweb/index.html | 普通GET | HTML中的title |

官方照片：https://www.dsat.gov.mo/bres/bus_stop_img/
官方班次依据：https://www.dsat.gov.mo/bus/site/route_display.aspx?route=busroute_102
原图：https://www.dsat.gov.mo/bus/images/busroute/busroute_102.jpg

当前站点坐标随定位接口返回，仍会每次下载；10分钟缓存的是独立站点资料接口，不能说“所有站点字段都只下载一次”。

## 5. 请求签名与解析

collector.py的阅读顺序：make_token → request_data → fetch。

1. 参数字典保留插入顺序，拼为key=value&key=value。
2. 对参数文本生成MD5摘要。
3. 获取澳门UTC+8的年月日时分，按官方前端规则插入摘要。
4. 将token放进请求头，参数按表单编码放进POST请求体。
5. 15秒HTTP超时，保留TLS验证；with语句确保连接关闭。
6. json.load解析响应结构，后续检查业务成功码。

MD5在这里用于复现官方请求格式，不是数据加密，也不是项目自创身份认证。成功访问不等于有无限调用授权。

## 6. 正则表达式：三处实际用途（展示重点）

### 6.1 HTML标题提取：collector.py / extract_title

```python
match = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
return unescape(match.group(1)).strip()
```

实际代码还检查未匹配和空标题，失败抛出ValueError。

| 部分 | 含义 |
|---|---|
| r前缀 | Python原始字符串，便于写正则反斜线 |
| <title>与</title> | 匹配目标HTML标签 |
| (...) | 捕获标题，group(1)读取 |
| . | 任意字符；配合re.S可包含换行 |
| *? | 非贪婪重复，尽早在结束标签处停止 |
| re.I | 不区分标签大小写 |
| re.S | 点号可匹配换行 |
| unescape / strip | 解码&amp;等实体并去除首尾空白 |

例：`<TITLE> Bus &amp; Stop </TITLE>` → `Bus & Stop`。
实际用途：官方HTML → 标题 → /api/source → 网页来源名称。它确实参与运行，但提取的不是站点列表。
这是针对已观察到的title结构的短表达式，不是通用HTML解析器。例如带属性的title标签并未专门支持；网站结构变化可能使提取失败。

### 6.2 路线坐标：app.py / parse_route_points

```python
match = re.fullmatch(r"([^,]+),([^,]+)", point)
longitude, latitude = match.groups()
```

`[^,]`表示非逗号字符；`+`表示至少一个；两个括号分别提取经度、纬度。fullmatch要求完整匹配，不接受多出第三个字段的坐标。

例：`113.56,22.14;113.57,22.15;`：
1. split(';')得到各坐标，跳过末尾空项。
2. 正则提取两组文本。
3. coordinates用float转换并检查有限值及经纬度范围。
4. 输出Leaflet需要的`[[22.14,113.56],[22.15,113.57]]`。

这里的正则只检查结构，不单独证明数值合法；`bad,22`结构匹配但会在float转换时失败。把提取与数值校验分开，比写一个含所有数值范围的长正则更清晰。
这部分处理JSON里的坐标字符串，不属于HTML提取。

### 6.3 照片站号：app.py / photo

```python
re.fullmatch(r"[MTLC]\d+(?:/\d+)?", code)
```

`[MTLC]`限制首字母；`\d+`表示数字；`(?:...)`是不捕获分组；`?`允许可选的斜线及数字后缀。
例如M800/7、T372、L17能通过。站号通过后，M800/7变成m800_7.jpg，L17变成l17_1.jpg。
作用是验证参数，避免照片接口变成任意URL代理，不是采集HTML。

search用于从长HTML中查找局部内容；fullmatch用于验证完整字段。项目没有必要为了看起来“用了正则”而用正则代替JSON解析。

## 7. 后端主流程与缓存

```text
GET /api/route?direction=0
  → 校验方向，只接受0/1
  → 加锁，读取该方向states
  → 未到刷新间隔：返回最新缓存
  → 到时间：collect(direction)
      → 并行 get_stations / 车辆状态 / 定位
      → get_geometry(direction)
      → 比较三份站号顺序
      → merge_data标准化
  → 成功覆盖该方向缓存；失败保留旧结果
  → JSON返回前端
```

| 内容 | 策略 |
|---|---|
| 动态数据 | 自动请求间隔10秒，手动最短5秒 |
| 站点资料 | 每方向600秒，失败不缓存 |
| 路线几何 | 每方向3600秒 |
| HTML标题 | 独立锁，一小时内不重复尝试 |
| 照片 | 返回浏览器可缓存86400秒的响应头 |

没有数据库或历史保存；关闭进程后内存清空。已有旧结果没有最长保存期限，但失败时标stale。站序不同则清除站点缓存，下次重新取；临时停靠状态可能延迟10分钟。
平常同方向更新调用两个官方动态接口，约12次/分钟，不含首次加载、手动刷新和图片。缓存不是授权保证，当前没有429退避、403自动停采机制。

merge_data逻辑：按站序及编号核对三份数据 → 合并站点信息 → 建立车牌到车辆编号映射 → 合并车辆定位与速度。不能用站名作为唯一键，也不能把不同方向混在一个缓存里。
速度None、空字符串、负值、NaN等转成null；0必须保留。时间字段是采集完成时间，不是车辆GPS时间。

## 8. 前端主流程

refresh负责网络与加载状态；renderStops负责候车和路线条；updateMap负责地图；updateVehicles负责车辆；showPhoto负责图片弹窗。

首次加载请求数据；之后setInterval每10秒触发，页面隐藏时跳过。busy防止重叠请求，请求期间刷新和方向按钮禁用，finally恢复。
切换方向：切换0/1 → 重置候车点 → 清除旧图层/车辆 → 获取新方向 → 第一次自动缩放全线。
普通刷新：保留视角和滚动位置；比较静态数据内容，变化才重画站点及路线；车辆按车牌复用marker，用setLatLng更新位置。
路线条记录车辆旧DOM纵坐标，在新的官方关联站点间做短过渡动画。这只是展示过渡，不是连续GPS轨迹或速度模拟。减少动画偏好下不播放。
弹窗内容通过textContent写入，避免把上游文本直接当HTML执行。

### 剩余站数如何计算
候车站索引为j，车辆关联站索引为i。只考虑i≤j的车辆；同站车辆还会按返回status筛选；从i+1到j统计未暂停的站点，取最小值。例：车在索引2、候车站索引5，中间全停靠则约3站。
已经过站的车不绕回计算；没有候选不表示停运；数据过期不估算。这个方法依赖上游站点关联及状态语义，未建立独立到站预测模型，不能保证实际还有精确几站。

## 9. 测试、局限与清理

运行 `python -m unittest -v`。六项测试覆盖标题及HTML实体、坐标正则异常、站点缓存与方向隔离、速度未知/零值、坐标合法性、动态缓存/刷新/过期/无效方向。
这些测试不等于浏览器视觉验收，也未覆盖全部候车计算边界。现场演示前应检查两方向、照片、全图、手动刷新和固定班次表。

保留功能代码、测试、Leaflet许可证、官方班次原图与文档。删除根目录旧JSON快照、官网HTML/JS下载副本、research一次性脚本及样本、Python字节码缓存；不删除.git和用户提供的D:/index.html。
曾发现页面将photo-source链接注释后，JS仍直接设置它的href，会中断照片弹窗；现加存在性判断，保留用户隐藏链接的选择。
