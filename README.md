# 空气监测点数据录入系统

面向空气质量监测业务的**监测点台账 + 监测数据录入 + 超标记录标注 + 数据查询**一体化系统。
后端使用 Flask + SQLAlchemy 以蓝图/服务分层组织, 前端使用 React + Vite 按业务模块拆分页面,
超标判定严格依据 **GB 3095-2012《环境空气质量标准》二级浓度限值** 自动完成。

## 功能模块

| 模块 | 路由 | 主要能力 |
| --- | --- | --- |
| 运行概览 | `/overview` | 监测点/设备规模、数据量与达标率、超标与待标注统计、近 7 日数据量趋势、待办超标列表 |
| 监测点台账 | `/stations` | 台账增删改查、区域/类型/状态筛选、点位详情与分因子统计、级联清理关联数据 |
| 设备与校准 | `/devices` | 设备档案(型号/厂商/安装位置)、分因子量程、校准周期管理、校准登记与结束、设备可用性自动判定 |
| 监测数据录入 | `/measurements` | 按“监测点 + 时刻 + 周期”成组录入多因子浓度、关联采集设备、校准期数据自动标记无效、超量程提示、超标校验预览、重复数据覆盖、录入结果回执 |
| 超标记录标注 | `/exceedances` | 超标自动建单、单条/批量标注(确认 / 忽略 / 重置)、等级人工修正、标注留痕与统计 |
| 数据查询 | `/query` | 多条件组合检索(含设备/有效性)、聚合统计(按因子/站点/区域/日/月等)、达标率(排除无效数据)、分页浏览、CSV 导出 |

设计要点:

- **超标自动判定**: 数据写入时即按“因子 + 数据周期”取用限值, 计算超标倍数并分级, 同步生成待标注超标记录; 修正数据后超标记录自动更新或撤销。
- **设备校准与数据有效性**: 设备登记校准开始后进入“校准中(不可用)”, 校准时间段内录入该设备的数据**保留但自动标记为无效**; 超过校准周期未校准则标记“校准超期”。无效数据不计入达标率统计, 录入界面给出醒目提示; 校准合格结束后设备恢复可用, 系统按已闭合校准窗口重算历史数据有效性。
- **业务规则集中在后端**: 限值与分级规则位于 `backend/app/domain/`, 校准窗口与有效性规则位于 `backend/app/services/device_service.py`, 前端仅做展示与前置校验, 避免规则分叉。
- **模块化组织**: 后端按 `api / services / models / domain / utils` 分层; 前端每个业务模块独占目录, 公共能力沉淀在 `components/`、`hooks/`、`api/`。

## 技术栈

| 层次 | 选型 |
| --- | --- |
| 后端 | Python 3.12 · Flask 3 · Flask-SQLAlchemy 3 · Flask-CORS · Gunicorn |
| 数据库 | SQLite(默认, 零依赖) / PostgreSQL 16(可选, compose 覆盖文件) |
| 前端 | React 18 · React Router 6 · Vite 7 · Axios · 原生 CSS(设计令牌 + 组件类) |
| 部署 | Docker 多阶段构建 · Nginx 静态托管与 `/api` 反向代理 · docker compose |
| 测试 | Pytest(67 个后端用例: 接口 + 领域规则) |

## 目录结构

```text
.
├── backend/                     # Flask 后端
│   ├── app/
│   │   ├── __init__.py          # 应用工厂 create_app
│   │   ├── config.py            # 多环境配置 (development/production/testing)
│   │   ├── extensions.py        # db / cors 单例, SQLite 外键开关
│   │   ├── errors.py            # 统一异常与 JSON 错误响应
│   │   ├── commands.py          # flask init-db / seed / reset-db / stats
│   │   ├── seed.py              # 演示数据生成与启动引导
│   │   ├── domain/              # 业务规则: 因子限值、枚举、超标分级
│   │   ├── models/              # Station / Device / DeviceRange / CalibrationRecord / Measurement / Exceedance
│   │   ├── services/            # 台账、设备校准、录入、标注、查询统计业务逻辑
│   │   ├── api/                 # 蓝图: meta / stations / devices / measurements / exceedances / query
│   │   └── utils/               # 校验器、分页、CSV 导出
│   ├── tests/                   # Pytest 用例
│   ├── Dockerfile · docker-entrypoint.sh · requirements*.txt
│   └── run.py · wsgi.py
├── frontend/                    # React 前端
│   ├── src/
│   │   ├── api/                 # 按模块拆分的接口封装 + axios 客户端
│   │   ├── components/          # layout(侧边栏/顶栏) 与 common(表格/分页/弹窗/表单等)
│   │   ├── constants/           # 路由、标签与色板映射
│   │   ├── hooks/               # useListQuery / useAsyncData / useOptions
│   │   ├── pages/               # overview / stations / devices / measurements / exceedances / query
│   │   ├── styles/global.css    # 设计令牌与公共样式
│   │   └── utils/               # 时间/数值格式化、下载
│   ├── Dockerfile · nginx.conf · vite.config.js
│   └── package.json
├── docker-compose.yml           # 默认编排(SQLite 卷)
└── docker-compose.postgres.yml  # 可选覆盖文件(PostgreSQL)
```

