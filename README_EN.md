# nonebot-plugin-ayasanko-chat

<div align="center">

[![PyPI](https://img.shields.io/pypi/v/nonebot-plugin-ayasanko-chat.svg)](https://pypi.org/project/nonebot-plugin-ayasanko-chat/)
[![Release](https://img.shields.io/badge/Release-v0.3.0-brightgreen.svg)](https://github.com/mgyanik/nonebot-plugin-ayasanko-chat/releases)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![NoneBot](https://img.shields.io/badge/NoneBot-2.3%2B-ea5252.svg)](https://nonebot.dev/)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2-e92063.svg?logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-orange.svg)](LICENSE)

[English](README_EN.md) | [简体中文](README.md)

</div>

NoneBot2 AI chat plugin supporting **OneBot V11**, **QQ Official**, and **Discord** multi-platform adapters, featuring **DeepSeek Reasoning Thinking Extraction**, **Multimodal Vision Inputs**, and **SQLite Session Persistence**.

---

## Key Features

- **Multi-Platform Matrix**: Unified strategy pattern supporting **OneBot V11**, **QQ Official Open Platform**, and **Discord**, normalizing user IDs, channel/guild routing, mentions, and nickname stripping.
- **Multimodal Vision Support**: Automatically detects and extracts images (QQ/OneBot/Discord), converting them into standard OpenAI multimodal format for GPT-4o, GLM-4V, and Claude.
- **DeepSeek Reasoning & SSE Streaming (R1)**: Native extraction of DeepSeek-R1 `reasoning_content` and `<think>` tags, supporting SSE streaming and formatted thinking display.
- **Dual Storage Engine (Memory / SQLite)**:
  - `memory`: In-memory **LRU eviction + TTL expiration** bounding memory overhead to constant $O(1)$.
  - `sqlite`: WAL-mode SQLite database persistence, ensuring **conversation history is never lost** across bot restarts.
- **Context Isolation & Shared Group Memory**: Configurable `individual` (per-user context) and `shared` (group-wide collective memory) modes to prevent cross-context leakage.
- **Global HTTP Connection Pool**: Shared `httpx.AsyncClient` with keep-alive limits bound to NoneBot lifecycle, slashing connection handshake latency by 30%~50%.
- **Adaptive Exponential Backoff with Jitter**: Automatically handles upstream 429, 502/503/504 network glitches with randomized jitter retries.
- **Sliding-Window Rate Limiting**: In-memory token bucket/sliding window limiter to prevent abuse and protect API budgets.
- **Safe Concurrent Scheduling**: Resolved `PriorityQueue` sorting hazards preventing crashes on Future comparisons; supports per-session serial execution.
- **Group Whitelist/Blacklist & Safe Chunking**: Selective group activation and intelligent chunking for long messages exceeding platform limits.
- **Ecosystem Integration**: Standard `get_context_count()` and `clear_context()` APIs for manager plugin interop.

---

## Installation

```bash
# Basic installation
nb plugin install nonebot-plugin-ayasanko-chat
# or
pip install nonebot-plugin-ayasanko-chat

# Adapter extras
pip install "nonebot-plugin-ayasanko-chat[onebot]"     # OneBot V11
pip install "nonebot-plugin-ayasanko-chat[qq]"         # QQ Official
pip install "nonebot-plugin-ayasanko-chat[discord]"    # Discord
pip install "nonebot-plugin-ayasanko-chat[all]"        # All platforms
```

---

## Quick Configuration

Add configurations to `.env` or `.env.prod` in your NoneBot2 project (see [.env.example](.env.example) for details):

```env
# LLM Endpoint & Parameters (Supports DeepSeek, Zhipu, OpenAI, Ollama, etc.)
CHAT__API_KEY=your_api_key_here
CHAT__API_BASE=https://api.deepseek.com
CHAT__MODEL=deepseek-reasoner
CHAT__MAX_TOKENS=2000
CHAT__TEMPERATURE=1.0
CHAT__TIMEOUT=60

# Streaming & Reasoning Display
CHAT__STREAM=false                    # Enable SSE streaming
CHAT__SHOW_THINKING=true              # Show formatted DeepSeek reasoning content

# Storage Engine
CHAT__STORAGE_BACKEND=sqlite          # "memory" or "sqlite"
CHAT__SQLITE_PATH=data/ayasanko_chat.db

# Session & Isolation
CHAT__GROUP_SESSION_MODE=individual   # "individual" or "shared"
CHAT__SESSION_TTL=1800                # Idle session timeout (seconds, default 30 min)
CHAT__MAX_SESSIONS=500                # In-memory session limit (LRU evicted)

# High Availability & Rate Limits
CHAT__MAX_RETRIES=2                   # Retries on 429/5xx glitches
CHAT__RATE_LIMIT_REQUESTS=10          # Max requests per window (0 to disable)
CHAT__RATE_LIMIT_PERIOD=60            # Window duration in seconds

# Role & Mentions
CHAT__SYSTEM_PROMPT=You are a helpful AI assistant.
CHAT__NICKNAME=["Cat", "Assistant"]
```

---

## Project Structure & Architecture

> [!NOTE]
> **💡 Directory Naming Clarification (Why are there two similar folder names?)**
>
> - **Outer Directory `nonebot-plugin-ayasanko-chat/` (with hyphens `-`)**: The **Git repository root** and the **PyPI package distribution name** (e.g., used when running `pip install nonebot-plugin-ayasanko-chat`). This level houses project documentation, build metadata, licensing, and test suites.
> - **Inner Directory `nonebot_plugin_ayasanko_chat/` (with underscores `_`)**: The **actual Python source code package**. Python syntax prohibits hyphens in module import names (as they are parsed as subtraction operators raising `SyntaxError`). Per PEP 423 / PEP 517 and NoneBot packaging standards, the importable module must use underscores (e.g. `import nonebot_plugin_ayasanko_chat`). These are not duplicate folders, but standard engineering layers.

```text
nonebot-plugin-ayasanko-chat/          # [Outer] Repository root / PyPI package distribution name (hyphens -)
├── pyproject.toml                     # Project dependencies & PEP 517/621 build configuration
├── README.md                          # Chinese documentation
├── README_EN.md                       # English documentation
├── LICENSE                            # MIT License
├── data/                              # Local runtime data (e.g. SQLite DB, git-ignored)
├── dist/                              # Built distribution artifacts (.whl and .tar.gz)
├── tests/                             # Automated testing & standalone CLI
│   ├── conftest.py                    # Mock fixtures for standalone test environments
│   ├── verify_standalone.py           # Standalone interactive CLI terminal simulator
│   └── test_*.py                      # pytest test suite
└── nonebot_plugin_ayasanko_chat/      # [Inner] Python source package (underscores _, imported in code)
    ├── __init__.py                    # Plugin entry, event matcher, and public exports
    ├── config.py                      # Pydantic v2 typed configuration model
    ├── client.py                      # Global HTTP connection pool lifecycle management
    ├── session.py                     # Session data models and helper utilities
    ├── limiter.py                     # Sliding-window rate limiter
    ├── engine.py                      # Dispatch engine: multimodal, streaming, retries, and reasoning parser
    ├── processor.py                   # Backward-compatibility shim for legacy callers
    ├── storage/                       # Persistent storage backends
    │   ├── base.py                    # BaseStorageBackend abstract interface
    │   ├── memory.py                  # In-memory LRU + TTL backend
    │   └── sqlite.py                  # High-concurrency WAL SQLite persistence backend
    └── adapters/                      # Protocol adapter strategy layer
        ├── base.py                    # Abstract adapter base class
        ├── onebot.py                  # OneBot V11 implementation (with image & revoke support)
        ├── qq.py                      # QQ official implementation (with image support)
        └── discord.py                 # Discord implementation (with attachments support)
```

---

## Unit Testing

Run unit tests via pytest:

```bash
poetry run pytest -v
```

---

## License

This project is licensed under the [MIT License](LICENSE).
