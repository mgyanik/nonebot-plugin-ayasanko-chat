# tests/test_multimodal.py
from nonebot_plugin_ayasanko_chat.config import ChatConfig
from nonebot_plugin_ayasanko_chat.engine import ChatEngine


def test_multimodal_content_formatting():
    config = ChatConfig()
    engine = ChatEngine(config)

    # 纯文本
    text_only = engine._format_user_content("你好", [])
    assert text_only == "你好"

    # 图文多模态
    img_urls = ["https://example.com/cat1.jpg", "https://example.com/cat2.jpg"]
    multimodal = engine._format_user_content("看这两只猫", img_urls)

    assert isinstance(multimodal, list)
    assert len(multimodal) == 3
    assert multimodal[0] == {"type": "text", "text": "看这两只猫"}
    assert multimodal[1] == {"type": "image_url", "image_url": {"url": "https://example.com/cat1.jpg"}}
    assert multimodal[2] == {"type": "image_url", "image_url": {"url": "https://example.com/cat2.jpg"}}
