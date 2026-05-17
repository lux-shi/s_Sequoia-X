"""海龟交易策略：20日新高突破 + 多层质量过滤。"""

import pandas as pd

from sequoia_x.core.logger import get_logger
from sequoia_x.strategy.base import BaseStrategy

logger = get_logger(__name__)


class TurtleTradeStrategy(BaseStrategy):
    """海龟交易策略（A股防诱多改良版）。

    选股条件（全部向量化，严禁 iterrows）：
    1. 突破新高：今日 close > 前20个交易日 high 的最大值
    2. 流动性：今日 turnover > 100,000,000（成交额过亿）
    3. 防诱多：今日实体阳线 + 真涨（close > 昨日 close）
    4. 放量确认：今日 volume > 20日均量 × 1.3
    5. 趋势质量：近60日最低点 >= 最高点 × 0.6

    后处理：
    - 按近20日均成交额排序，仅保留 Top 30
    - 过滤日均成交额 < 5,000 万的股票（排除流动性不足的小票）

    Attributes:
        webhook_key: 路由到 'turtle' 专属飞书机器人。
    """

    webhook_key: str = "turtle"
    _MIN_BARS: int = 60
    _MIN_AVG_TURNOVER: float = 50_000_000  # 20日均成交额下限 5 千万
    _MAX_RESULTS: int = 30

    def run(self) -> list[str]:
        """遍历全市场，返回满足海龟突破条件的股票代码列表。"""
        symbols = self.engine.get_local_symbols()
        candidates: list[tuple[str, float]] = []  # (symbol, avg_turnover)

        for symbol in symbols:
            try:
                df = self.engine.get_ohlcv(symbol)
                if len(df) < self._MIN_BARS:
                    continue

                # ——— 向量化指标 ———
                df["high_20"] = df["high"].shift(1).rolling(20).max()
                df["vol_ma20"] = df["volume"].rolling(20).mean()
                df["turnover_20"] = df["turnover"].rolling(20).mean()

                last = df.iloc[-1]
                prev = df.iloc[-2]

                if pd.isna(last["high_20"]) or pd.isna(last["vol_ma20"]) or pd.isna(last["turnover_20"]):
                    continue

                # 条件 1：突破前 20 天最高点
                breakout = last["close"] > last["high_20"]

                # 条件 2：流动性过亿（当日成交额）
                liquid = last["turnover"] > 100_000_000

                # 条件 3：防诱多 — 实体阳线 + 真涨
                is_yang = last["close"] > last["open"]
                is_up = last["close"] > prev["close"]

                # 条件 4：放量确认 — 突破日必须有量配合
                volume_confirm = last["volume"] > last["vol_ma20"] * 1.3

                # 条件 5：趋势质量 — 60 日内不能深度下跌
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

        # ——— 后处理：按日均成交额过滤 + 排序，取 Top N ———
        raw_count = len(candidates)

        # 过滤日均成交额 < 5 千万
        candidates = [(s, t) for s, t in candidates if t >= self._MIN_AVG_TURNOVER]
        after_filter = len(candidates)

        # 按成交额降序，取 Top N
        candidates.sort(key=lambda x: x[1], reverse=True)
        top = [s for s, _ in candidates[:self._MAX_RESULTS]]

        logger.info(
            f"TurtleTradeStrategy 选出 {raw_count} 只"
            f" → 成交额过滤后 {after_filter} 只"
            f" → 推送 Top {len(top)} 只"
        )
        return top
