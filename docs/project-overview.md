# Sequoia-X 项目总览

> 本文档描述 Sequoia-X 的定位、架构、现状和前进方向。
> 面向接手本仓库的新 agent 或协作者。

---

## 1. 一句话定位

Sequoia-X 是四仓库交易系统中的**量化初筛引擎**。它从全市场海量标的中，用技术策略筛选出每日值得关注的候选池，推送至飞书供人工研判。它不做交易决策，不接券商，不自动下单。

---

## 2. 在四仓库体系中的位置

```
trading-intel（信息层）
  │  采集信源 → 市场快照 → 板块热度 → 博主观点
  │
  ▼
Sequoia-X（初筛层）★ 本仓库
  │  全市场日K数据 → 技术策略筛选 → 候选池推送
  │
  ▼
trading-strategy（策略层）
  │  候选池深度研判 → 策略模型匹配 → 入场/出场条件
  │
  ▼
trading-os（执行层）
  │  交易宪法 → 风控门禁 → 仓位检查 → 日志复盘
  │
  ▼
trading-main（总控层）
     项目方向 → 决策记录 → 跨仓库协调
```

Sequoia-X 定位在 **intel 和 strategy 之间**：intel 告诉你"市场在发生什么"，Sequoia-X 告诉你"哪些票在技术上值得看"，strategy 告诉你"这个票能不能用你的策略做"。

---

## 3. 核心功能

| 功能 | 说明 |
|------|------|
| 数据回填 | 从 baostock 拉取全市场 ~5200 只 A 股历史日 K（后复权），存储于本地 SQLite |
| 每日增量 | 8 进程并行补今日数据，2-3 分钟完成 |
| 策略筛选 | 4 个技术策略并行运行，选出各自候选池 |
| 飞书推送 | 结果格式化为飞书卡片，按策略路由到不同 Webhook |

---

## 4. 当前策略

| 策略 | 平均日选出 | 状态 | 说明 |
|------|-----------|------|------|
| MaVolume | ~9 只 | ✅ 活跃 | 5日线上穿20日线 + 放量 1.5 倍 |
| TurtleTrade | ~30 只（Top 30） | ✅ 活跃 | 20日新高突破 + 多层质量过滤 |
| HighTightFlag | 0-2 只 | ✅ 低频 | 40天涨幅 > 60% + 10天收敛 < 15% |
| LimitUpShakeout | 0-2 只 | ✅ 低频 | 涨停次日放量洗盘回踩 |

已移除：RpsBreakout（噪音过大）、UptrendLimitDown（接飞刀风险）、PrivatePlacement（非选股策略）。

详见 [strategy-review.md](strategy-review.md)。

---

## 5. 架构

```
main.py（编排入口）
   ├── DataEngine         — SQLite存储 + baostock数据同步
   ├── IndicatorCache     — 一次全量加载，批量向量化计算核心指标
   ├── Strategy.*.run()   — 各自从缓存取指标，执行筛选逻辑
   └── FeishuNotifier     — 格式化飞书卡片 + POST推送
```

### 5.1 分层隔离原则

- **数据层不关心策略**：DataEngine 只负责存取，不知道哪些策略在用
- **策略层不关心推送**：run() 只返回 list[str]，不涉及通知逻辑
- **推送层不关心筛选**：FeishuNotifier 只接收结果 + 格式化，不参与选股
- **指标缓存不关心业务**：IndicatorCache 只提供预计算的 DataFrame，策略自行解读

### 5.2 添加新策略

只需两步：

1. 创建 `sequoia_x/strategy/my_strategy.py`，继承 `BaseStrategy`
2. 在 `main.py` 顶部加一行 `import sequoia_x.strategy.my_strategy`

策略自动注册，无需修改策略列表。

---

## 6. 与 trading-intel 的协同（规划中）

| 协同点 | 状态 | 说明 |
|--------|------|------|
| 市场背景标注 | 📋 规划 | 飞书卡片头部附加 intel 的市场快照摘要 |
| 风险模式过滤 | 📋 规划 | 跌停过多、炸板率过高时自动压制动量类策略 |
| 板块归因 | 💡 设想 | 选股结果按 intel 的领涨/领跌板块做交叉标注 |
| 博主交叉信号 | 💡 设想 | TGB 博主一致看多方向与选股结果做拥挤度提示 |

当前不做自动化 intel→strategy 管道，所有交叉引用由人工完成或在 Sequoia-X 侧"拉取参考"。

---

## 7. 部署与运行

### 环境

- Python ≥ 3.10
- 依赖：见 pyproject.toml
- 数据源：baostock（免费、无需注册）
- 通知：飞书 Webhook

### 命令

```bash
# 安装
uv sync --all-extras

# 配置飞书 Webhook
cp .env.example .env
# 编辑 .env，填入 FEISHU_WEBHOOK_URL

# 首次回填（一次性，约1-2小时）
python main.py --backfill

# 日常运行
python main.py

# 或使用一键脚本
./run.sh
```

### 定时任务

```cron
# 每个交易日 19:15 执行（收盘后）
15 19 * * 1-5 cd /root/code/external/Sequoia-X && ./run.sh
```

---

## 8. 前进方向

### 短期（当前阶段）

- [ ] 与 trading-intel 的市场快照做轻量集成（市场背景标注 + 风险过滤）
- [x] 策略审计与清洗（已完成 2026-05-17）
- [x] 架构分层优化（IndicatorCache + 自动注册，已完成 2026-05-17）
- [ ] TurtleTrade 进一步收紧（Top 15？行业分散？）

### 中期

- [ ] 新增 1-2 个策略（放量突破年线、杯柄形态）
- [ ] 策略回测框架（基于 baostock 历史数据验证策略表现）
- [ ] 策略表现追踪（每日选股 vs 实际走势的统计）

### 长期

- [ ] 策略参数自动优化（网格搜索/贝叶斯优化）
- [ ] 多策略组合信号（多个策略同时出票 = 高置信度）
- [ ] 与 trading-strategy 的结构化对接（Sequoia-X 输出直接进入 strategy 候选池）

### 不做的事

- ❌ 不接券商 API，不自动下单
- ❌ 不生成买卖建议
- ❌ 不绕过 trading-os 的风控门禁
- ❌ 不替代人工研判
- ❌ 不追求"选得最多"或"最精准"

---

## 9. 仓库信息

| 项目 | 值 |
|------|-----|
| 远程地址 | https://github.com/lux-shi/s_Sequoia-X |
| 上游来源 | https://github.com/sngyai/Sequoia-X |
| 分支 | master |
| 许可证 | MIT |

---

## 10. 修改记录

| 日期 | 内容 |
|------|------|
| 2026-05-17 | 创建本文档 |
| 2026-05-17 | 策略审计：移除 3 个低价值策略 |
| 2026-05-17 | 架构升级：IndicatorCache + 策略自动注册 |
| 2026-05-17 | TurtleTrade 改造：新增 4 层质量过滤 |

---

*本文档随 Sequoia-X 代码一同版本管理。重大方向变更需同步更新。*