## 快速开始

### 方式一: Docker Compose (推荐)

```bash
docker compose up -d --build
```

启动完成后:

| 服务 | 地址 | 说明 |
| --- | --- | --- |
| 前端 | http://localhost:8080 | Nginx 托管, `/api` 反向代理到后端 |
| 后端 | http://localhost:5000/api/meta/health | 健康检查 |

首次启动会自动建表并写入演示数据(8 个监测点 / 8 台监测设备与 9 条校准记录 / 1200 条监测数据, 其中 198 条处于校准期被标记无效 / 56 条超标记录), 可通过环境变量 `SEED_DEMO=false` 关闭。

```bash
docker compose ps          # 查看容器与健康状态
docker compose logs -f backend
docker compose down        # 停止(保留数据卷)
docker compose down -v     # 停止并删除数据卷
```

### 方式二: 本地开发

后端(默认使用 SQLite, 无需额外依赖):

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
python -m flask --app wsgi init-db      # 建表
python -m flask --app wsgi seed         # 可选: 写入演示数据
python run.py                           # http://127.0.0.1:5000
```

前端(Vite 开发服务器会把 `/api` 代理到 `http://127.0.0.1:5000`):

```bash
cd frontend
npm install
npm run dev                             # http://127.0.0.1:5173
```

> 若后端不在默认地址, 通过 `VITE_PROXY_TARGET=http://host:port npm run dev` 指定, 或复制 `.env.example` 为 `.env` 后修改。

### 方式三: 使用 PostgreSQL

```bash
docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d --build
```

覆盖文件会新增 `postgres:16-alpine` 服务并把后端 `DATABASE_URL` 指向它; 后端容器会等待数据库健康检查通过后再建表初始化。

## 超标判定规则

判定逻辑位于 `backend/app/domain/exceedance_rules.py`, 限值定义位于 `backend/app/domain/standards.py`。

**GB 3095-2012 二级浓度限值**

| 监测因子 | 1 小时平均 | 24 小时平均 | 单位 |
| --- | --- | --- | --- |
| PM2.5 | 不设限值(仅记录) | 75 | μg/m³ |
| PM10 | 不设限值(仅记录) | 150 | μg/m³ |
| SO₂ | 500 | 150 | μg/m³ |
| NO₂ | 200 | 80 | μg/m³ |
| CO | 10 | 4 | mg/m³ |
| O₃ | 200 | 160 | μg/m³ |

- **判定**: `监测值 > 限值` 即判为超标, 记录限值快照与原值, 避免限值调整后历史数据失真。
- **分级**: 超标倍数 = 监测值 / 限值; `1.0 ~ 1.5 倍` 为轻度超标, `1.5 ~ 2.0 倍` 为中度超标, `≥ 2.0 倍` 为重度超标。
- **无 1 小时限值的因子**(PM2.5、PM10 小时值)仅记录数值, 不参与超标判定, 避免误报。
- **标注状态**: `待标注(pending)` 由系统自动创建, 人工标注为 `已确认(confirmed)` 或 `已忽略(ignored)`; 确认与忽略都必须填写标注说明, 用于后续追溯。

## API 概览

