# nonebot-plugin-ayasanko-chat

[English](README_EN.md) | [简体中文](README.md)

基于 NoneBot2 的 AI 智能聊天插件，支持 OneBot V11 与 QQ 官方适配器。

---

## 特性

- **多适配器兼容**：支持 OneBot V11 及 QQ 官方适配器。
- **并发与队列控制**：内置用户级任务队列与请求并发信号量控制。
- **上下文管理**：支持会话记忆、角色设定 Prompt 与指令重置（`/clear`）。
- **配置化**：通过环境变量灵活配置大模型 API 地址、Key、模型名称等。

---

## 安装

```bash
# 使用 nb-cli
nb plugin install nonebot-plugin-ayasanko-chat

# 使用 pip
pip install nonebot-plugin-ayasanko-chat
```

---

## 配置项

在 NoneBot2 项目的 `.env` 文件中添加以下配置项：

```env
# 聊天插件配置
CHAT__API_KEY=<your_api_key>
CHAT__API_BASE=https://open.bigmodel.cn/api/paas/v4
CHAT__MODEL=glm-4.5-air
CHAT__MAX_TOKENS=1000
CHAT__TEMPERATURE=1.0
CHAT__TIMEOUT=30
SYSTEM_PROMPT=你是一位有用的AI
CHAT__NICKNAME=["亚托莉", "猫猫"]
```

---

## 基础指令

| 指令 | 说明 |
| :--- | :--- |
| `/clear` | 清理用户当前的对话上下文与历史记录 |

---

## 开源协议

本项目采用 [MIT License](LICENSE) 许可协议。
