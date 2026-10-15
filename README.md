# AI 旅行规划助手

基于 **LangGraph** 的多工具旅行规划 Agent，带**短期 / 长期双层记忆**，配 **React 前端**。

你只要说一句「帮我规划北京三日游，2 人，预算 5000」，它就会自动：

> 回忆你的长期偏好 → 检索旅游攻略 → 规划交通路线 → 推荐沿途餐厅 → 挑选酒店 → 查天气与汇率 → 整合成一份可执行的行程

## 特性

| 能力 | 说明 |
|---|---|
| **多工具协同** | 11 个工具：攻略 / 景点 / 餐厅 / 酒店 / 交通 / 天气 / 汇率 + 4 个记忆读写工具 |
| **短期记忆** | SQLite 单文件，按 `thread_id` 隔离每个会话，自动裁剪上限 |
| **长期记忆** | Chroma 向量库，跨会话记住偏好与忌口，支持语义检索 |
| **流式输出** | SSE 逐字推送，前端有打字机效果与工具调用时间线，可随时停止生成 |
| **会话管理** | 历史会话列表、点击回放、删除 |
| **离线可用** | 嵌入模型本地加载，运行时不联网下载；模型缺失自动降级 |
| **一键启动** | `python -m travel_plan_agent`，前端由后端托管，**无需 Node.js** |

## 快速开始

### 1. 安装依赖

```powershell
pip install -r travel_plan_agent/requirements.txt
```

### 2. 配置密钥
复制 `travel_plan_agent/.env.example` ，并再此基础上，添加自己的密钥
```powershell
copy travel_plan_agent\.env.example travel_plan_agent\.env
```

编辑 `travel_plan_agent/.env`，至少填写下面几项：

| 变量 | 用途 | 申请地址 |
|---|---|---|
| `MODEL_API_KEY` | 大模型（另有 `MODEL_PROVIDER` / `MODEL_NAME` / `MODEL_API_URL`） | 通义千问 / DeepSeek / OpenAI 等 |
| `TAVILY_API_KEY` | 攻略、景点、餐厅、酒店检索 | https://tavily.com |
| `GAODE_KEY` | 交通路线规划 | https://lbs.amap.com |
| `HEFENG_KEY` + `HEFENG_HOST` | 天气预报 | https://dev.qweather.com |

> 缺少某个 Key 时，对应工具会返回一句中文提示，不会导致程序崩溃。

### 3. 下载嵌入模型（可选，约 470 MB）

```powershell
python scripts/download_model.py
# 国内网络较慢时使用镜像
python scripts/download_model.py --mirror
```

> **不下载也能跑**：找不到模型目录时，长期记忆会自动退化为哈希嵌入（功能可用，语义检索效果较弱）。

### 4. 启动

```powershell
python -m travel_plan_agent
```

浏览器打开 **http://127.0.0.1:8000** ——界面和接口都在这个地址。

## 开发模式（前后端分离）

前端支持热更新，适合改界面：

```powershell
# 终端 1：后端
uvicorn travel_plan_agent.server:app --host 127.0.0.1 --port 8000

# 终端 2：前端
cd travel-plan-web
npm install
npm run dev          # 打开 http://localhost:5173
```

改完前端后，构建进后端包内：

```powershell
npm run build:agent
```

## 切换大模型

只改 `.env`，不用动代码：

| 想用 | `MODEL_PROVIDER` | 是否要填接口地址 |
|---|---|---|
| 通义千问 | `qwen` | 否 |
| DeepSeek | `deepseek` | 否 |
| OpenAI | `openai` | 否 |
| Kimi | `moonshot` | 否 |
| 智谱 GLM | `zhipu` | 否 |
| 自建 / 专属网关 | `custom` | **是**（同时填 `MODEL_API_URL` 与 `MODEL_NAME`） |

切换时记得把 `MODEL_API_URL` 和 `MODEL_NAME` **清空**，否则会继续沿用上一家的地址。

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/health` | 健康检查（版本、模型、工具数） |
| POST | `/api/v1/chat/message` | 非流式对话 |
| POST | `/api/v1/chat/stream` | SSE 流式对话 |
| GET | `/api/v1/chat/sessions` | 会话列表 |
| GET | `/api/v1/chat/history` | 某会话的历史消息 |
| DELETE | `/api/v1/chat/session/{id}` | 删除会话 |

交互式接口文档：http://127.0.0.1:8000/docs

**SSE 事件协议**（前端按此解析）：

| 事件 | 数据 | 用途 |
|---|---|---|
| `start` | `{conversationId, messageId}` | 拿到会话 ID |
| `tool_call` | `{name, args}` | 显示「正在查天气 / 正在规划路线」 |
| `tool_result` | `{name, preview}` | 显示工具返回摘要 |
| `token` | `{content}` | 打字机效果，逐字追加 |
| `done` | `{conversationId, messageId}` | 本轮结束 |
| `error` | `{error}` | 出错信息 |

## 目录结构

```
.
├── travel_plan_agent/            # 后端
│   ├── api/                      # HTTP 接口层（FastAPI 路由）
│   ├── memory/                   # 记忆模块
│   │   ├── short_term.py         #   短期记忆（SQLite）
│   │   ├── long_term.py          #   长期记忆（Chroma）
│   │   └── embeddings.py         #   嵌入函数（本地模型 / 哈希兜底）
│   ├── tools/                    # 11 个 Agent 工具
│   ├── webui/                    # 前端构建产物（由后端托管）
│   ├── build_agent.py            # Agent 组装与系统提示词
│   ├── server.py                 # FastAPI 应用
│   └── __main__.py               # python -m 启动入口
├── travel-plan-web/              # 前端（React 19 + Vite）
│   └── src/
│       ├── api/client.js         #   接口封装（含 SSE 手工解析）
│       └── components/           #   消息列表 / 工具时间线 / 会话列表 / 输入框
├── scripts/download_model.py     # 嵌入模型下载（零依赖）
└── pyproject.toml                # 打包配置
```

## 数据存放

运行时数据都在 `travel_plan_agent/memory_data/`：

| 文件 | 内容 |
|---|---|
| `short_term_memory.db` | 短期记忆（各会话对话） |
| `long_term_memory/` | 长期记忆（Chroma 向量库） |
| `checkpoints.db` | 对话状态检查点 |

删除整个 `memory_data/` 目录即清空所有记忆（程序会自动重建）。

## 常见问题

**Q：打开 8000 端口只有一句提示，没有界面？**
说明前端还没构建。执行 `cd travel-plan-web && npm run build:agent`。

**Q：长期记忆检索不准？**
先确认模型是否已下载：`travel_plan_agent/paraphrase-multilingual-MiniLM-L12-v2/model.safetensors`。缺失时会降级为哈希嵌入。

**Q：一次规划要等很久？**
正常，Agent 会串行调用多个工具。前端是流式的，可以实时看到进度，也可以随时停止。

**Q：能用多进程 / 多 worker 启动吗？**
不能。内部使用全局单例与 SQLite，请以单进程运行。

**Q：为什么仓库里没有嵌入模型？**
完整模型有 4.4 GB，超出 GitHub 限制，因此改为按需下载（`scripts/download_model.py`），且程序在无模型时也能运行。

## License

[MIT](LICENSE)
