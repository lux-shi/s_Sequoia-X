#!/usr/bin/env python3
"""Export Sequoia-X strategy picks as structured JSON for trading-strategy.

Writes: /home/dev/code/trading-intel/data/raw/{date}-sequoia-picks.json
Output is consumed by generate_trade_plan.py for candidate pool (section 3.2).
"""
import json
import os
import sys

from dotenv import load_dotenv
load_dotenv()

from sequoia_x.core.config import get_settings
from sequoia_x.data.engine import DataEngine
from sequoia_x.data.indicators import IndicatorCache
from sequoia_x.strategy.turtle_trade import TurtleTradeStrategy
from sequoia_x.strategy.ma_volume import MaVolumeStrategy
from sequoia_x.strategy.high_tight_flag import HighTightFlagStrategy
from sequoia_x.strategy.limit_up_shakeout import LimitUpShakeoutStrategy


def export(date_str: str, engine: DataEngine, cache: IndicatorCache) -> dict:
    settings = get_settings()
    strategies = [
        MaVolumeStrategy(engine=engine, settings=settings, cache=cache),
        TurtleTradeStrategy(engine=engine, settings=settings, cache=cache),
        HighTightFlagStrategy(engine=engine, settings=settings, cache=cache),
        LimitUpShakeoutStrategy(engine=engine, settings=settings, cache=cache),
    ]

    results: list[dict] = []
    for s in strategies:
        name = type(s).__name__
        codes = s.run()
        results.append({
            "strategy": name,
            "count": len(codes),
            "codes": codes,
            "source": "Sequoia-X quantitative screen",
        })
        print(f"  {name}: {len(codes)} picks", file=sys.stderr)

    return {"date": date_str, "strategies": results}


def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else None
    if not date_str:
        from datetime import date
        date_str = date.today().isoformat()

    settings = get_settings()
    engine = DataEngine(settings)
    cache = IndicatorCache(engine.db_path)
    cache.compute_all()

    picks = export(date_str, engine, cache)

    # Write to trading-strategy's consumption path
    out_dir = "/home/dev/code/trading-intel/data/raw"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{date_str}-sequoia-picks.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(picks, f, ensure_ascii=False, indent=2)
    print(f"Sequoia-X picks written to {out_path}", file=sys.stderr)

    # Also print compact summary
    for s in picks["strategies"]:
        codes = s["codes"][:5]
        print(f"  {s['strategy']}: {s['count']} picks {codes}{'...' if len(s['codes']) > 5 else ''}")


if __name__ == "__main__":
    main()
