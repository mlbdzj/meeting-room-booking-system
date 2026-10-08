# 智能会议室预约系统 · 面试准备手册

> 用途：把本项目写到简历后，按「面试官会怎么问」系统复习。
> 定位：**AI Agent 编排**是第一卖点，**库存/防超卖**是第二，**全栈完整度**是第三。

---

## 零、一句话定位

> 一个基于 Agent 的会议室预约系统：FastAPI + SQLAlchemy + MySQL 后端，React 19 + TypeScript + Vite 前端，内置支持 function calling 的 AI 客服助手，覆盖会议空间/会议室类型维护、按天预约、库存防超卖、预约确认与经营看板的完整闭环。

⚠️ **务必提前说明**：Agent 是**手写的 function calling 编排**，不是 LangChain / LangGraph。手写不是缺点，但要能讲清原理；否则一问框架细节就露馅。

---

## 一、必背：90 秒项目自述（STAR）

- **背景**：会议室预约系统，需要同时服务「页面下单」和「自然语言下单」，并保证两者都不会超卖、不会写脏数据。
- **技术栈**：FastAPI + SQLAlchemy + MySQL；React 19 + TS + Vite + antd + zustand；Agent 走 OpenAI 兼容接口的 function calling。
- **我的核心工作**：
  1. 设计「大模型工具调用 + 本地知识库降级」的**双引擎 Agent**；
  2. 设计「口语解析 → 预览草稿 → 用户确认 → 确定性落库」的**两段式下单**；
  3. 抽取 `reservation_service` 让页面与 AI **复用同一套库存校验**；
  4. 实现按日期区间重叠汇总的**库存防超卖**与预约状态机。
- **结果**：8 个受权限约束的工具、20 条知识库、100 个 pytest 用例覆盖核心链路；大模型不可用时自动降级，功能不中断。

---

## 二、Agent 专题（最高频，按由浅入深准备）

总入口：`backend/app/agent/engine.py` 的 `answer_question`；工具层 `tools.py`；LLM 客户端 `llm.py`；本地知识库 `knowledge.py`；口语解析 `reservation.py`。

| 问题 | 回答要点 |
|---|---|
| Agent 编排怎么做的？ | 双引擎：有模型走 `_llm_answer` 的**多轮工具调用循环**，失败/返回空则降级 `local_answer` 规则引擎。 |
| function calling 完整流程？ | 组装 `[system] + 最近 6 条历史 + 用户问题` → 调 `/chat/completions`（`tool_choice=auto`）→ 模型返回 `tool_calls` → 校验参数并执行 → 结果以 `role=tool` 回灌 → 下一轮，直到模型给出文本。 |
| 工具怎么定义/注册？ | `TOOL_REGISTRY` 字典集中管理：描述 + Pydantic 入参模型 + handler；发给模型的 JSON Schema 由 Pydantic **自动生成**，并去掉冗余 `title` 省 token。 |
| 模型乱传参数怎么办？ | 入参模型 `extra="ignore"`；校验失败**不抛异常**，把错误当工具结果回传给模型让它自我修正。 |
| 怎么防死循环/失控？ | `AGENT_MAX_TOOL_ROUNDS=5`；历史只取最近 6 条；`temperature=0.3`。 |
| 怎么防 AI 瞎编？ | 提示词强制「实时数据必须先调工具」；更关键的是**工具是唯一数据入口**。 |
| 怎么防 AI 越权？ | 权限内建在工具里：`list_pending_reservations` 校验 admin；`system_statistics` 按角色限范围；`list_my_reservations` 只查本人。 |
| 为什么不让模型直接下单？ | 预约涉及空间/会议室类型/日期区间/间数/人数，误判一次就是脏数据 → 两段式：模型只「理解」，落库由确定性代码完成。 |
| 「不写库」怎么实现？ | `prepare_reservation` 只调 `build_draft()` 生成草稿（含 problems 校验），前端渲染确认卡；点确认才走 `/api/agent/actions/confirm` 建单。 |
| 确认时怎么防重复/防篡改？ | 草稿 JSON 存在**服务端** `chat_message.action`，前端只传 session_id + message_id；状态 `pending → confirmed`，重复确认报「该操作已经处理过了」。 |
| AI 与页面校验一致吗？ | 完全一致，都走 `reservation_service.validate_reservation`；这是刻意设计，**AI 无法绕过业务规则**。 |
| 大模型挂了怎么办？ | 异常统一包成 `LLMError`，捕获后降级 `local_answer`，回答标注 `local-fallback`，前端显示「来自本地知识库」。 |
| 本地引擎怎么识别意图？ | 关键词表 + 正则；`_is_reservation_intent` 区分订房与查询（带「吗/多少钱」算查询）。 |
| 中文口语怎么解析？ | `detect_date` 支持今天/明天/下周五/9月24号/ISO；`cn_to_int` 支持中文数字；正则抽取晚数/间数/人数；`match_venue` 做简称消歧。 |
| 知识库检索算法？ | 字符 bigram 相似度 + 关键词命中 + 分类加权，`score`/`similarity` 双阈值。**未用向量库**（见软肋）。 |
| 多轮/上下文怎么存？ | `chat_session` / `chat_message` 表，取最近 6 条历史；action 草稿持久化，跨会话可继续。 |
| 防 Prompt 注入吗？ | 靠角色约束 + 工具权限兜底（被注入也拿不到越权数据、写操作要用户确认）；**如实承认**没有专门注入检测。 |
| token/延迟怎么优化？ | 限轮数、截断历史、schema 去 title、低温度；**无流式输出**（可扩展）。 |

