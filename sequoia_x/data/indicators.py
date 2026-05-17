"""共享指标缓存：一次性全量加载 + 批量向量化计算，策略层复用。"""

import sqlite3

import pandas as pd

from sequoia_x.core.logger import get_logger

logger = get_logger(__name__)

# 核心指标集及其所需最小 K 线条数
_CORE_INDICATORS = {
    "ma5": 5,
    "ma20": 20,
    "ma60": 60,
    "vol_ma20": 20,
    "turnover_20": 20,
    "high_20_shifted": 21,
    "high_60": 60,
    "low_60": 60,
}
_MIN_BARS = max(_CORE_INDICATORS.values())  # 60


class IndicatorCache:
    """全市场行情 + 核心指标缓存。

    一次 SQL 查询加载全表，pandas groupby + rolling 批量计算指标。
    策略通过 get(symbol) 获取预计算好的最近 N 行（含所有核心列）。
    策略专属指标仍可通过 engine.get_ohlcv() 自行计算。
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._cache: dict[str, pd.DataFrame] = {}
        self._symbols: list[str] = []

    def compute_all(self) -> list[str]:
        """加载全市场数据，批量计算核心指标，存入缓存。

        Returns:
            可用股票代码列表。
        """
        with sqlite3.connect(self._db_path) as conn:
            df = pd.read_sql(
                "SELECT symbol, date, open, high, low, close, volume, turnover "
                "FROM stock_daily ORDER BY symbol, date",
                conn,
            )

        if df.empty:
            logger.warning("stock_daily 为空，跳过指标计算")
            return []

        df["date"] = pd.to_datetime(df["date"])

        # 按股票分组批量计算滚动指标
        grouped = df.groupby("symbol")

        df["ma5"] = grouped["close"].transform(lambda x: x.rolling(5).mean())
        df["ma20"] = grouped["close"].transform(lambda x: x.rolling(20).mean())
        df["ma60"] = grouped["close"].transform(lambda x: x.rolling(60).mean())
        df["vol_ma20"] = grouped["volume"].transform(lambda x: x.rolling(20).mean())
        df["turnover_20"] = grouped["turnover"].transform(lambda x: x.rolling(20).mean())
        df["high_20_shifted"] = grouped["high"].transform(lambda x: x.shift(1).rolling(20).max())
        df["high_60"] = grouped["high"].transform(lambda x: x.rolling(60).max())
        df["low_60"] = grouped["low"].transform(lambda x: x.rolling(60).min())

        # 每只股票按日期排序后缓存最后 60 行（足以覆盖所有策略的 lookback）
        symbols: list[str] = []
        for symbol, gdf in df.groupby("symbol"):
            gdf = gdf.sort_values("date").tail(_MIN_BARS)
            if len(gdf) >= _MIN_BARS:
                self._cache[symbol] = gdf.reset_index(drop=True)
                symbols.append(symbol)

        self._symbols = symbols
        logger.info(
            f"指标缓存计算完成：{len(symbols)} 只股票"
            f"（核心窗口 {_MIN_BARS} 日）"
        )
        return symbols

    @property
    def symbols(self) -> list[str]:
        return self._symbols

    def get(self, symbol: str) -> pd.DataFrame | None:
        """返回某只股票的预计算 DataFrame（末尾 _MIN_BARS 行，含所有指标列）。"""
        return self._cache.get(symbol)
