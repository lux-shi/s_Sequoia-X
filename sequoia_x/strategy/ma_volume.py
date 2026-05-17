"""均线+成交量选股策略：5日均线上穿20日均线且成交量放大。"""

from sequoia_x.core.logger import get_logger
from sequoia_x.strategy.base import BaseStrategy

logger = get_logger(__name__)


class MaVolumeStrategy(BaseStrategy):
    """均线+成交量选股策略。

    选股条件（依赖共享指标缓存）：
    1. 5日收盘均线上穿20日收盘均线（金叉）
    2. 当日成交量 > 20日均量的 1.5 倍（放量确认）

    Attributes:
        webhook_key: 路由到 'ma_volume' 专属飞书机器人。
    """

    webhook_key: str = "ma_volume"

    def run(self) -> list[str]:
        """遍历全市场，返回满足均线金叉+放量条件的股票代码列表。"""
        if self.cache is None:
            logger.warning("MaVolumeStrategy 需要 IndicatorCache，回退到 DataEngine 逐票查询")
            return self._run_legacy()

        symbols = self.cache.symbols
        selected: list[str] = []

        for symbol in symbols:
            df = self.cache.get(symbol)
            if df is None:
                continue

            last = df.iloc[-1]
            prev = df.iloc[-2]

            golden_cross = (
                prev["ma5"] < prev["ma20"]
                and last["ma5"] > last["ma20"]
            )
            volume_surge = last["volume"] > last["vol_ma20"] * 1.5

            if golden_cross and volume_surge:
                selected.append(symbol)

        logger.info(f"MaVolumeStrategy 选出 {len(selected)} 只股票")
        return selected

    def _run_legacy(self) -> list[str]:
        """回退模式：使用 DataEngine 逐票计算（兼容无 cache 的场景）。"""
        import pandas as pd

        symbols = self.engine.get_local_symbols()
        selected: list[str] = []

        for symbol in symbols:
            try:
                df = self.engine.get_ohlcv(symbol)
                if len(df) < 20:
                    continue

                df["ma5"] = df["close"].rolling(5).mean()
                df["ma20"] = df["close"].rolling(20).mean()
                df["vol_ma20"] = df["volume"].rolling(20).mean()

                last = df.iloc[-1]
                prev = df.iloc[-2]

                golden_cross = (
                    prev["ma5"] < prev["ma20"]
                    and last["ma5"] > last["ma20"]
                )
                volume_surge = last["volume"] > last["vol_ma20"] * 1.5

                if golden_cross and volume_surge:
                    selected.append(symbol)

            except Exception as exc:
                logger.warning(f"[{symbol}] 策略计算失败：{exc}")
                continue

        logger.info(f"MaVolumeStrategy 选出 {len(selected)} 只股票")
        return selected
