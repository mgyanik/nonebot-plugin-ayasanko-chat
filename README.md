# nonebot-plugin-ayasanko-chat

[English](README_EN.md) | [简体中文](README.md)

NoneBot2 AI 对话插件，支持 **OneBot V11**、**QQ 官方开放平台** 与 **Discord** 多平台适配器，内建 **DeepSeek 思考链**、**多模态视觉图文** 与 **SQLite 会话持久化**。

---

## 核心特性

- **多平台适配器矩阵**：统一抽象策略层，无缝支持 **OneBot V11**、**QQ 官方开放平台** 与 **Discord**，统一处理用户 ID、群组/公会识别、@提及与昵称清洗。
- **多模态视觉支持 (Vision)**：自动检测并提取消息中的图片 URL（QQ/OneBot/Discord），组装为 OpenAI 标准多模态格式，无缝支持 GPT-4o、GLM-4V 等视觉模型。
- **DeepSeek 思考链与流式推理 (R1)**：原生解析 DeepSeek-R1 / `deepseek-reasoner` 的 `reasoning_content` 及 `<think>` 标签，支持打字机 SSE 流式传输与思考过程独立折叠展示。
- **持久化存储双引擎 (Memory / SQLite)**：
  - `memory`：基于 **LRU 淘汰 + TTL 自动失效机制**，常数阶 $O(1)$ 内存开销，杜绝高频群聊环境下的内存无界膨胀。
  - `sqlite`：基于 WAL 高并发模式的 SQLite 数据库存储，服务重启、更新代码或崩溃恢复后**对话历史永不丢失**。
- **群/私聊会话隔离与共享**：支持配置 `individual`（群内个人独立上下文）与 `shared`（群内全员共享连续记忆）双模式，彻底解决不同群聊与私聊串台问题。
- **全局 HTTP 连接池复用**：内建共享 `httpx.AsyncClient` 长连接池与驱动生命周期管理，降低 30%~50% 请求握手延迟。
- **自适应指数退避重试 (Exponential Backoff with Jitter)**：针对上游大模型偶发 429、502/503/504 网络抖动，自动按随机抖动时间退避重试，保障请求成功率。
- **滑动窗口速率限制 (Rate Limiting)**：内置内存滑动窗口限流器，有效防止用户恶意高频刷屏消耗 API 额度。
- **安全并发调度引擎**：修复 `PriorityQueue` 协程安全排序，防止高并发下因 Future 比较引发崩溃；支持单用户/会话任务队列串行化。
- **群聊黑白名单与长文本保护**：支持群白名单、黑名单过滤；单条长回复超限自动智能断句分段下发。
- **外部生态互通**：对外导出标准会话控制函数 `get_context_count()` 与 `clear_context()`，无缝联动管理类插件。

---

## 安装方式

```bash
# 基础安装
nb plugin install nonebot-plugin-ayasanko-chat
# 或
pip install nonebot-plugin-ayasanko-chat

# 安装特定平台适配器扩展
pip install "nonebot-plugin-ayasanko-chat[onebot]"     # OneBot V11
pip install "nonebot-plugin-ayasanko-chat[qq]"         # QQ 官方
pip install "nonebot-plugin-ayasanko-chat[discord]"    # Discord
pip install "nonebot-plugin-ayasanko-chat[all]"        # 全平台支持
```

---

## 快速配置

在 NoneBot2 项目的 `.env` 或 `.env.prod` 文件中添加配置项（完整参数见 [.env.example](.env.example)）：

