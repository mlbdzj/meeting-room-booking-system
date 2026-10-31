# 智能会议室预约系统

基于 Agent 的会议空间预约平台，使用 **React + FastAPI + MySQL** 实现。系统覆盖会议空间、会议室规格、按小时预约、时段冲突控制、容量校验、预约审核和经营看板，并保留完整的智能助手、工具调用、知识库和会话历史功能。

## 功能亮点

- **会议空间与会议室管理**：维护空间开放时段、地址、配套等级、会议室布局、时租价、容量、数量和设备。
- **按小时预约**：使用开始/结束时间占用会议室，支持半小时计费；同一时段的待确认与已确认预约共同占用余量。
- **业务规则统一**：页面预约与 Agent 预约共用 `reservation_service`，校验空间开放时间、会议时长、容量、剩余数量和总价。
- **预约审核闭环**：待确认预约可由管理员确认或拒绝，确认时再次校验余量；会员可取消自己的预约。
- **经营看板**：展示空间数、会议室规格数、会员数、待确认预约、今日预约、会议室使用率与空间排行。
- **智能助手保留**：8 个受权限约束的工具，支持大模型 function calling、本地规则引擎降级、知识库检索和会话历史。
- **自然语言预约**：例如「下周五上午 10 点到 12 点订杭州西湖商务中心西湖 A 会议室，10 人」，生成预约卡片，用户确认后才写库。
- **双角色权限**：空间管理员与会员用户使用前端路由守卫和后端依赖注入双重校验。
- **浅色 / 深色主题**：一键切换并记住选择，页面、表格、弹窗和 Agent 对话同步换肤。

## 界面预览

<table>
  <tr>
    <td width="50%"><img src="docs/screenshots/login.png" alt="登录页"><br>
      <sub>简约登录页：浅色 / 深色主题切换</sub></td>
    <td width="50%"><img src="docs/screenshots/home.png" alt="经营首页"><br>
      <sub>首页看板：空间、会议室、预约与使用率</sub></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/home-dark.png" alt="深色主题"><br>
      <sub>深色主题：统一表格、卡片与导航视觉</sub></td>
    <td><img src="docs/screenshots/venues.png" alt="会议空间管理"><br>
      <sub>会议空间管理：紧凑表格与清晰状态</sub></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/reservation.png" alt="预约会议室"><br>
      <sub>预约弹窗：实时余量、容量与费用预估</sub></td>
    <td><img src="docs/screenshots/reservation-review.png" alt="预约审核"><br>
      <sub>预约审核：筛选、确认、拒绝和取消</sub></td>
  </tr>
</table>

<p align="center">
  <img src="docs/screenshots/agent.png" alt="智能助手" width="86%"><br>
  <sub>智能助手：工具调用来源、知识库建议与自然语言预约</sub>
</p>

## 技术栈

| 层次 | 技术 |
| --- | --- |
| 前端 | React 19、TypeScript、React Router 7、Ant Design 5、Zustand、Vite 8 |
| 后端 | FastAPI、SQLAlchemy 2.x、Pydantic v2、Uvicorn |
| 依赖管理 | 后端 uv，前端 npm |
| 数据库 | MySQL 8；测试默认使用内存 SQLite |
| 鉴权 | HMAC-SHA256 签名 Token + PBKDF2 加盐密码哈希 |
| Agent | OpenAI 兼容 SDK、function calling、本地知识库兜底 |

## 快速开始

### 1. 创建数据库

```sql
CREATE DATABASE meeting_room_booking DEFAULT CHARSET utf8mb4;
```

首次启动会自动建表，并写入 4 个会议空间、11 个会议室规格、演示预约和 20 条预约知识库。

### 2. 配置后端

```powershell
cd backend
Copy-Item .env.example .env
```

修改 `.env` 中的数据库账号和密码。Agent 不配置密钥时会自动使用本地知识库模式。

### 3. 启动后端

```powershell
uv sync
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

接口文档：<http://127.0.0.1:8000/docs>

### 4. 启动前端

```powershell
cd frontend
npm install
npm run dev
```

访问 <http://127.0.0.1:5173>。

### 5. 演示账号

| 角色 | 账号 | 密码 |
| --- | --- | --- |
| 空间管理员 | `admin` | `123456` |
| 会员用户 | `student` | `123456` |

## 测试与构建

```powershell
cd backend
uv run pytest

cd ../frontend
npm run build
npm run capture:screenshots
```

当前覆盖 103 个后端用例，包括自然语言时间解析、时段重叠、容量限制、开放时间、预约幂等、Agent 权限隔离、审核阶段二次校验和会员删除级联清理。

真实 MySQL 测试可设置独立测试库：

```powershell
$env:TEST_DATABASE_URL='mysql+pymysql://root:123456@127.0.0.1:3306/meeting_room_booking_test'
uv run pytest
```

## 目录结构

```text
backend/
  app/
    agent/        Agent 编排、工具、自然语言预约解析、知识库检索
    api/          鉴权、空间、会议室、预约、审核、统计、知识库路由
    core/         配置与 Token / 密码安全
    db/           数据库连接与会话
    models/       Venue、MeetingRoom、Reservation、User、Knowledge、Chat
    schemas/      Pydantic 入参和出参
    services/     页面与 Agent 共用的预约校验和计费
    init_db.py    建表与演示数据
    main.py       FastAPI 入口
  tests/          后端测试
  scripts/        Agent 冒烟测试与解析自检