### 2.1 可直接背诵的问答稿（第一人称口语版）

**Q1：介绍一下你的 Agent 是怎么编排的？**
> 我的 Agent 是一个「单 Agent + function calling」的编排，没有用框架。总入口是 `answer_question`，它做两件事：优先走大模型，失败就降级到本地引擎。大模型这条链路是一个多轮工具调用循环：先把系统提示词、最近 6 条对话历史和用户问题组装成 messages，带着 8 个工具的 schema 去调 `chat/completions`；模型如果返回 `tool_calls`，我就校验参数、执行工具、把结果以 `tool` 角色回灌，再进入下一轮，直到模型不再调工具、给出自然语言回答。为了避免死循环，我限制了最多 5 轮。

**Q2：工具是怎么定义和注册的？**
> 我用一个 `TOOL_REGISTRY` 字典集中管理所有工具，每个工具由三部分组成：给模型看的描述、一个 Pydantic 入参模型、一个 handler。发给模型的 JSON Schema 由 Pydantic 根据入参模型自动生成，我还特意把自动补的 `title` 字段去掉省 token。这样新增工具只要在注册表加一条，schema 和参数校验都是自动的。

**Q3：模型传的参数不合法怎么办？**
> 我的原则是：校验失败不要抛异常、不要中断对话，而是把错误当成工具结果回传给模型。入参模型设 `extra=ignore` 容忍多余字段，用 `model_validate` 校验，捕获校验异常后返回 `{"error": "参数不合法：…"}`。模型拿到之后通常会自己修正参数重试。

**Q4：怎么防止模型编造价格、会议室余量这些数据？**
> 两层。第一层，系统提示词明确要求涉及实时数据必须先调工具、禁止凭记忆回答；第二层也是更关键的——工具是唯一的数据入口，工具直接查数据库，模型不调工具根本拿不到数据，也就编不出真实数字。

**Q5：怎么防止 AI 越权，比如普通用户问到别人的预约或经营数据？**
> 权限是内建在工具里的，不依赖提示词。比如查待确认预约的工具会判断当前用户是不是 admin，不是就返回权限说明；经营统计按角色决定统计范围，普通用户只能看到自己的预约；查预约也只查当前登录用户的。即使模型被诱导去调用，工具层也不会返回越权数据。

**Q6：为什么不让大模型直接下单、直接写库？**
> 因为下单涉及空间、会议室类型、日期区间、间数和人数，模型只要有一个字段理解错就会产生脏数据。所以我拆成了两段式：模型只负责「理解」，把用户那句话解析成预约草稿；真正落库是点「确认下单」之后，由确定性代码——也就是复用页面下单那套校验和创建逻辑——完成的。模型永远不直接写库。