```env
# 核心大模型配置 (支持智谱、DeepSeek、OpenAI、Ollama等)
CHAT__API_KEY=your_api_key_here
CHAT__API_BASE=https://api.deepseek.com
CHAT__MODEL=deepseek-reasoner
CHAT__MAX_TOKENS=2000
CHAT__TEMPERATURE=1.0
CHAT__TIMEOUT=60

# 思考链与流式输出
CHAT__STREAM=false                    # 是否启用 SSE 流式接收
CHAT__SHOW_THINKING=true              # 是否在回复中保留并排版展示思考链 (Reasoning)

# 存储后端
CHAT__STORAGE_BACKEND=sqlite          # "memory"(内存LRU) 或 "sqlite"(持久化)
CHAT__SQLITE_PATH=data/ayasanko_chat.db # SQLite 文件存放路径

# 会话与隔离模式
CHAT__GROUP_SESSION_MODE=individual   # "individual"(群内单人隔离) 或 "shared"(群内共享记忆)
CHAT__SESSION_TTL=1800                # 会话闲置过期时间（秒，默认 30 分钟）
CHAT__MAX_SESSIONS=500                # 内存活跃会话上限（超出后按 LRU 自动淘汰）

# 高可用与限流
CHAT__MAX_RETRIES=2                   # 遇到网络抖动/429/5xx时的最大重试次数
CHAT__RATE_LIMIT_REQUESTS=10          # 周期内最大请求数（0 表示关闭限流）
CHAT__RATE_LIMIT_PERIOD=60            # 速率限制周期时长（秒）

# 角色与触发设定
CHAT__SYSTEM_PROMPT=你是一位聪明、可爱且乐于助人的 AI 助手。
CHAT__NICKNAME=["猫猫", "小助手"]
```

---

## 项目架构与目录结构

> [!NOTE]
> **💡 目录命名说明（为什么会有两个名字相似的目录？）**
>
> - **外层目录 `nonebot-plugin-ayasanko-chat/`（中划线 `-`）**：这是 **Git 仓库根目录** 与 **PyPI 安装包名**（例如执行 `pip install nonebot-plugin-ayasanko-chat`）。这里存放的是项目全局文档、构建元数据、许可证及自动化测试套件。
> - **内层目录 `nonebot_plugin_ayasanko_chat/`（下划线 `_`）**：这是实际运行的 **Python 核心源码包**。因为 Python 语法规则禁止模块导入名称中含有减号 `-`（会被解释器视为减号运算符触发 `SyntaxError`），因此按照 Python/NoneBot 标准规范，实际业务包必须使用下划线（供 `import nonebot_plugin_ayasanko_chat` 调用）。两者并非重复目录，而是符合 PEP 423 / PEP 517 标准规范的工程分层设计。

```text
nonebot-plugin-ayasanko-chat/          # 【外层】Git 仓库根目录 / PyPI 分发包名（使用中划线 - ）
├── pyproject.toml                     # 项目依赖与 PEP 517/621 构建元数据
├── README.md                          # 中文说明文档
├── README_EN.md                       # 英文说明文档
├── LICENSE                            # MIT 开源协议
├── data/                              # 本地运行时数据（如 SQLite 数据库，已加入 .gitignore）
├── dist/                              # 打包构建产物目录（.whl 与 .tar.gz）
├── tests/                             # 自动化测试与实机模拟器
│   ├── conftest.py                    # pytest 测试桩配置
│   ├── verify_standalone.py           # 独立交互式终端模拟器 (CLI，不依赖 NoneBot 即可直接对话测试)
│   └── test_*.py                      # 核心单元测试集
└── nonebot_plugin_ayasanko_chat/      # 【内层】实际 Python 代码模块（使用下划线 _，供 import 调用）
    ├── __init__.py                    # 插件入口、事件响应器与公开 API 导出
    ├── config.py                      # 基于 Pydantic v2 的类型化配置定义
    ├── client.py                      # 全局 HTTP 连接池生命周期管理
    ├── session.py                     # 会话数据模型与生命周期辅助
    ├── limiter.py                     # 滑动窗口速率限制器
    ├── engine.py                      # 调度引擎：多模态组装、流式处理、退避重试与思考链解析
    ├── processor.py                   # 历史向后兼容垫片层
    ├── storage/                       # 持久化存储后端抽象
    │   ├── base.py                    # 存储基类 BaseStorageBackend
    │   ├── memory.py                  # 内存 LRU + TTL 后端
    │   └── sqlite.py                  # 高并发 WAL SQLite 持久化后端
    └── adapters/                      # 适配器策略层
        ├── base.py                    # 适配器抽象基类
        ├── onebot.py                  # OneBot V11 协议实现（含图片与撤回）
        ├── qq.py                      # QQ 官方开放平台实现（含图片）
        └── discord.py                 # Discord 平台实现（含附件图片识别）
```

---

## 单元测试

项目内置完整的 pytest 测试套件：

```bash
poetry run pytest -v
```

---

## 开源协议

本项目采用 [MIT License](LICENSE) 许可协议。
