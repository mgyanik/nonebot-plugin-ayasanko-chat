# tests/test_reasoning.py
from nonebot_plugin_ayasanko_chat.config import ChatConfig
from nonebot_plugin_ayasanko_chat.engine import ChatEngine


def test_deepseek_reasoning_content_shown():
    config = ChatConfig(show_thinking=True)
    engine = ChatEngine(config)

    content = "42 是答案"
    reasoning = "通过深度思考计算，宇宙的终极答案是 42。"
    result = engine._assemble_final_text(content, reasoning)

    assert "💡 【深度思考过程】" in result
    assert "宇宙的终极答案是 42。" in result
    assert "42 是答案" in result


def test_deepseek_reasoning_content_hidden():
    config = ChatConfig(show_thinking=False)
    engine = ChatEngine(config)

    content = "42 是答案"
    reasoning = "思考中..."
    result = engine._assemble_final_text(content, reasoning)

    assert "💡 【深度思考过程】" not in result
    assert result == "42 是答案"


def test_embedded_think_tags_parsing():
    config = ChatConfig(show_thinking=True)
    engine = ChatEngine(config)

    content = "<think>\n这里是推理阶段的内容\n</think>\n最终回复文本"
    result = engine._assemble_final_text(content, None)

    assert "💡 【深度思考过程】" in result
    assert "这里是推理阶段的内容" in result
    assert "最终回复文本" in result
    assert "<think>" not in result