**Q7：「不写库」具体怎么实现？用户确认前草稿存在哪？**
> 生成草稿的 `prepare_reservation` 工具只调用 `build_draft`，做解析和校验、算出总价和缺失项，但不 `db.add`、不 commit。草稿会作为 JSON 存到那条助手消息的 `action` 字段里，前端把它渲染成一张预约确认卡。

**Q8：用户点确认后，怎么保证不被篡改、也不会重复下单？**
> 确认接口只接收 session_id 和 message_id，草稿以**服务端存储的为准**，前端传不了金额和会议室类型。确认时再次执行和页面完全一样的库存、人数、日期校验；然后把状态从 `pending` 改成 `confirmed`；同一条草稿再点一次，会因为状态不是 `pending` 而返回「该操作已经处理过了」。所以既防篡改，也防重复。

**Q9：大模型调用失败或超时怎么办？**
> 我把超时、连接失败、接口报错统一包装成 `LLMError`，在最外层捕获。捕获后不向用户报错，而是降级到本地知识库引擎，回答标注来源是 `local-fallback`，前端提示「来自本地知识库」。这样即使断网或额度用完，助手依然可用。

**Q10：本地引擎没有大模型，怎么理解问题？**
> 本地引擎是「关键词 + 规则」的意图识别。我维护了几组关键词——订房意图、会议室状态查询、我的预约、规则咨询等，配合正则匹配；日期和数字单独解析，比如「明天」「下周五」「9 月 24 号」「两晚」「三个人」。还特意区分了订房和查询：带「吗」「多少钱」的疑问句算查询，不会误触发下单。

**Q11：知识库检索怎么做的？为什么不用向量数据库？**
> 我用的是纯字符级 bigram 相似度，加上关键词命中、问题包含、分类命中做加权，用两个阈值分别判断「是不是同一个问题」和「够不够相关」。不用向量库是我的取舍：这是中文短问题的知识库，只有 20 条左右，字符相似度零依赖、够用、还可解释。如果知识库规模上来、表达更发散，我会升级成 embedding 向量检索。

**Q12：对话历史怎么管理？会不会无限增长？**
> 会话和消息存两张表，`chat_session` 和 `chat_message`。每次请求我只取最近 6 条历史拼进上下文，避免 token 无限增长。草稿的 action 持久化在消息里，所以同一个会话继续聊也能接着确认之前那张卡。

**Q13（挑战）：你为什么不直接用 LangChain？**
> 见 2.2，直接背最后的收尾话术。

### 2.2 手写 function calling vs LangChain / LangGraph

**一句话结论**：8 个工具、单 Agent、规则边界清晰 —— **手写更合适**；一旦走向多 Agent、复杂分支、断点续跑、可观测，就该上 **LangGraph**。

| 维度 | 手写（本项目） | LangChain / LangGraph |
|---|---|---|
| 依赖体量 | 只依赖 `openai` SDK | 抽象层多、依赖重 |
| 工具定义 | Pydantic 模型 + 注册表，schema 自动生成 | `@tool` / `StructuredTool`，schema 自动生成 |
| 循环控制 | 自己写 `for` + 轮数上限，完全可控 | `AgentExecutor` / `create_tool_calling_agent` 内置循环 |
| 参数校验纠错 | Pydantic 校验，错误回传模型 | 有解析器，异常处理不如手写直观 |
| 提示词/记忆 | 自己拼 system、截取最近 N 条 | `ChatPromptTemplate` + 各种 Memory 组件 |
| 可观测 | 打日志、存库 | LangSmith 内置追踪（生态强） |
| 调试 | 全链路是自己代码，好断点 | 抽象可能泄漏，要读框架源码 |
| 复杂控制流 | 多 Agent / 分支要自己写 | LangGraph 原生支持图、条件边、checkpointer、`interrupt` |
| 版本风险 | 无 | 迭代快、API 变动多 |

**手写的优点（背这几条）**：
1. **完全可控**：每一轮、每个 token 的去向都清楚，方便按业务加约束。
2. **依赖少**：只装 `openai`，部署轻、无升级焦虑。
3. **可调试**：出问题直接断点，不用读框架源码。
4. **校验/权限内建**：对业务系统最关键，框架反而要额外绕。
5. **测试友好**：本地引擎和工具都是纯函数，好写单测。

