# 智能会议室预约系统

基于 Agent 的会议空间预约平台：**React + FastAPI + MySQL** 全栈实现，内置支持工具调用（function calling）与自然语言下单的客服助手，覆盖会议空间与会议室类型管理、按天预约、会议室余量库存与超卖控制、预约确认的完整流程。

- 🧠 **客服助手**：8 个受权限约束的工具，可查询空间、会议室类型价格、剩余会议室余量与预约状态
- 🤖 **自然语言下单**：一句话生成预约卡片，用户点击确认后才写入数据库（人机协同，而非让模型直接下单）
- 🛡️ **AI 无法绕过业务规则**：页面下单与助手下单共用同一套校验（含会议室余量库存与超卖控制）
- 🔌 **可降级**：未配置大模型密钥或调用失败时，自动切换到本地知识库引擎，功能不中断
- 📋 **完整业务闭环**：注册登录、会议空间/会议室类型/会员管理、按天预约、总价计算、预约确认、取消与使用开始率看板

> 项目规模：后端 41 个文件 / 3260+ 行 Python + 6 个文件 / 890+ 行测试，前端 26 个源文件 / 4000+ 行 TypeScript + CSS，43 个 REST 接口，7 张数据表，98 个 pytest 用例

## 界面预览

<table>
  <tr>
    <td width="50%"><img src="docs/screenshots/home.png" alt="经营看板"><br>
      <sub>经营看板：空间 / 会议室类型 / 会员 / 待确认预约，今日使用开始率与本周空间排行（会员登录时只统计本人预约）</sub></td>
    <td width="50%"><img src="docs/screenshots/agent.png" alt="客服助手"><br>
      <sub>客服助手：一句话生成预约预览卡片，点击「确认下单」之前不写入数据库</sub></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/reservation.png" alt="预约弹窗"><br>
      <sub>预约弹窗：按日期实时显示剩余会议室余量与总价预估，超出会议室余量直接拦截</sub></td>
    <td><img src="docs/screenshots/reservation-review.png" alt="预约确认"><br>
      <sub>预约确认：待确认预约优先排序，已确认 / 已完成 / 已拒绝等历史预约同样可见</sub></td>
  </tr>
</table>

<p align="center">
  <img src="docs/screenshots/venues.png" alt="会议空间列表" width="80%"><br>
  <sub>会议空间浏览：会员按卡片查看空间信息与可预约会议室类型，管理员另见表格视图与维护入口</sub>
</p>

## 一、功能亮点

### 客服助手（Agent）

- 基于 function calling 的工具编排：模型自主决定查询空间、会议室状态价格、个人预约、经营数据等
- **权限收敛**：普通会员问「有哪些待确认预约」只会得到权限说明，问「我的预约」只返回本人记录
- **自然语言预约**：解析「下周五使用开始两晚的高级大床房，2 个人」这类口语描述，生成预约确认卡片
- **写操作人在环路**：草稿存服务端、前端只回传消息 ID、确认时二次校验库存、同一条草稿只能确认一次
- **优雅降级**：大模型不可用时切换本地知识库引擎，回答会标注来源
- 管理员可维护客服知识库（分类/问题/答案/关键词/启停），修改后立即生效

### 业务功能

- 双角色（空间管理员 / 会员用户）权限体系，前端路由守卫 + 后端依赖注入双重校验
- **按天预约与库存控制**：预约按 [使用开始日期, 使用结束日期) 占用会议室余量，按下单区间汇总占用间数，剩余不足直接拒单，避免超卖
- **价格计算**：总价 = 会议室类型单价 × 晚数 × 间数，下单时自动结算并展示
- 预约校验：使用开始日期不早于今天、使用结束晚于使用开始、间数不超过剩余会议室余量、人数不超过「可住人数 × 间数」
- 预约状态机：待确认 → 已确认 / 已拒绝 / 已取消，使用结束日期已过的已确认预约自动转为已完成
- 管理员预约确认（确认时再次校验库存）、会员自助取消、管理员代取消与删除
- 首页经营看板：空间数、会议室类型数、会员数、待确认预约、今日使用开始、**今日使用开始率**，以及按本周使用开始预约数排序的空间排行