frontend/
  src/
    api/          HTTP 请求封装与类型
    components/   预约弹窗、Agent 对话窗口
    config/       角色化侧边菜单
    router/       登录与角色守卫
    store/        登录态、预约状态字典
    theme/        浅色 / 深色主题配置
    views/        空间、会议室、预约、审核、会员、知识库
docs/
  interview-prep.md
```

## 预约规则

1. 开始时间不能早于当前时间，结束时间必须晚于开始时间。
2. 预约时段必须处于所选空间的开放时间内。
3. 参会人数不能超过「会议室容量 × 预约间数」。
4. 时段按左闭右开 `[start_at, end_at)` 统计，首尾相接不会冲突。
5. 待确认与已确认预约都会占用会议室余量。
6. 总价 = 时租价 × 小时数 × 间数，使用服务端数据计算。
7. 已确认预约结束后自动转为已完成。

## Agent 工具

| 工具 | 作用 | 权限 |
| --- | --- | --- |
| `search_knowledge` | 检索预约知识库 | 登录用户 |
| `list_venues` | 查询会议空间、开放时段和会议室数量 | 登录用户 |
| `check_meeting_room_availability` | 查询指定时段的会议室价格和余量 | 登录用户 |
| `list_my_reservations` | 查询自己的预约 | 登录用户 |
| `list_pending_reservations` | 查询待确认预约 | 仅管理员 |
| `system_statistics` | 查询空间使用统计 | 登录用户，按角色限定范围 |
| `reservation_rules` | 查询预约规则 | 登录用户 |
| `prepare_reservation` | 生成预约预览草稿，不写库 | 登录用户 |

### 两段式预约

流程为「口语解析 → 预约预览卡 → 用户确认 → 确定性校验 → 写入数据库」：

1. `prepare_reservation` 只构建草稿，不执行 `db.add` 或提交。
2. 前端根据服务端存储的草稿渲染卡片。
3. 用户点击「确认预约」后，后端重新执行完整时间、容量和库存校验。
4. 同一草稿只能确认一次，重复确认不会重复建单。
5. Agent 与页面共用同一服务层，模型无法绕过业务规则。

自然语言示例：

> 下周五上午 10 点到 12 点订杭州西湖商务中心西湖 A 会议室，10 人，需要视频会议

> 明天下午 2 点到 4 点预约深圳湾创新中心南山 A 会议室，18 人

> 下周三上午 9 点半到 11 点半订两间上海外滩云舍会议空间外滩 1 号，12 人

## 主要接口

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| POST | `/api/auth/register`、`/api/auth/login` | 注册、登录 | 公开 |
| GET/PUT | `/api/auth/me` | 当前用户信息 / 修改资料 | 登录 |
| GET | `/api/venues` | 会议空间列表 | 登录 |
| GET | `/api/venues/{id}/availability` | 指定时段的会议室余量 | 登录 |
| POST/PUT/DELETE | `/api/venues`、`/api/venues/{id}` | 会议空间维护 | 管理员 |
| GET | `/api/meeting-rooms`、`/api/meeting-rooms/all` | 会议室分页 / 全量 | 登录 |
| POST/PUT/DELETE | `/api/meeting-rooms`、`/api/meeting-rooms/{id}` | 会议室维护 | 管理员 |
| POST | `/api/reservations` | 提交预约 | 登录 |
| GET | `/api/reservations/my` | 我的预约 | 登录 |
| GET | `/api/reservations` | 全部预约与筛选 | 管理员 |
| POST | `/api/reservations/{id}/review` | 确认 / 拒绝预约 | 管理员 |
| POST | `/api/reservations/{id}/cancel` | 取消预约 | 本人 / 管理员 |
| DELETE | `/api/reservations/{id}` | 删除预约 | 管理员 |
| GET | `/api/stats/overview` | 经营看板 | 登录 |
| POST | `/api/agent/chat` | 智能助手对话 | 登录 |
| POST | `/api/agent/actions/confirm` | 确认预约草稿 | 本人草稿 |
| POST | `/api/agent/actions/cancel` | 放弃预约草稿 | 本人草稿 |
| GET/DELETE | `/api/agent/sessions...` | 会话历史 | 本人 |
| GET/POST/PUT/DELETE | `/api/knowledge`、`/api/knowledge/{id}` | 知识库查询与维护 | 登录 / 管理员 |

## Agent 自检

```powershell
cd backend

# 分别以会员和管理员身份运行典型问答与自然语言预约
.\.venv\Scripts\python.exe scripts\agent_smoke_test.py

# 强制本地知识库模式
$env:AGENT_PROVIDER='local'
.\.venv\Scripts\python.exe scripts\agent_smoke_test.py

# 查看口语解析结果
.\.venv\Scripts\python.exe scripts\reservation_parser_check.py
```

## 后续规划

- 邮箱 / 短信预约提醒与日历订阅。
- 设备套餐、茶歇下单和费用结算。
- 并发写入时使用行锁或条件库存更新进一步强化防超卖。
- Docker Compose 一键部署与 GitHub Actions 持续集成。
- 知识库向量检索和 Agent 回归评测集。

本项目基于 [MIT License](LICENSE) 开源。
