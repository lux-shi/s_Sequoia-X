"""策略基类模块：定义所有选股策略的抽象接口 + 自动注册。"""

from abc import ABC, abstractmethod

from sequoia_x.core.config import Settings
from sequoia_x.data.engine import DataEngine
from sequoia_x.data.indicators import IndicatorCache


class BaseStrategy(ABC):
    """选股策略抽象基类。

    所有具体策略必须继承此类并实现 run() 方法。
    子类会自动注册到策略注册表，无需手动修改 main.py。

    Attributes:
        webhook_key: 飞书 webhook 标识，默认 'default'。
        enabled: 设为 False 可临时禁用该策略而不删除文件。
    """

    webhook_key: str = "default"
    enabled: bool = True

    # ——— 自动注册 ———
    _registry: list[type["BaseStrategy"]] = []

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if not cls.__name__.startswith("_"):
            cls._registry.append(cls)

    @classmethod
    def get_strategies(cls) -> list[type["BaseStrategy"]]:
        """返回所有已注册的策略类（按注册顺序）。"""
        return cls._registry

    # ——— 实例 ———

    def __init__(
        self,
        engine: DataEngine,
        settings: Settings,
        cache: IndicatorCache | None = None,
    ) -> None:
        self.engine = engine
        self.settings = settings
        self.cache = cache

    @abstractmethod
    def run(self) -> list[str]:
        """执行选股逻辑，返回选中的股票代码列表。"""
        ...
