# tests/conftest.py
import sys
from unittest.mock import MagicMock

# 确保在未安装 NoneBot 的精简测试环境下，自动化测试仍可正常运行
if "nonebot" not in sys.modules:
    mock_nonebot = MagicMock()
    mock_matcher = MagicMock()
    mock_matcher.handle.return_value = lambda f: f
    mock_nonebot.on_message.return_value = mock_matcher
    sys.modules["nonebot"] = mock_nonebot
    sys.modules["nonebot.adapters"] = MagicMock()
    sys.modules["nonebot.exception"] = MagicMock()
    sys.modules["nonebot.internal.matcher"] = MagicMock()
    sys.modules["nonebot.log"] = MagicMock()
    sys.modules["nonebot.plugin"] = MagicMock()

if "pydantic" not in sys.modules:
    _validators_map: dict[str, list] = {}

    def _field_validator(*field_names, mode="after"):
        def decorator(fn):
            for name in field_names:
                _validators_map.setdefault(name, []).append(fn)
            return fn
        return decorator

    def _mock_field(*args, default=None, default_factory=None, **kwargs):
        if default_factory is not None:
            return default_factory()
        return default

    class MockBaseModel:
        def __init__(self, **kwargs):
            # 填充默认值
            for k in dir(self.__class__):
                if not k.startswith("_"):
                    val = getattr(self.__class__, k)
                    if not callable(val):
                        setattr(self, k, val)
            # 填充入参
            for k, v in kwargs.items():
                setattr(self, k, v)
            # 执行验证器
            for k in list(self.__dict__.keys()):
                if k in _validators_map:
                    for fn in _validators_map[k]:
                        actual_fn = getattr(fn, "__func__", fn)
                        setattr(self, k, actual_fn(self.__class__, getattr(self, k)))

    mock_pydantic = MagicMock()
    mock_pydantic.Field = _mock_field
    mock_pydantic.field_validator = _field_validator
    mock_pydantic.BaseModel = MockBaseModel
    mock_pydantic.ConfigDict = dict
    sys.modules["pydantic"] = mock_pydantic
