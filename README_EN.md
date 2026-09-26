# nonebot-plugin-ayasanko-chat

[English](README_EN.md) | [简体中文](README.md)

NoneBot2 AI-assisted chat plugin supporting OneBot V11 and QQ official adapters.

---

## Features

- **Multi-Adapter Support**: Compatible with OneBot V11 and QQ official adapters.
- **Concurrency & Queue Management**: Built-in user-level priority queues and semaphore concurrency controls.
- **Context Handling**: Preserves conversation history, customized system prompts, and context clearing (`/clear`).
- **Configurable**: Highly customizable API endpoints, model parameters, and nicknames via `.env`.

---

## Installation

```bash
# via nb-cli
nb plugin install nonebot-plugin-ayasanko-chat

# via pip
pip install nonebot-plugin-ayasanko-chat
```

---

## Configuration

Add the following configurations to your NoneBot2 `.env` file:

```env
CHAT__API_KEY=<your_api_key>
CHAT__API_BASE=https://open.bigmodel.cn/api/paas/v4
CHAT__MODEL=glm-4.5-air
CHAT__MAX_TOKENS=1000
CHAT__TEMPERATURE=1.0
CHAT__TIMEOUT=30
SYSTEM_PROMPT=You are a helpful AI assistant.
CHAT__NICKNAME=["Cat", "Bot"]
```

---

## Commands

| Command | Description |
| :--- | :--- |
| `/clear` | Clear conversation history and reset memory |

---

## License

This project is licensed under the [MIT License](LICENSE).