**框架的优点**：
1. 抽象齐全、开发快（memory、streaming、retry、tracing）。
2. 生态强（LangSmith、社区集成多）。
3. **LangGraph** 对多 Agent、条件分支、状态机、人工介入（`interrupt`）、checkpoint 断点续跑是降维打击。
4. 适合复杂、长流程。

**什么时候该换框架（说出这个 = 成熟）**：
- 工具数量 > 20，或需要动态加载多个 toolkit；
- 多 Agent 协作 / 角色分工；
- 需要长时间、可中断、可恢复的流程（human-in-the-loop）；
- 需要分支、并行、循环等复杂控制流；
- 需要完整的 tracing / eval 体系。

**如果要迁移到 LangGraph，我会怎么做**：
- 每个工具包成 `ToolNode`；
- 把「意图判断 → 查数据 → 出草稿 → 等用户确认」建成 StateGraph 的节点与条件边；
- 用 checkpointer 持久化会话状态，替代现在手动存 `action`；
- 用 `interrupt()` 实现「确认下单」的人工介入，天然支持暂停/恢复；
- **保留 `reservation_service` 作为工具内部实现，业务规则完全不变**。

**收尾话术（可直接背）**：
> 我选型的原则是「用最少的抽象满足需求」。这个项目是单 Agent、工具边界清晰、业务规则强，手写能让每一步都可控可测，也便于把权限和校验内建进去；而 LangGraph 的价值在多 Agent、复杂状态机和人工介入这些我现在用不到的能力上。所以我不是排斥框架，而是按复杂度选型——一旦需求升级到多 Agent 或长流程可恢复，我会迁到 LangGraph，并保留现有的 service 层。

---

## 三、库存与并发（第二高频，陷阱最多）

代码：`backend/app/services/reservation_service.py`。

| 问题 | 回答要点 |
|---|---|
| 怎么防超卖？ | 预约按 **[使用开始, 使用结束) 半开区间**统计重叠；汇总同会议室类型 `status ∈ (pending, confirmed)` 的间数；`剩余 = quantity - 占用`，不足拒单；确认时**二次校验**（`exclude_id` 排除自己）。 |
| 为什么 pending 也占库存？ | 避免同房多人同时提交；取消/拒绝后离开 `ACTIVE_STATUS`，库存自动释放。 |
| ⚠️ 并发下安全吗？ | **不安全**。查询-插入非原子，两个请求可能都读到「剩 1 间」然后都插入。**主动承认**：要加数据库行锁（`SELECT ... FOR UPDATE`）/ 乐观锁 + 唯一约束，或 Redis 预扣。 |
| 总价怎么算？改价影响历史预约吗？ | 下单时 `price × 晚数 × 间数` 存快照；用 `Decimal` 保精度；历史预约不受改价影响。 |
| 区间重叠为什么用 `<` / `>`？ | 使用结束当天不算占用：`check_in < 使用结束 且 check_out > 使用开始`。 |

---

## 四、预约状态机与业务规则

- **流转**：`pending → confirmed / rejected / canceled`；`confirmed → canceled / completed`。仅「待确认」可 review；仅「待确认/已确认」可取消。
- **自动完成**：`refresh_completed_status` 把「已确认且使用结束日已过」的预约标记为 `completed`。
- **被追问的坑**：为什么放在 GET 里更新？→ 实现简单，但**依赖被读取才触发**、属副作用，规范做法是定时任务/事件。
- **使用开始率**：`今日在住间数 / 全部会议室余量`。⚠️ 分母是全体会议室类型总量、跨空间汇总，属「空间整体出租率」的简化口径，要能解释。

---

## 五、认证与权限

代码：`backend/app/core/security.py`、`backend/app/api/deps.py`。

- **JWT 自研**：标准库实现 `HMAC-SHA256` 签名，token = `base64(payload).base64(signature)`；密码 `PBKDF2-SHA256`（12 万次迭代）+ 随机盐。
- **不足（主动说）**：无 refresh token、不能主动失效（登出仅前端清 localStorage）、无限流、无失败锁定、`SECRET_KEY` 默认值需替换。
- **权限**：后端 `get_current_user` / `require_admin` 依赖注入；前端 `Protected` 只是体验层，真正校验在后端。
- **加分**：`get_current_user` 每次从数据库重新加载 user，**不信任 token 里的 role**；被禁用用户直接 403。