统一前缀 `/api`, 成功直接返回数据对象; 失败返回 `{"error": {"code": "...", "message": "...", "fields": {...}}}`。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/meta/health` | 健康检查(数据库连通性、时区、限值标准) |
| GET | `/api/meta/pollutants` | 监测因子清单与限值 |
| GET | `/api/meta/options` | 枚举选项(监测点、区域、状态、类型等) |
| GET | `/api/meta/overview` | 首页概览聚合数据 |
| GET/POST | `/api/stations` | 台账分页查询 / 新增 |
| GET/PUT/DELETE | `/api/stations/{id}` | 台账详情(含分因子统计) / 更新 / 删除(级联) |
| GET | `/api/stations/options` | 下拉选项(监测点、区域) |
| GET | `/api/stations/summary` | 台账规模统计 |
| GET/POST | `/api/devices` | 设备分页查询(动态状态过滤) / 登记 |
| GET/PUT/DELETE | `/api/devices/{id}` | 设备详情(量程+校准记录) / 更新 / 删除(监测数据解除关联但保留) |
| GET | `/api/devices/options` | 设备下拉选项(可按 `station_id` 过滤) |
| GET | `/api/devices/summary` | 设备状态统计(含进行中校准数) |
| POST | `/api/devices/{id}/calibrations` | 登记校准开始(设备置为校准中, 拒绝重叠窗口) |
| POST | `/api/devices/calibrations/{id}/finish` | 登记校准结束(恢复可用, 重算窗口内数据有效性) |
| GET | `/api/devices/calibrations` | 校准记录查询 |
| GET | `/api/measurements` | 监测数据分页查询(含筛选汇总) |
| POST | `/api/measurements/entries` | **成组录入**: 一个监测点 + 一个时刻 + 多个因子(可带 `device_id`) |
| POST | `/api/measurements/preview` | 超标/量程/有效性校验预览(不写库) |
| GET | `/api/measurements/device-availability` | 查询设备在指定时刻的可用状态与量程 |
| DELETE | `/api/measurements/{id}` | 删除监测数据 |
| GET | `/api/measurements/export` | 按条件导出 CSV(含设备、有效性、无效原因列) |
| GET | `/api/exceedances` | 超标记录查询(含筛选统计) |
| GET | `/api/exceedances/{id}` | 超标记录详情(含关联监测数据) |
| PATCH | `/api/exceedances/{id}` | 单条标注 |
| POST | `/api/exceedances/annotations` | 批量标注 |
| GET | `/api/exceedances/summary` | 超标统计(状态/等级/高发因子/站点排名) |
| GET | `/api/query/measurements` | 高级条件检索 |
| GET | `/api/query/statistics` | 聚合统计(`group_by` + `metric`) |
| GET | `/api/query/export` | 查询结果导出 CSV |

`POST /api/measurements/entries` 请求示例:

```json
{
  "station_id": 1,
  "device_id": 3,
  "measured_at": "2026-09-14 10:00",
  "period": "hourly",
  "data_source": "manual",
  "recorder": "王敏",
  "remark": "在线设备人工比对",
  "overwrite": false,
  "entries": [
    { "pollutant": "PM25", "value": 82.5 },
    { "pollutant": "SO2", "value": 640 },
    { "pollutant": "CO", "value": 1.4 }
  ]
}
```

若该设备在监测时刻处于校准中/校准超期, 响应中 `device_unavailable=true`、`invalid_reason` 标明原因,
对应记录写入但标记无效, `summary.invalid_count` 给出条数; 超出设备登记量程的因子会列入 `out_of_range`(仅提示)。

响应会返回本次新增/更新条数、超标记录、重复项与逐因子判定结果:

```json
{
  "created": [ "..." ],
  "updated": [],
  "exceedances": [ { "pollutant": "SO2", "level": "moderate", "exceed_ratio": 1.28 } ],
  "duplicates": [],
  "summary": { "created_count": 3, "updated_count": 0, "exceeded_count": 1, "duplicate_count": 0 }
}
```

## 数据模型

| 表 | 关键字段 | 说明 |
| --- | --- | --- |
| `stations` | `code`(唯一) `name` `area` `station_type` `status` `longitude/latitude` `installed_at` | 监测点台账 |
| `devices` | `code`(唯一) `name` `model` `manufacturer` `station_id` `install_location` `calibration_interval_days` `last_calibration_at` `status` | 监测设备档案; `status=retired` 为人工停用, `校准中/校准超期` 由校准记录动态计算 |
| `device_ranges` | `device_id` `pollutant`(唯一) `min_value` `max_value` `unit` | 分因子量程; 录入越界给提示但不阻断 |
| `calibration_records` | `device_id` `started_at` `finished_at` `result(pass/fail)` `calibrator` `organization` `note` | 校准窗口; `finished_at` 为空表示校准进行中(设备不可用) |
| `measurements` | `station_id` `device_id` `pollutant` `period` `value` `limit_value` `exceed_ratio` `is_exceeded` `is_valid` `invalid_reason` `measured_at` `data_source` `recorder` | 监测数据; `(station_id, pollutant, period, measured_at)` 唯一 |
| `exceedances` | `measurement_id`(唯一) `status` `level` `note` `annotator` `annotated_at` | 超标记录与人工标注 |

删除监测点会级联清理其监测数据与超标记录; 删除设备会删除校准记录, 历史监测数据保留(置空 `device_id`)。

### 设备校准与数据有效性规则

- **设备状态**: `可用(available)` / `校准中(calibrating)` / `校准超期(overdue)` / `停用(retired)`。
  校准中与超期由校准记录动态计算; 登记校准开始即不可用, 校准合格结束后恢复可用并推进“最近校准时间”。
- **无效数据**: 监测时刻落在该校准时间窗 `[started_at, finished_at]` 内(进行中的窗口只有下界),
  或设备已超校准周期且之后没有新校准覆盖时, 该设备录入的数据 `is_valid=false`:
  - `invalid_reason=calibration`: 设备校准中;
  - `invalid_reason=calibration_overdue`: 设备校准超期;
  - `invalid_reason=manual`: 人工判定无效(系统重算时不覆盖)。
- **数据保留**: 无效数据原样保留(超标判定与超标记录照常生成), 仅从达标考核中剔除。
  补登一条“进行中”校准不会追溯作废此前已入库的数据; 校准结束(窗口闭合)时系统按完整窗口重算有效性。
- **达标率**: `达标率 = 未超标的有效数据 / 全部有效数据`;
  接口同时返回 `exceed_rate`(全量超标率, 含无效数据)与 `compliance_rate`(有效数据达标率)。

## 配置项

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `FLASK_ENV` | `development` | `development` / `production` / `testing` |
| `DATABASE_URL` | SQLite(`backend/instance/air_monitor.db`) | 如 `postgresql+psycopg2://user:pass@host:5432/db` |
| `CORS_ORIGINS` | `*` | 允许的前端来源, 逗号分隔 |
| `TIMEZONE` | `Asia/Shanghai` | 展示时区 |
| `AUTO_INIT_DB` / `AUTO_SEED` | `true`(开发) | 启动时自动建表 / 写入演示数据 |
| `SEED_DEMO` | `true` | Docker 容器启动时是否写入演示数据 |
| `GUNICORN_WORKERS` | `2` | 生产容器 worker 数量 |
| `VITE_API_BASE` | `/api` | 前端接口前缀 |
| `VITE_PROXY_TARGET` | `http://127.0.0.1:5000` | 开发代理的后端地址 |

