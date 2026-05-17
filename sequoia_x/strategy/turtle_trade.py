"""海龟交易策略：20日新高突破 + 多层质量过滤。"""

import pandas as pd

from sequoia_x.core.logger import get_logger
from sequoia_x.strategy.base import BaseStrategy

logger = get_logger(__name__)


class TurtleTradeStrategy(BaseStrategy):
    """海龟交易策略（A股防诱多改良版）。

    选股条件（优先使用共享指标缓存）：
    1. 突破新高：今日 close > 前20个交易日 high 的最大值（high_20_shifted）
    2. 流动性：今日 turnover > 100,000,000
    3. 防诱多：今日实体阳线 + 真涨（close > 昨日 close）
    4. 放量确认：今日 volume > 20日均量 × 1.3（vol_ma20）
    5. 趋势质量：近60日最低点 >= 最高点 × 0.6（high_60 / low_60）

    后处理：按近20日均成交额排序，过滤 < 5kw，仅保留 Top 30。

    Attributes:
        webhook_key: 路由到 'turtle' 专属飞书机器人。
    """

    webhook_key: str = "turtle"
    _MIN_AVG_TURNOVER: float = 50_000_000
    _MAX_RESULTS: int = 30

    def run(self) -> list[str]:
        """遍历全市场，返回满足海龟突破条件的股票代码列表。"""
        if self.cache is None:
            return self._run_legacy()

        symbols = self.cache.symbols
        candidates: list[tuple[str, float]] = []

        for symbol in symbols:
            df = self.cache.get(symbol)
            if df is None:
                continue

            last = df.iloc[-1]
            prev = df.iloc[-2]

            if pd.isna(last["high_20_shifted"]) or pd.isna(last["turnover_20"]):
                continue

            breakout = last["close"] > last["high_20_shifted"]
            liquid = last["turnover"] > 100_000_000
            is_yang = last["close"] > last["open"]
            is_up = last["close"] > prev["close"]
            volume_confirm = last["volume"] > last["vol_ma20"] * 1.3
            trend_ok = (
                last["low_60"] >= last["high_60"] * 0.6
                if last["high_60"] > 0
                else False
            )

            if breakout and liquid and is_yang and is_up and volume_confirm and trend_ok:
                avg_turnover = float(last["turnover_20"])
                candidates.append((symbol, avg_turnover))

        if not candidates:
            logger.info("TurtleTradeStrategy 选出 0 只股票")
            return []

        raw_count = len(candidates)
        candidates = [(s, t) for s, t in candidates if t >= self._MIN_AVG_TURNOVER]
        after_filter = len(candidates)
        candidates.sort(key=lambda x: x[1], reverse=True)
        top = [s for s, _ in candidates[:self._MAX_RESULTS]]

        logger.info(
            f"TurtleTradeStrategy 选出 {raw_count} 只"
            f" → 成交额过滤后 {after_filter} 只"
            f" → 推送 Top {len(top)} 只"
        )
        return top

    def _run_legacy(self) -> list[str]:
        """回退模式：使用 DataEngine 逐票计算指标（兼容无 cache 场景）。"""
        symbols = self.engine.get_local_symbols()
        candidates: list[tuple[str, float]] = []

        for symbol in symbols:
            try:
                df = self.engine.get_ohlcv(symbol)
                if len(df) < 60:
                    continue

                df["high_20"] = df["high"].shift(1).rolling(20).max()
                df["vol_ma20"] = df["volume"].rolling(20).mean()
                df["turnover_20"] = df["turnover"].rolling(20).mean()

                last = df.iloc[-1]
                prev = df.iloc[-2]

                if pd.isna(last["high_20"]) or pd.isna(last["turnover_20"]):
                    continue

                breakout = last["close"] > last["high_20"]
                liquid = last["turnover"] > 100_000_000
                is_yang = last["close"] > last["open"]
                is_up = last["close"] > prev["close"]
                volume_confirm = last["volume"] > last["vol_ma20"] * 1.3

                tail60 = df.tail(60)
                high60 = tail60["high"].max()
                low60 = tail60["low"].min()
                trend_ok = low60 >= high60 * 0.6 if high60 > 0 else False

                if breakout and liquid and is_yang and is_up and volume_confirm and trend_ok:
                    avg_turnover = float(last["turnover_20"])
                    candidates.append((symbol, avg_turnover))

            except Exception as exc:
                logger.warning(f"[{symbol}] TurtleTradeStrategy 计算失败：{exc}")
                continue

        if not candidates:
            logger.info("TurtleTradeStrategy 选出 0 只股票")
            return []

        raw_count = len(candidates)
        candidates = [(s, t) for s, t in candidates if t >= self._MIN_AVG_TURNOVER]
        after_filter = len(candidates)
        candidates.sort(key=lambda x: x[1], reverse=True)
        top = [s for s, _ in candidates[:self._MAX_RESULTS]]

        logger.info(
            f"TurtleTradeStrategy 选出 {raw_count} 只"
            f" → 成交额过滤后 {after_filter} 只"
            f" → 推送 Top {len(top)} 只"
        )
        return top