---

## 六、数据库与性能

- **索引**：`venue_id / meeting_room_id / user_id / start_at / end_at / status`。
- **N+1**：预约序列化时批量查 venue / meeting_room / user 名称（`_serialize`）。
- **金额**：`Numeric(10,2)` 存库（模型注解写 `float` 是标注瑕疵，实际 Decimal）。
- **分页**：SQL `offset/limit`；预约列表用 `case` 让「待确认」优先。
- **可被追问**：深分页慢（可换游标）；`like %x%` 用不上索引。

---

## 七、前端

- **栈**：React 19 + TS + Vite + antd 5 + zustand + react-router 7。
- **请求封装**：自封 `fetch`（非 axios）；统一加 Bearer、统一解析 `detail`、401 自动清态跳登录、`silent` 让调用方自己提示。
- **状态管理**：zustand 只存 `{token, user}`，持久化 localStorage，刷新保持登录。
- **路由**：`Protected` / `PublicOnly` + `React.lazy` + `Suspense` 按页分包。
- **Agent 交互**：悬浮按钮 + Drawer；确认卡按 `status` 渲染；会话 404 自动开新会话重试。

---

## 八、测试与工程化

- **pytest 用例**：`test_reservation_service` / `test_reservation_api` / `test_permissions` / `test_agent_reservation` / `test_user_management`，共 100 个。
- **测试隔离（重点讲）**：默认内存 SQLite；`INIT_DB_ON_STARTUP=false` 不碰开发库；`AGENT_PROVIDER=local` 不调外部模型保证可复现；**每个用例跑在一条外层事务里、结束回滚**；可切 `TEST_DATABASE_URL` 对真实 MySQL。
- **自检脚本**：`agent_smoke_test.py`、`reservation_parser_check.py`。

---

## 九、主动承认的软肋（说出来 = 有工程判断力）

1. **并发超卖**：业务层校验非原子 → 要加行锁/乐观锁/Redis。
2. **知识库是 bigram 不是向量/RAG**：中文短问题够用、零依赖；升级方向是向量检索 + 评测集。
3. **自研 Token 短板**：无刷新/失效/限流。
4. **Agent 无流式、无评测集、防注入弱**。
5. **`refresh_completed_status` 副作用放在 GET**。
6. **CORS 默认 `*` 且允许凭证**：生产要收紧到白名单。

---

## 十、加分点

- **两段式下单**：模型理解与确定性落库解耦，可靠性设计典范。
- **校验复用**：页面与 AI 共用 `reservation_service`，从架构上杜绝绕过规则。
- **双引擎降级**：可用性设计。
- **测试事务回滚隔离**：体现测试工程能力。
- **问题解决案例（可主动讲）**：会员删除接口原本用 `selectinload(Reservation.meeting_rooms)` / `reservation.meeting_rooms = []`，但 `Reservation` 只有 `meeting_room`（多对一），现场删除会员会 `AttributeError`；且 `chat_session.user_id`、`reservation.reviewer_id` 外键会阻塞删除。已修复为：级联删除该用户预约、删除其对话（消息随会话级联）、把其作为审核人的 `reviewer_id` 置空，并补充 `tests/test_user_management.py` 回归测试。
- **优化路线**（被问「怎么改进」时答）：库存下沉 DB、Agent 流式 + 评测集、知识库向量化、Docker/CI、支付与通知。

---

## 十一、反问面试官

- 团队的 Agent 是自研编排还是用框架？有没有评测/回归机制？
- 库存一致性在应用层还是数据库层解决？有没有用 Redis？
- 对 AI 生成内容的可靠性有没有兜底或人工审核策略？

---

## 十二、针对性手撕题（现场编码）

> 面试官常从项目里「抠一个小函数」让你白板实现。下面按命中概率排序。
> **通用节奏**：先讲思路 → 再写代码 → 最后补复杂度和边界。

### 12.1 手写 function calling 多轮工具循环（最高频）

考察点：你是真的懂循环与消息结构，还是只会调 API。