## 二、技术栈

| 层次 | 技术 |
| --- | --- |
| 前端 | React 19、TypeScript、React Router 7、Ant Design 5、Zustand、Vite 8 |
| 后端 | FastAPI、SQLAlchemy 2.x、Pydantic v2、Uvicorn |
| 依赖管理 | 后端 uv（`pyproject.toml` + `uv.lock`），前端 npm |
| 数据库 | MySQL 8（PyMySQL 驱动） |
| 鉴权 | 自实现 HMAC-SHA256 签名 Token + PBKDF2 加盐密码哈希（零额外依赖） |
| 智能助手 | OpenAI 兼容接口（DeepSeek / OpenAI）+ function calling 工具编排 + 本地知识库兜底引擎 |

## 三、环境要求

- Python 3.11+ 与 [uv](https://docs.astral.sh/uv/)（`uv` 会自动安装并托管 `.python-version` 指定的解释器）
- Node.js 18+（开发环境为 24）
- MySQL 8.0

## 四、快速开始

### 1. 准备数据库

```sql
CREATE DATABASE meeting_room_booking DEFAULT CHARSET utf8mb4;
```

后端首次启动会自动建表并写入演示数据（4 家会议空间、11 个会议室类型、演示预约、20 条客服知识库）。

### 2. 配置后端环境变量

```powershell
cd backend
Copy-Item .env.example .env    # 然后按需修改数据库账号密码
```

`backend/.env` 不会被提交到仓库，可配置项见 `backend/.env.example`。

### 3. 启动后端

```powershell
cd backend
uv sync                                              # 按 uv.lock 创建 .venv 并装好依赖
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

`uv sync` 会自动下载 `.python-version` 指定的 Python 版本，不需要手动 `python -m venv` 或 `pip install`。

接口文档：<http://127.0.0.1:8000/docs>

### 4. 启动前端

```powershell
cd frontend
npm install
npm run dev
```

访问 <http://127.0.0.1:5173>（开发服务器已将 `/api` 代理到 `127.0.0.1:8000`，见 `frontend/vite.config.ts`）。

### 5. 演示账号

| 角色 | 账号 | 密码 |
| --- | --- | --- |
| 空间管理员 | `admin` | `123456` |
| 会员用户 | `student` | `123456` |

### 6. 运行测试

```powershell
cd backend
uv run pytest
```

`uv run` 会自动使用包含 dev 依赖组的项目环境；`pytest` 配置（`testpaths` / `pythonpath`）已写入 `backend/pyproject.toml`。

98 个用例，覆盖库存区间重叠与超卖拦截、日期 / 会议室余量 / 人数校验、价格结算、权限隔离、助手草稿确认的幂等与二次校验、知识库降级等核心链路。

- 默认跑在内存 SQLite 上：不依赖 MySQL、不调用外部大模型，也不会碰开发库
- 需要对着真实 MySQL 跑时，用 `TEST_DATABASE_URL` 指向一个测试库（夹具会自动建表与清理，请不要指向开发库）

```powershell
$env:TEST_DATABASE_URL='mysql+pymysql://root:123456@127.0.0.1:3306/meeting_room_booking_test'
uv run pytest
```

## 五、目录结构

```
backend/
  app/
    core/        配置与安全工具（Token 签发校验、密码哈希）
    db/          数据库连接与会话
    models/      ORM 模型：用户、会议空间、会议室类型、预约、知识库、会话
    schemas/     Pydantic 出入参模型
    services/    业务规则（按天预约、库存与超卖校验、价格计算，页面与助手共用）
    api/         依赖注入、序列化、各业务路由
    agent/       客服助手：tools（工具定义）、engine（编排与降级）、
                 llm（大模型客户端）、knowledge（知识库检索）、reservation（口语解析与草稿）
    init_db.py   建表、字段补齐与演示数据
    main.py      应用入口（CORS、异常处理、生命周期）
  pyproject.toml 依赖声明 + dev 依赖组 + pytest 配置
  uv.lock        锁定的依赖版本（由 uv sync 生成）
  .python-version 项目使用的 Python 版本
  tests/         pytest 用例：库存与超卖、权限隔离、助手草稿幂等、降级问答
  scripts/       冒烟测试与解析自检脚本
docs/
  screenshots/   README 界面截图
frontend/
  src/
    api/         request（fetch 封装：Token、401、错误文案）与各域接口封装
    store/       Zustand 登录态与角色 / 预约状态字典
    router/      路由表与登录态 / 角色守卫
    config/      侧边菜单配置（菜单渲染与页面标题共用）
    hooks/       useDocumentTitle 等通用 Hook
    layouts/     主框架（顶栏、角色化菜单、个人信息、修改密码）
    components/  预约弹窗、客服助手对话窗口（含预约确认卡片）
    views/       登录、注册、首页概览、会议空间管理、会议室类型管理、会员管理、我的预约、预约确认、客服知识库
    utils/       日期金额格式化、非组件代码使用的 message / modal
```

## 六、业务流程

1. **注册 / 登录 / 登出**：注册默认会员用户，密码 PBKDF2 加盐存储，登录签发 Token 并持久化到 localStorage
2. **权限控制**：前端路由守卫按角色控制页面与菜单，后端接口校验 Token 与角色（`admin` / `user`）
3. **会议空间管理**：管理员维护空间（城市、地址、星级、会议室数、使用开始使用结束时间、营业状态）；会员以卡片浏览可预约空间
4. **会议室类型管理**：管理员维护会议室类型（编号、床型、价格、可住人数、会议室余量、状态：可预约 / 维护中 / 停售）
5. **会员管理**：管理员查询、新增、编辑、启停、重置密码、删除会员（删除时同步清理其预约）
6. **预约下单**：选择空间、使用开始与使用结束日期、会议室类型、间数与人数，填写特殊要求；系统实时显示剩余会议室余量并计算总价
7. **库存与超卖控制**：预约按 [使用开始日期, 使用结束日期) 占用会议室余量，同一会议室类型的待确认与已确认预约合并计算；剩余不足时拒绝下单
8. **预约确认**：管理员按状态 / 会议空间 / 使用开始日期 / 会员筛选，确认或拒绝并填写意见（仅「待确认」可操作，确认时再次校验库存）；列表默认展示全部预约，待确认优先排序，已确认 / 已完成 / 已拒绝等历史预约同样可见
9. **取消与状态流转**：会员可取消本人的待确认 / 已确认预约，管理员可代取消或删除；使用结束日期已过的已确认预约自动标记为已完成
10. **经营看板**：首页展示空间数、会议室类型数、会员数、待确认预约、今日使用开始、今日使用开始率，以及本周空间预约排行与最近预约（会员仅统计本人预约）
11. **个人中心**：修改个人信息与密码（改密后自动退出登录）

## 七、客服助手（Agent）

助手以右下角悬浮按钮的形式出现在所有登录后的页面。

### 1. 两种运行模式

| 模式 | 触发条件 | 回答来源 |
| --- | --- | --- |
| 大模型模式 | 配置了 `LLM_API_KEY`（或环境变量 `DEEPSEEK_API_KEY` / `OPENAI_API_KEY`） | 大模型 + 工具调用，实时读取数据库 |
| 本地知识库模式 | 未配置密钥、`AGENT_PROVIDER=local`，或大模型调用失败 | 知识库检索 + 规则引擎，自动降级 |

大模型调用失败（网络不通、额度不足、超时等）时不会向用户报错，而是自动降级到本地知识库，并在回答下方提示「回答来自本地知识库」。

### 2. 可调用的工具（均受权限约束）

| 工具 | 作用 | 权限 |
| --- | --- | --- |
| `search_knowledge` | 检索客服知识库（使用开始使用结束、押金发票、取消政策等） | 所有登录用户 |
| `list_venues` | 查询空间城市、地址、星级、会议室类型数量与营业状态 | 所有登录用户 |
| `check_room_availability` | 查询某空间某日期区间的会议室类型价格与剩余会议室余量 | 所有登录用户 |
| `list_my_reservations` | 查询自己的预约与状态 | 所有登录用户 |
| `list_pending_reservations` | 查询待确认预约列表 | 仅管理员 |
| `system_statistics` | 经营统计（会员仅统计本人预约） | 所有登录用户（数据范围不同） |
| `reservation_rules` | 返回预约规则（使用开始使用结束时间、会议室余量、人数、取消政策） | 所有登录用户 |
| `prepare_reservation` | 解析需求并生成预约预览草稿（不写库） | 所有登录用户 |

### 3. 自然语言预约（写操作）

客人可以直接用一句话让助手准备预约，例如：

> 帮我订下周五使用开始两晚的杭州西湖智选假日会议空间高级大床房，2 个人，需要安静楼层
>
> 下周三使用开始，住 3 晚，上海外滩云舍会议空间江景双床房，2 位客人
>
> 9 月 24 号使用开始、26 号使用结束，三亚亚龙湾海景度假会议空间海景大床房，2 人

流程为「解析 → 预览卡片 → 用户确认 → 创建预约」：

1. 解析空间（支持简称，「成都宽窄巷子花园会议空间」→「宽窄巷子花园」）、会议室类型（大床房 / 双床房 / 家庭房）、使用开始日期（今天/明天/下周五/9 月 24 号）、晚数（住两晚）、间数（两间）、人数（2 个人 / 2 位客人）与特殊要求
2. 生成**预约预览卡片**，包含完整要素、会议室余量与总价校验结果，**此时不写入数据库**
3. 用户点击卡片上的「确认下单」才真正创建预约，状态为「待确认」；点「不用了」则作废
4. 信息不全或会议室余量不足时，卡片列出具体原因（如「2026-09-25 至 2026-09-27 期间该会议室类型仅剩 2 间可订」）

安全设计：

- 未经用户确认不会产生任何预约记录
- 确认时以**服务端存储的草稿**为准（前端只传会话与消息 ID），并再次执行与页面下单完全相同的库存与价格校验
- 同一条草稿只能确认一次，重复确认返回「该操作已经处理过了」
- 工具调用与写操作都受当前登录用户权限约束，助手不能替他人下单
- 大模型只负责理解与组织语言，决定「能不能订」的是后端规则引擎

相关实现：`app/agent/reservation.py`（口语解析与草稿）、`app/services/reservation_service.py`（页面与助手共用的库存/价格校验）、`app/api/routers/agent.py`（确认 / 取消接口）、`frontend/src/components/AgentChat.tsx`（确认卡片）。

### 4. 知识库维护

管理员可在「客服知识库」页面维护问答条目（分类、问题、答案、关键词、启停），系统预置 20 条常见问题（预约流程、会议室类型会议室余量、支付发票、使用开始须知、账号问题、管理员指南等）。

- 关键词（逗号分隔）用于提升本地模式的命中率，建议填写客人常用的口语化说法
- 条目修改后立即生效，无需重启服务；停用后不再被检索，但保留在列表中
- 会话记录保存在 `chat_session` / `chat_message` 表，用户可在对话窗口的「历史」中继续之前的对话

### 5. 自检脚本

```powershell
cd backend

# 端到端问答（含自然语言预约草稿），分别以会员与管理员身份提问
.\.venv\Scripts\python.exe scripts\agent_smoke_test.py

# 强制使用本地知识库引擎
$env:AGENT_PROVIDER='local'; .\.venv\Scripts\python.exe scripts\agent_smoke_test.py

# 自然语言预约解析自检（空间 / 会议室类型 / 日期 / 晚数 / 间数 / 人数 / 特殊要求）
.\.venv\Scripts\python.exe scripts\reservation_parser_check.py
```

## 八、关键设计取舍

- **为什么不让大模型直接下单**：预约涉及空间、会议室类型、日期区间、间数与人数，模型误判一次就会产生脏数据。因此拆成「草稿 → 确认 → 写库」两段，模型只做理解，落库由确定性代码完成
- **库存与超卖**：以预约区间 [使用开始, 使用结束) 汇总同会议室类型的在途间数，剩余会议室余量不足直接拒单；确认预约时再次校验，避免管理员确认阶段超卖
- **为什么把校验抽成 service**：页面下单与 AI 下单复用同一入口，保证 AI 无法绕过会议室余量、人数、日期与价格规则
- **为什么自研签名 Token**：面向单机部署，用标准库实现 HMAC-SHA256 与 PBKDF2，避免引入额外依赖；生产环境应补充 refresh token、限流与失败锁定
- **为什么保留本地知识库引擎**：外部模型不可控（网络、额度、耗时），本地引擎保证助手在离线或异常时仍可用，同时为中文口语解析提供确定性兜底

## 九、主要接口

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| POST | `/api/auth/register` | 注册 | 公开 |
| POST | `/api/auth/login` | 登录 | 公开 |
| GET/PUT | `/api/auth/me` | 当前用户信息 / 修改资料 | 登录 |
| PUT | `/api/auth/password` | 修改本人密码 | 登录 |
| GET | `/api/venues` | 会议空间列表 | 登录 |
| GET | `/api/venues/{id}/availability` | 指定日期区间的会议室类型价格与剩余会议室余量 | 登录 |
| POST/PUT/DELETE | `/api/venues`、`/api/venues/{id}` | 会议空间维护 | 管理员 |
| GET | `/api/meeting-rooms`、`/api/meeting-rooms/all` | 会议室类型分页 / 全量列表 | 登录 |
| POST/PUT/DELETE | `/api/meeting-rooms`、`/api/meeting-rooms/{id}` | 会议室类型维护 | 管理员 |
| GET/POST/PUT/DELETE | `/api/users`、`/api/users/{id}` | 会员管理 | 管理员 |
| PUT | `/api/users/{id}/password` | 重置会员密码 | 管理员 |
| POST | `/api/reservations` | 提交预约（含库存校验与总价计算） | 登录 |
| GET | `/api/reservations/my` | 我的预约 | 登录 |
| GET | `/api/reservations` | 全部预约（可筛选） | 管理员 |
| POST | `/api/reservations/{id}/review` | 确认 / 拒绝预约 | 管理员 |
| POST | `/api/reservations/{id}/cancel` | 取消预约 | 本人 / 管理员 |
| DELETE | `/api/reservations/{id}` | 删除预约 | 管理员 |
| GET | `/api/stats/overview` | 经营看板（含使用开始率与空间排行） | 登录 |
| POST | `/api/agent/chat` | 向客服助手提问（自动创建 / 续接会话） | 登录 |
| POST | `/api/agent/actions/confirm` | 确认预约草稿并创建预约 | 登录（仅本人草稿） |
| POST | `/api/agent/actions/cancel` | 放弃预约草稿 | 登录（仅本人草稿） |
| GET | `/api/agent/status` | 助手运行模式、模型、知识库数量 | 登录 |
| GET | `/api/agent/faq` | 推荐问题 | 登录 |
| GET/DELETE | `/api/agent/sessions`、`/api/agent/sessions/{id}` | 会话列表 / 删除会话 | 登录（仅本人） |
| GET | `/api/agent/sessions/{id}/messages` | 会话消息记录 | 登录（仅本人） |
| GET/POST/PUT/DELETE | `/api/knowledge`、`/api/knowledge/{id}` | 知识库查询与维护 | 查询：登录；维护：管理员 |

## 十、后续规划

- 助手确认卡片支持「修改后再确认」（当前需重新描述一次需求）
- 在线支付与预约金额结算、发票申请
- 使用开始签到 / 超时未到自动释放会议室余量、会员等级与积分
- 消息通知（短信 / 邮件）与使用开始提醒
- 库存写入加行锁 / 乐观锁与唯一约束，把防超卖从业务层下沉到数据库层
- Docker Compose 一键部署、GitHub Actions 持续集成（pytest 已覆盖核心链路，见「快速开始 · 6」）
- 知识库检索升级为向量检索，并建立 Agent 评测集做回归

## 十一、开源许可

本项目基于 [MIT License](LICENSE) 开源。
