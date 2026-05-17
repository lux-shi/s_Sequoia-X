"""Sequoia-X V2 主程序入口。

两种运行模式：
  python main.py               # 日常模式：8进程增量补数据 + 跑策略 + 飞书推送
  python main.py --backfill    # 回填模式：baostock 拉全市场历史K线（首次用，约12分钟）

新策略只需：
  1. 在 sequoia_x/strategy/ 下创建文件，继承 BaseStrategy
  2. 实现 run() 方法，设置 webhook_key
  3. 启动时自动被发现和运行，无需修改本文件
"""

import argparse
import sys
from dotenv import load_dotenv
load_dotenv()

import socket
socket.setdefaulttimeout(10.0)

from sequoia_x.core.config import get_settings
from sequoia_x.core.logger import get_logger
from sequoia_x.data.engine import DataEngine
from sequoia_x.data.indicators import IndicatorCache
from sequoia_x.notify.feishu import FeishuNotifier
from sequoia_x.strategy.base import BaseStrategy

# 导入策略模块，触发 __init_subclass__ 注册
import sequoia_x.strategy.high_tight_flag     # noqa: F401
import sequoia_x.strategy.limit_up_shakeout   # noqa: F401
import sequoia_x.strategy.ma_volume           # noqa: F401
import sequoia_x.strategy.turtle_trade        # noqa: F401


def main() -> None:
    parser = argparse.ArgumentParser(description="Sequoia-X V2 选股系统")
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="回填模式：通过 baostock 拉取全市场历史 K 线",
    )
    args = parser.parse_args()

    try:
        settings = get_settings()
        logger = get_logger(__name__)
        logger.info("Sequoia-X V2 启动")

        engine = DataEngine(settings)

        if args.backfill:
            logger.info("进入回填模式...")
            all_symbols = engine.get_all_symbols()
            engine.backfill(all_symbols)
            logger.info("Sequoia-X V2 回填模式运行完成")
            return

        # ── 日常模式：增量补数据 → 指标缓存 → 策略 → 推送 ──
        logger.info("开始拉取最新快照...")
        count = engine.sync_today_bulk()
        logger.info(f"快照同步完成，写入 {count} 只股票")

        # 共享指标缓存（一次全量 + 批量计算，策略层复用）
        cache = IndicatorCache(engine.db_path)
        cache.compute_all()

        # 自动发现并实例化所有已注册策略
        strategy_classes = BaseStrategy.get_strategies()
        active = [cls for cls in strategy_classes if cls.enabled]

        if not active:
            logger.warning("未发现任何已注册策略")
            return

        strategies = [
            cls(engine=engine, settings=settings, cache=cache)
            for cls in active
        ]

        notifier = FeishuNotifier(settings)

        for strategy in strategies:
            strategy_name = type(strategy).__name__
            logger.info(f"执行策略：{strategy_name}")

            selected: list[str] = strategy.run()
            logger.info(f"{strategy_name} 选出 {len(selected)} 只股票")

            if selected:
                notifier.send(
                    symbols=selected,
                    strategy_name=strategy_name,
                    webhook_key=strategy.webhook_key,
                )
            else:
                logger.info(f"{strategy_name} 无选股结果，跳过推送")

    except Exception:
        try:
            _logger = get_logger(__name__)
            _logger.exception("主流程发生未捕获异常，程序终止")
        except Exception:
            import traceback
            traceback.print_exc()
        sys.exit(1)

    logger.info("Sequoia-X V2 运行完成")


if __name__ == "__main__":
    main()