```python
import json

def run_agent(messages, tools, execute_tool, max_rounds=5):
    """execute_tool(name, args) -> dict；出错也要返回 {"error": ...} 而不是抛异常。"""
    for _ in range(max_rounds):
        message = chat_completion(messages, tools)          # {"content", "tool_calls"}
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            return (message.get("content") or "").strip()   # 模型给出最终回答

        # assistant 的 tool_calls 必须原样回灌
        messages.append({"role": "assistant",
                         "content": message.get("content") or "",
                         "tool_calls": tool_calls})
        for call in tool_calls:
            fn = call["function"]
            args = json.loads(fn.get("arguments") or "{}")
            result = execute_tool(fn["name"], args)
            # tool 消息必须带 tool_call_id，与上面某个 tool_call 一一对应
            messages.append({"role": "tool",
                             "tool_call_id": call["id"],
                             "content": json.dumps(result, ensure_ascii=False)})
    return None   # 轮数用尽 → 上层降级到本地引擎
```

追问：为什么 `tool` 消息必须带 `tool_call_id`？→ 接口要求 assistant 的每个 `tool_call` 都有对应的结果，缺了会报错或对不上号。

### 12.2 判断两个使用开始区间是否重叠（送分题）

```python
def overlaps(a_in, a_out, b_in, b_out):
    return a_in < b_out and a_out > b_in   # 半开区间 [使用开始, 使用结束)
```

追问：为什么用半开区间？→ 使用结束当天不算占用；若写成 `<=`，当天退当天住会误判为叠加。

### 12.3 计算某会议室类型某区间的剩余会议室余量（对应项目核心 SQL）

```sql
SELECT COALESCE(SUM(rooms), 0)
FROM reservation
WHERE meeting_room_id = :rt
  AND status IN ('pending', 'confirmed')   -- 在途状态占用库存
  AND start_at  < :check_out
  AND end_at > :check_in;
-- remaining = meeting_room.quantity - occupied
```

### 12.4 并发占用峰值 / 最少房间数（会议室 II 变体，超高频）

题目：给一批 `[使用开始, 使用结束)` 区间，同一会议室类型同时最多被占用几间？（用来判断是否超 `quantity`）

```python
def peak_rooms(intervals):
    events = []
    for cin, cout in intervals:
        events.append((cin, +1))    # 使用开始 +1
        events.append((cout, -1))   # 使用结束 -1
    # 同一天：使用结束(-1) 排在使用开始(+1) 前，符合半开区间「当天退可当天住」
    events.sort(key=lambda e: (e[0], e[1]))
    cur = peak = 0
    for _, delta in events:
        cur += delta
        peak = max(peak, cur)
    return peak
```

也可用最小堆：按使用开始排序，使用结束早的弹出，堆大小即当前占用。
复杂度 `O(n log n)`。
追问：怎么判断「这次能不能订」？→ `当前占用 + 本次 rooms <= quantity`。

### 12.5 手写中文口语日期解析（项目亮点小函数）

```python
import re
from datetime import date, timedelta

def detect_date(text):
    today = date.today()
    for word, off in {"今天": 0, "明天": 1, "后天": 2}.items():
        if word in text:
            return today + timedelta(days=off)

    m = re.search(r"(\d{1,2})\s*[月/-]\s*(\d{1,2})", text)   # 9月24号 / 9-24
    if m:
        return date(today.year, int(m.group(1)), int(m.group(2)))

    m = re.search(r"(下周|本周|周|星期)([一二三四五六日天])", text)
    if m:
        target = "一二三四五六日".find(m.group(2).replace("天", "日"))
        if m.group(1).startswith("下"):
            next_monday = today + timedelta(days=7 - today.weekday())
            return next_monday + timedelta(days=target)
        return today + timedelta(days=(target - today.weekday()) % 7 or 7)
    return None
```

追问：跨年怎么办？→ 用 `check_in.year` 推断，若算出的日期已过则加一年。

### 12.6 手写 HMAC 签名 Token（对应自研 JWT）

```python
import base64, hashlib, hmac, json, time

def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")

def create_token(user_id, secret, ttl=7 * 24 * 3600):
    body = _b64(json.dumps({"sub": str(user_id), "exp": int(time.time()) + ttl}).encode())
    sig = _b64(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"

def verify_token(token, secret):
    body, sig = token.split(".")
    expected = _b64(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):     # 防时序攻击
        raise ValueError("签名无效")
    payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    if payload["exp"] < time.time():
        raise ValueError("已过期")
    return payload
```