## 测试与校验

```bash
cd backend
python -m pytest -q          # 67 个用例: 台账/设备与校准 CRUD、录入与超标判定、校准期无效标记与达标率排除、标注规则、查询统计与导出、元数据接口

cd frontend
npm run build                # 生产构建校验
```

健康检查与常用命令:

```bash
curl http://localhost:5000/api/meta/health
python -m flask --app wsgi stats      # 查看监测点/数据/超标记录数量
python -m flask --app wsgi reset-db   # 重置数据库并重建演示数据
```

## 常见问题

- **端口被占用**: 后端改 `PORT=5001 python run.py`(同时调整 `VITE_PROXY_TARGET`), 或修改 compose 的端口映射。
- **想清空演示数据**: `python -m flask --app wsgi reset-db --empty`, 或 `docker compose down -v` 后重新启动。
- **SQLite 文件位置**: 本地开发为 `backend/instance/air_monitor.db`; Docker 部署为数据卷 `air-monitor-data` 中的 `/data/air_monitor.db`。
- **前端页面 404 / 刷新报错**: Nginx 已配置 SPA 回退(`try_files ... /index.html`), 自定义部署时需保留该配置。
- **时区**: 系统按“本地墙钟时间”存储与展示监测时间, 部署时请保持后端 `TIMEZONE` 与业务所在地一致。