追问：为什么用 `hmac.compare_digest` 而不是 `==`？→ 定长比较，防时序侧信道攻击。

### 12.7 预约状态机（写一个流转校验）

```python
ALLOWED = {
    "pending":   {"confirmed", "rejected", "canceled"},
    "confirmed": {"canceled", "completed"},
    "rejected":  set(),
    "canceled":  set(),
    "completed": set(),
}

def can_transition(src, dst):
    return dst in ALLOWED.get(src, set())
```

追问：为什么确认时还要二次校验库存？→ 从下单到确认之间，可能有别的预约占用了同一间房。

### 12.8 防超卖（开放题，重思路）

四种主流方案，被问就按需递进：

1. **悲观锁**：`SELECT ... FOR UPDATE` 锁住会议室类型行，检查剩余再插入，事务提交释放。
2. **乐观锁**：会议室类型加 `version` 字段，`UPDATE ... WHERE version = ?`，失败重试。
3. **库存行 + 条件更新**（推荐）：按 `(meeting_room, date)` 建库存行，
   `UPDATE inventory SET available = available - :n WHERE meeting_room_id=:rt AND date=:d AND available >= :n`，
   靠数据库原子判断影响行数是否为 1 来决定成败。
4. **Redis 预扣**：下单前 `DECRBY`，取消回补；再异步落库，注意最终一致。

**必答的一句**：本项目目前只有**业务层校验、非原子**，高并发下会超卖，升级方向就是上面第 3 种（把校验下沉到数据库）。

### 12.9 白板注意事项（收尾加分）

- **边界**：相同日期、跨月跨年、空区间、`quantity = 0`、`rooms > remaining`。
- **口径**：半开区间是纠结点，主动说清「使用结束当天不占房」。
- **复杂度**：区间题一般是 `O(n log n)`（排序）或 `O(n)`（哈希/扫描）。
- **别急着写**：先复述题意、给例子、说思路，面试官点头再落笔。

---

## 十三、项目相关八股速查

> 只列与本项目强相关、且高频的八股。答法都尽量往项目上靠。

### 13.1 FastAPI / Python

| 问题 | 要点 |
|---|---|
| FastAPI 的依赖注入怎么工作？ | `Depends` 在请求进入时解析依赖图；`get_db` 是生成器依赖，请求结束在 `finally` 里 `close()`，保证会话释放。 |
| 同步 `def` 和 `async def` 端点有什么区别？ | FastAPI 把同步 `def` 端点丢到**线程池**执行，阻塞的 DB 调用不会卡事件循环；`async def` 里做阻塞操作会卡死循环。本项目是同步端点 + 同步 SQLAlchemy，所以不卡。 |
| Pydantic v2 常用能力？ | `model_validate` 校验/转换、`model_json_schema()` 生成 JSON Schema（Agent 的工具 schema 就用它）、`from_attributes=True` 直接读 ORM 对象。业务上用 `extra="ignore"` 容错。 |
| lifespan 是什么？ | 应用启动/关闭钩子；项目在 lifespan 里做 `init_database()`，比 `on_event` 更规范。 |
| 为什么用 ORM 不用原生 SQL？ | 类型安全、可组合、抗注入；代价是复杂查询/性能有时不如手写 SQL。 |

### 13.2 HTTP / REST

| 问题 | 要点 |
|---|---|
| 401 和 403 的区别？ | 401 = **未认证**（没带/带了坏 token）；403 = **已认证但无权限**（如普通用户访问 `require_admin`、账号被禁用）。项目严格区分。 |
| 201 / 400 / 404 / 422 用在哪？ | 201 创建成功（注册、建单）；400 业务校验失败；404 资源不存在；422 框架参数校验失败（项目自定义 handler 把 `msg` 转成中文 `detail`）。 |
| CORS 预检是什么？ | 跨域非简单请求先发 `OPTIONS` 预检。⚠️ `allow_origins=["*"]` 且 `allow_credentials=True` 是配置隐患，生产要收紧白名单。 |
| RESTful 怎么设计的？ | 资源用名词、动作用 HTTP 方法；项目里如 `POST /api/reservations/{id}/review`（确认/拒绝）、`/cancel`（取消）是「动作即子资源」的常见写法。 |

### 13.3 数据库 / 事务

| 问题 | 要点 |
|---|---|
| 事务 ACID / 隔离级别？ | MySQL 默认 RR（可重复读）。本项目下单的并发隐患属于**丢失更新 / 写偏斜**，即便 RR 也挡不住「读到剩余再插入」，需要行锁或条件更新。 |
| 索引原理？最左前缀？ | B+ 树；联合索引按最左前缀匹配。`LIKE '%关键字%'` 用不上索引（项目会员搜索就是这个，数据量大要换方案）。 |
| N+1 问题？ | 逐条查关联字段会放大查询数；项目用**批量字典**（一次性查 venue/meeting_room/user）规避。 |
| 悲观锁 vs 乐观锁？ | 悲观：`SELECT ... FOR UPDATE` 一开始就锁；乐观：`version` 字段 + 条件更新，冲突重试。防超卖见 12.8。 |
| 金额为什么用 Numeric？ | `Decimal` 精确、不丢精度；浮点 `float` 会有 0.1+0.2 问题。 |

### 13.4 安全

| 问题 | 要点 |
|---|---|
| 密码为什么要加盐 + 迭代？ | 盐防彩虹表、迭代增加暴力成本；项目用 PBKDF2-SHA256 12 万次。更现代可选 bcrypt/argon2。 |
| JWT 结构？签名还是加密？ | 标准是 `header.payload.signature`，**只签名不加密**（payload 可解码）；项目的 token 是简化版 `body.signature`，同样是签名防篡改、非保密。 |
| 为什么 `compare_digest`？ | 定长比较防**时序攻击**。 |
| token 放 localStorage 的取舍？ | 放 header 发送天然免疫 CSRF（浏览器不会自动带）；但受 **XSS** 影响（被脚本读到即泄漏）。 |
| 怎么防 SQL 注入？ | ORM 参数化查询；项目里 `like(f"%{kw}%")` 仍是参数绑定，注入安全（只是索引失效）。 |
| 权限为什么放后端？ | 前端路由守卫只是体验，**可被绕过**；真正的鉴权必须在每个后端接口（`get_current_user`/`require_admin`）。 |

### 13.5 AI / LLM

| 问题 | 要点 |
|---|---|
| function calling、RAG、Agent 区别？ | function calling = 模型输出结构化**工具调用意图**；RAG = 检索资料拼进上下文**增强生成**；Agent = 多步决策 + 调用工具 + 观察结果循环。本项目是 function calling 驱动的单 Agent，知识库检索更像关键词检索、不算严格 RAG。 |
| temperature 作用？为什么 0.3？ | 控制随机性；客服要稳定、少发挥，所以调低。 |
| 幻觉怎么缓解？ | 提示词约束 + **工具做唯一数据入口**（Grounding）+ 低温度 + 关键写操作要用户确认。 |
| embedding / 向量检索原理？ | 文本转向量，用余弦相似度找最近的；比字符 bigram 更能匹配语义，是知识库的升级方向。 |
| Prompt 注入怎么防？ | 身份与权限边界靠**代码**兜底（不等于靠提示词），写操作二次确认；进一步可加输入过滤与工具调用白名单。 |

### 13.6 前端 / 通用

| 问题 | 要点 |
|---|---|
| 受控组件是什么？ | 值由 state 驱动、`onChange` 回写；项目表单全程受控。 |
| `useEffect` 依赖数组？ | 空数组只跑一次；依赖变化才重跑；漏依赖会拿到旧值（闭包）。项目加载数据都用 `useCallback` + `useEffect`。 |
| 列表 key 为什么不用 index？ | diff 不准、状态错位；项目用数据库 `id` 作 key。 |
| 防抖 / 节流用在哪？ | 搜索框输入防抖可减少请求（项目当前是「回车/点搜索」触发，属于简化处理，可优化点）。 |
| React 19 有什么变化？ | 更推荐用 `actions`/`useTransition` 处理异步；项目用 antd 的 React 19 兼容补丁。 |

### 13.7 一句话兜底

被问到不确定的八股时，可以这样收：**「这块我在项目里的具体做法是 X，底层原理大致是 Y，如果要做深我下一步会 Z」**——把八股拉回项目，永远比空谈概念得分高。
