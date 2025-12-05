# 🧠 GSIN Trading Platform: Complete Brain & Database Technical Report

**Version:** 1.0  
**Date:** 2025-01-05  
**Purpose:** Comprehensive technical documentation for AI systems (Gemini, ChatGPT) to understand the entire Brain evolution system, database schema, thresholds, mutations, and data lifecycle.

---

## 📋 Table of Contents

1. [System Overview](#system-overview)
2. [Database Schema](#database-schema)
3. [Evolution Worker](#evolution-worker)
4. [Monitoring Worker](#monitoring-worker)
5. [Backtesting Engine](#backtesting-engine)
6. [Mutation Engine](#mutation-engine)
7. [Scoring System](#scoring-system)
8. [Strategy Status Lifecycle](#strategy-status-lifecycle)
9. [Thresholds & Parameters](#thresholds--parameters)
10. [MCN Integration](#mcn-integration)
11. [Data Lifecycle](#data-lifecycle)
12. [Lineage Tracking](#lineage-tracking)
13. [Royalty System](#royalty-system)

---

## 🎯 System Overview

### What is the "Brain"?

The **Brain** is a self-evolving genetic algorithm system that:
- **Evolves** trading strategies through mutation and selection
- **Backtests** strategies on historical data
- **Promotes** successful strategies through status levels (experiment → candidate → proposable)
- **Discards** poor-performing strategies
- **Learns** from all events via Memory Cluster Networks (MCN)
- **Tracks** strategy lineage to prevent legal disputes

### Core Components

1. **Evolution Worker** - Main genetic algorithm loop (runs every 8 minutes)
2. **Monitoring Worker** - Gatekeeper for new strategies (runs every 15 minutes)
3. **Backtest Engine** - Simulates strategy execution on historical data
4. **Mutation Engine** - Creates new strategies from existing ones
5. **MCN Adapter** - Records events and retrieves patterns for learning
6. **Status Manager** - Determines strategy promotion/demotion
7. **Scoring System** - Calculates unified 0-1 score for ranking

---

## 🗄️ Database Schema

### Core Tables

#### `user_strategies` (Primary Strategy Table)

**Purpose:** Stores all trading strategies with their evolution state.

**Critical Columns for Evolution:**

| Column | Type | Purpose | Default |
|--------|------|---------|---------|
| `id` | UUID (String) | Primary key | - |
| `user_id` | UUID (String) | Strategy owner | - |
| `name` | String(255) | Strategy name | - |
| `status` | String(32) | **CRITICAL** - Current status | `'experiment'` |
| `score` | Float | **CRITICAL** - Unified score (0-1) | `NULL` |
| `last_backtest_at` | Timestamp | **CRITICAL** - Last backtest time | `NULL` |
| `last_backtest_results` | JSONB | **CRITICAL** - Latest metrics | `NULL` |
| `train_metrics` | JSONB | **CRITICAL** - In-sample metrics | `NULL` |
| `test_metrics` | JSONB | **CRITICAL** - Out-of-sample metrics | `NULL` |
| `evolution_attempts` | Integer | **CRITICAL** - Mutation count | `0` |
| `is_proposable` | Boolean | **CRITICAL** - Can be proposed | `false` |
| `is_active` | Boolean | Active flag | `true` |
| `generalized` | Boolean | Multi-asset tested | `false` |
| `per_symbol_performance` | JSONB | Per-symbol metrics | `NULL` |
| `parameters` | JSON | Strategy parameters | `{}` |
| `ruleset` | JSON | Strategy logic/rules | `{}` |
| `created_at` | Timestamp | Creation time | `NOW()` |
| `updated_at` | Timestamp | Last update (auto) | `NOW()` |

**Indexes:**
- `idx_user_strategies_status` on `status`
- `idx_user_strategies_last_backtest_at` on `last_backtest_at`

**Status Values:**
- `"experiment"` - Newly created, not yet evaluated
- `"candidate"` - Passed initial backtest
- `"proposable"` - Ready to be proposed to users
- `"discarded"` - Failed criteria, marked inactive
- `"pending_review"` - New user upload, awaiting review
- `"duplicate"` - Matches existing strategy
- `"rejected"` - Failed sanity check

#### `strategy_lineage` (Parent-Child Relationships)

**Purpose:** Tracks genetic relationships between strategies (for mutations and crossovers).

| Column | Type | Purpose |
|--------|------|---------|
| `id` | UUID | Primary key |
| `parent_strategy_id` | UUID | Parent strategy (FK) |
| `child_strategy_id` | UUID | Child strategy (FK) |
| `mutation_type` | String(64) | Type: "mutation", "crossover", etc. |
| `mutation_params` | JSONB | Mutation parameters |
| `similarity_score` | Float | Similarity between parent/child |
| `creator_user_id` | UUID | User who created mutation |
| `royalty_percent_parent` | Float | Royalty % for parent creator |
| `royalty_percent_child` | Float | Royalty % for child creator |
| `created_at` | Timestamp | Creation time |

**Note:** Strategies do NOT have a direct `parent_id` column. Parent relationships are tracked via this table, allowing:
- Multiple parents (crossover mutations)
- Complex lineage trees
- Mutation history tracking

#### `strategy_backtests` (Backtest History)

**Purpose:** Stores historical backtest results (separate from `last_backtest_results` in `user_strategies`).

| Column | Type | Purpose |
|--------|------|---------|
| `id` | UUID | Primary key |
| `strategy_id` | UUID | Strategy (FK) |
| `symbol` | String(32) | Symbol tested |
| `timeframe` | String(16) | Timeframe (e.g., "1d") |
| `start_date` | Timestamp | Backtest start |
| `end_date` | Timestamp | Backtest end |
| `total_return` | Float | Return % |
| `win_rate` | Float | Win rate (0-1) |
| `max_drawdown` | Float | Max drawdown % |
| `sharpe_ratio` | Float | Sharpe ratio |
| `total_trades` | Integer | Number of trades |
| `results` | JSONB | Full backtest results |

**Note:** `last_backtest_results` in `user_strategies` stores the **latest** backtest. This table stores **all historical** backtests.

---

## 🔄 Evolution Worker

### Purpose

The Evolution Worker is the **main genetic algorithm loop** that:
1. Backtests all active strategies with updated data
2. Updates metrics and status (experiment → candidate → proposable)
3. Mutates poor/borderline strategies
4. Discards strategies that fail repeatedly
5. Records all events to MCN for learning

### Execution Schedule

- **Interval:** Every 8 minutes (480 seconds)
- **Configurable:** `EVOLUTION_INTERVAL_SECONDS` env var
- **Parallel Processing:** 3 strategies processed concurrently (`EVOLUTION_PARALLEL_WORKERS`)

### Rate Limiting

- **Twelve Data Credits:** 377 credits/minute (Grow plan)
- **Batch Size:** 50 strategies per cycle (configurable via `EVOLUTION_BATCH_SIZE`)
- **Max Per Cycle:** `min(EVOLUTION_BATCH_SIZE, 377 * 0.8) = 301` strategies

### Evolution Cycle Flow

```
1. Get all active strategies (is_active=true, status != 'discarded')
2. Prioritize strategies:
   - Highest: Never backtested (last_backtest_at == NULL)
   - Second: Old backtests (>7 days old)
   - Third: Experiment status
   - Lower: Already evaluated
3. Limit to MAX_REQUESTS_PER_CYCLE (respects rate limits)
4. Process strategies in parallel (3 workers)
5. For each strategy:
   a. Run backtest (200 days history, rolling walk-forward)
   b. Calculate unified score
   c. Determine new status
   d. Update database (score, status, metrics, evolution_attempts)
   e. Check if should mutate (attempts >= 3 OR winrate < 0.60)
   f. If mutate: Create 1-2 child strategies
   g. Check if should discard (attempts >= 10 OR fail-fast rules)
6. Enforce max strategies limit (keep top 100 by score)
7. Record events to MCN (non-blocking)
```

### Mutation Triggers

A strategy is mutated when:
- `evolution_attempts >= 3` (forced mutation)
- `win_rate < 0.60` AND status in `['experiment', 'candidate']` (poor performance)

**Mutation Types:**
- `parameter_tweak` - Adjust indicator parameters
- `indicator_substitution` - Replace indicators (SMA→EMA, RSI→MACD)
- `timeframe_change` - Change timeframe (1d→1h, etc.)
- `cross_asset_transplant` - Test on different symbols
- `crossover` - Combine two parent strategies

### Discard Rules (Fail-Fast)

A strategy is discarded when:
1. `evolution_attempts >= 10` (max attempts reached)
2. `sharpe_ratio < 0` AND `total_trades >= 50` (proven loser)
3. `evolution_attempts >= 5` AND `score < 0.20` (not learning)
4. `evolution_attempts >= 5` AND `win_rate < 0.50` AND `score < 0.40` AND `overfitting_detected` (consistently poor)

### Data Saved to Database

After each evolution cycle, the following is saved:
- `score` - Unified score (0-1)
- `status` - New status (if changed)
- `last_backtest_at` - Current timestamp
- `last_backtest_results` - Full backtest results (JSON)
- `train_metrics` - In-sample metrics (JSON)
- `test_metrics` - Out-of-sample metrics (JSON)
- `evolution_attempts` - Incremented by 1
- `is_proposable` - Boolean flag

**What is NOT saved:**
- `generation` - Calculated dynamically from `strategy_lineage` table
- `parent_id` - Tracked via `strategy_lineage` table (not direct column)

---

## 🔍 Monitoring Worker

### Purpose

The Monitoring Worker is the **gatekeeper** that:
1. Reviews new user-uploaded strategies (`pending_review` status)
2. Checks for duplicates using strategy fingerprinting
3. Runs basic sanity checks (lightweight backtest)
4. Computes robustness scores for existing strategies
5. Promotes candidate → proposable based on robustness
6. Discards strategies that consistently fail robustness checks
7. Sends notifications to users about status changes

### Execution Schedule

- **Interval:** Every 15 minutes (900 seconds)
- **Configurable:** `MONITORING_WORKER_INTERVAL_SECONDS` env var

### Monitoring Cycle Flow

```
1. Process pending_review strategies:
   a. Check for duplicates (strategy fingerprinting)
   b. Run sanity check (lightweight backtest, 10+ trades)
   c. Accept → experiment, Reject → rejected, Duplicate → duplicate
   
2. Compute robustness for experiment/candidate strategies:
   a. Calculate robustness score (0-100):
      - Regime diversity (tested across different volatility regimes)
      - Walk-forward stability (first half vs second half)
      - Parameter sensitivity (small perturbations)
   b. If robustness >= 70 AND meets thresholds → promote to proposable
   c. If robustness < 40 AND trades >= 20 AND cycles >= 3 → discard
   
3. Send notifications for status changes
```

### Sanity Check Thresholds

- **Min Trades:** 10 (increased from 3 to reduce gap with full backtest)
- **Max Drawdown:** 70% (very lenient)
- **Require No NaN:** True (must have valid data)

### Robustness Score Calculation

**Components:**
1. **Regime Diversity** - Tested across at least 2 different volatility regimes
2. **Walk-Forward Stability** - First half vs second half performance (50/50 split)
3. **Parameter Sensitivity** - Test 2 small perturbations (±5%)

**Score Range:** 0-100
- **70+** = Robust (can promote to proposable)
- **40-70** = Moderate (needs improvement)
- **<40** = Fragile (should discard if meets other criteria)

### Promotion to Proposable (Monitoring Worker)

A candidate strategy is promoted when:
- `robustness_score >= 70`
- `sharpe_ratio >= 1.0`
- `profit_factor >= 1.2`
- `max_drawdown <= 25%`
- `total_trades >= 20`

---

## 🧪 Backtesting Engine

### Purpose

The Backtest Engine simulates strategy execution on historical market data to calculate performance metrics.

### Data Source

- **Primary:** Twelve Data API (historical OHLCV)
- **Rate Limit:** 377 credits/minute
- **Max Candles:** 5000 per request

### Backtest Process

```
1. Normalize strategy ruleset (add default exit rules if missing)
2. Validate ruleset (must have entry/exit conditions)
3. Fetch historical candles (up to 5000, adapts to timeframe)
4. Split data:
   - Train: 70% (in-sample)
   - Test: 30% (out-of-sample)
   OR
   - Rolling Walk-Forward (if enabled):
     * Train: 12 months
     * Test: 3 months
     * Step: 3 months forward each iteration
5. Execute strategy simulation:
   a. Calculate indicators (SMA, EMA, RSI, MACD, etc.)
   b. Check entry conditions
   c. Execute trades (entry/exit)
   d. Track equity curve
6. Calculate metrics:
   - Win rate, Sharpe ratio, max drawdown
   - Profit factor, expectancy
   - Train metrics (in-sample)
   - Test metrics (out-of-sample)
7. Detect overfitting:
   - Compare train vs test metrics
   - Flag if test << train
8. Run Monte Carlo simulation (1000 iterations)
9. Return results dictionary
```

### Walk-Forward Analysis

**Purpose:** Prevent overfitting by testing on multiple time periods.

**Configuration:**
- **In-Sample:** 12 months (training)
- **Out-of-Sample:** 3 months (testing)
- **Step:** 3 months forward each iteration
- **Min Periods:** 1 (reduced from 3 for flexibility)
- **Min Data:** 3 months of data required

**Example:**
- Period 1: Train 2021, Test Q1 2022
- Period 2: Train 2021-Q1 2022, Test Q2-Q3 2022
- Period 3: Train 2021-Q3 2022, Test Q4 2022-Q1 2023

**Consistency Score:** How similar performance is across periods (0-1).

### Monte Carlo Simulation

**Purpose:** Test strategy robustness by simulating random trade sequences.

**Configuration:**
- **Simulations:** 1000 iterations
- **Method:** Randomly shuffle trade order, recalculate returns

**Metrics:**
- `mean_return` - Average return across simulations
- `std_return` - Standard deviation (lower = more robust)
- `percentile_5` - Worst-case scenario (5th percentile)

### Overfitting Detection

**Method:** Compare train vs test metrics.

**Flags:**
- `overfitting_detected = True` if:
  - Test win rate < 0.70 AND train win rate > 0.80
  - Test Sharpe < 0.5 AND train Sharpe > 1.5
  - Test return < 0 AND train return > 0.20

**Impact:** Overfit strategies are NOT promoted, even if they meet thresholds.

### Backtest Results Structure

```json
{
  "symbol": "AAPL",
  "timeframe": "1d",
  "start_date": "2023-01-01T00:00:00Z",
  "end_date": "2024-01-01T00:00:00Z",
  "total_trades": 150,
  "win_rate": 0.75,
  "total_return": 25.5,
  "sharpe_ratio": 1.8,
  "max_drawdown": 0.15,
  "profit_factor": 1.5,
  "expectancy": 0.02,
  "equity_curve": [...],
  "train_metrics": {
    "win_rate": 0.78,
    "total_return": 28.0,
    "sharpe_ratio": 2.0
  },
  "test_metrics": {
    "win_rate": 0.72,
    "total_return": 23.0,
    "sharpe_ratio": 1.6
  },
  "wfa_results": {
    "consistency_score": 0.85,
    "periods": [...]
  },
  "monte_carlo_results": {
    "mean_return": 24.0,
    "std_return": 5.0,
    "percentile_5": 15.0
  },
  "overfitting_detected": false,
  "score": 0.82
}
```

---

## 🧬 Mutation Engine

### Purpose

The Mutation Engine creates new strategies from existing ones using genetic algorithm techniques.

### Types

#### 1. Enhanced Mutation Engine (Primary)

**Algorithm:** Genetic Algorithm with Tournament Selection

**Parameters:**
- `mutation_rate = 0.2` (20% mutation rate)
- `crossover_rate = 0.7` (70% crossover rate)
- `elite_size = 0.1` (Top 10% are elite)

**Selection Method:** Tournament Selection (not top 10% elite)
- Pick 4 random strategies
- Select best from tournament
- Increases genetic diversity (prevents premature convergence)

**Mutation Types:**

1. **Parameter Tweak** - Adjust indicator parameters
   - Strength: Adaptive based on score
     - Score >= 0.8: ±5% (fine-tuning)
     - Score >= 0.6: ±10% (medium)
     - Score < 0.6: ±20% (exploration)

2. **Indicator Substitution** - Replace indicators
   - SMA ↔ EMA
   - RSI ↔ MACD
   - Random selection from indicator pool

3. **Timeframe Change** - Change timeframe
   - 1d ↔ 1h ↔ 15m ↔ 30m
   - Random selection

4. **Cross-Asset Transplant** - Test on different symbols
   - Move strategy to different asset
   - Tests generalization

5. **Crossover** - Combine two parents
   - Average numeric parameters
   - Random choice for categorical
   - Combine indicators from both parents

#### 2. Legacy Mutation Engine (Fallback)

**Simple mutations:**
- Parameter tweak
- Timeframe change
- Indicator threshold
- Trailing stop
- Volume threshold

### Mutation Creation

When a mutation is created:
1. New `UserStrategy` record is created
2. `StrategyLineage` record links parent → child
3. `evolution_attempts` of parent is incremented
4. Event recorded to MCN (non-blocking)

**Child Strategy Properties:**
- `status = 'experiment'` (starts fresh)
- `evolution_attempts = 0` (reset)
- `user_id = parent.user_id` (inherits owner)
- `name = "{parent.name} (Mutated)"`

---

## 📊 Scoring System

### Purpose

The Scoring System calculates a **unified score (0-1)** that ranks strategies for the Brain.

### Formula

```
score = (WIN_RATE_WEIGHT * win_rate_score)
      + (RISK_ADJUSTED_RETURN_WEIGHT * risk_adjusted_score)
      + ((1 - DRAWDOWN_PENALTY_WEIGHT) * drawdown_score)
      + (STABILITY_WEIGHT * stability_score)
      + (SHARPE_BONUS_WEIGHT * sharpe_score)
      + (WFA_WEIGHT * wfa_score)
      + (MC_WEIGHT * mc_score)
```

**Weights:**
- `WIN_RATE_WEIGHT = 0.30` (30%)
- `RISK_ADJUSTED_RETURN_WEIGHT = 0.20` (20%)
- `DRAWDOWN_PENALTY_WEIGHT = 0.20` (20% penalty)
- `STABILITY_WEIGHT = 0.15` (15%)
- `SHARPE_BONUS_WEIGHT = 0.05` (5%)
- `WFA_WEIGHT = 0.10` (10%)
- `MC_WEIGHT = 0.10` (10%)

### Component Calculations

1. **Win Rate Score** (0-1)
   - Direct: `win_rate_score = win_rate`
   - High win rate is critical

2. **Risk-Adjusted Return Score** (0-1)
   - Uses CAGR normalized by volatility
   - `risk_adjusted_return = CAGR / (volatility * 100)`
   - Normalized to 0-1 range

3. **Drawdown Score** (0-1)
   - Exponential penalty: `exp(-max_drawdown * 2.0)`
   - 0% drawdown = 1.0
   - 50%+ drawdown ≈ 0.0

4. **Stability Score** (0-1)
   - Calculated from equity curve
   - Coefficient of variation (lower = more stable)
   - `stability = exp(-cv)`

5. **Sharpe/Sortino Score** (0-1)
   - Prefers Sortino (penalizes downside only)
   - Normalized: `(ratio / 3.0) + 0.5`

6. **Walk-Forward Consistency Score** (0-1)
   - From WFA results
   - How similar performance is across periods
   - Normalized from -1 to 1 → 0 to 1

7. **Monte Carlo Robustness Score** (0-1)
   - Lower variance = higher score
   - Penalizes negative worst-case (5th percentile)
   - `robustness = 1.0 / (1.0 + (std / 50.0))`

### Score Interpretation

- **0.9+** = Elite strategy (highly proposable)
- **0.7-0.9** = Good strategy (proposable with caution)
- **0.5-0.7** = Acceptable (needs improvement)
- **<0.5** = Poor (should be discarded or heavily mutated)

### Usage

- **Ranking:** Strategies sorted by score (descending)
- **Selection:** Top strategies selected for mutation/crossover
- **Promotion:** Score >= 0.70 required for proposable status
- **Discard:** Score < 0.20 after 5+ attempts = discard

---

## 🔄 Strategy Status Lifecycle

### Status Transitions

```
pending_review → [duplicate|rejected|experiment]
experiment → candidate → proposable
proposable → candidate (if metrics degrade)
any → discarded (if fail criteria)
```

### Transition Rules

#### Experiment → Candidate

**Requirements:**
- `total_trades >= 50`
- `win_rate >= 0.75` (75%)
- `max_drawdown <= 0.30` (30%)

**Action:** Status updated to `'candidate'`, `is_proposable = false`

#### Candidate → Proposable

**Two Paths (Flexible Thresholds):**

**Path 1: High Win Rate**
- `total_trades >= 50`
- `win_rate >= 0.80` (80%)
- `sharpe_ratio >= 1.0`
- `profit_factor >= 1.2`
- `max_drawdown <= 0.20` (20%)
- `score >= 0.70`
- `test_win_rate >= 0.70` (anti-overfitting)

**Path 2: High Sharpe**
- `total_trades >= 50`
- `win_rate >= 0.60` (60%)
- `sharpe_ratio >= 1.5`
- `profit_factor >= 1.2`
- `max_drawdown <= 0.20` (20%)
- `score >= 0.70`
- `test_win_rate >= 0.70` (anti-overfitting)

**MCN Requirements (if DB available):**
- `regime_stability_score >= 0.75` (75%)
- `overfitting_risk == "Low"`

**Action:** Status updated to `'proposable'`, `is_proposable = true`

#### Proposable → Candidate (Demotion)

**Buffer Zone:** Demotion thresholds are lower than promotion to prevent oscillation.

**Demote if:**
- `win_rate < 0.70` (buffer: 0.80 → 0.70)
- `sharpe_ratio < 0.5` (buffer: 1.0 → 0.5)
- `score < 0.60` (buffer: 0.70 → 0.60)
- `max_drawdown > 0.30` (buffer: 0.20 → 0.30)
- `total_trades < 50`

**Action:** Status updated to `'candidate'`, `is_proposable = false`

#### Any → Discarded

**Discard Rules:**
1. `evolution_attempts >= 10` (max attempts)
2. `sharpe_ratio < 0` AND `total_trades >= 50` (proven loser)
3. `evolution_attempts >= 5` AND `score < 0.20` (not learning)
4. `evolution_attempts >= 5` AND `win_rate < 0.50` AND `score < 0.40` AND `overfitting_detected` (consistently poor)

**Action:** Status updated to `'discarded'`, `is_active = false`

---

## ⚙️ Thresholds & Parameters

### Evolution Phases

The system adapts thresholds based on evolution phase:

#### Phase 0: Cold Start
- `winrate_min = 0.25` (25%)
- `sharpe_min = 0.2`
- `trades_min = 5`

#### Phase 1: Growth
- `winrate_min = 0.55` (55%)
- `sharpe_min = 0.5`
- `trades_min = 10`

#### Phase 2: Mature
**Path 1: High Win Rate**
- `winrate_min = 0.80` (80%)
- `sharpe_min = 1.0`
- `trades_min = 30`
- `max_drawdown_max = 10.0%`

**Path 2: High Sharpe**
- `winrate_min = 0.55` (55%)
- `sharpe_min = 1.5`
- `trades_min = 30`
- `max_drawdown_max = 10.0%`

### Configuration Constants

**Evolution Worker:**
- `EVOLUTION_INTERVAL_SECONDS = 480` (8 minutes)
- `MAX_EVOLUTION_ATTEMPTS = 10`
- `MAX_STRATEGIES_TO_MAINTAIN = 100`
- `MIN_TRADES_FOR_CANDIDATE = 50`
- `EVOLUTION_BATCH_SIZE = 50` (configurable)
- `PARALLEL_WORKERS = 3`

**Monitoring Worker:**
- `MONITORING_WORKER_INTERVAL_SECONDS = 900` (15 minutes)
- `SANITY_CHECK_MIN_TRADES = 10`
- `SANITY_CHECK_MAX_DRAWDOWN = 0.70` (70%)
- `MONITORING_ROBUSTNESS_SCORE_MIN = 70`
- `MONITORING_DISCARD_ROBUSTNESS_THRESHOLD = 40`
- `MONITORING_DISCARD_MIN_TRADES = 20`
- `MONITORING_DISCARD_MIN_EVALUATION_CYCLES = 3`

**Backtesting:**
- `train_test_split = 0.7` (70% train, 30% test)
- `walk_forward_in_sample_months = 12`
- `walk_forward_out_of_sample_months = 3`
- `walk_forward_step_months = 3`
- `monte_carlo_simulations = 1000`

**Mutation:**
- `mutation_rate = 0.2` (20%)
- `crossover_rate = 0.7` (70%)
- `elite_size = 0.1` (10%)

---

## 🧠 MCN Integration

### Purpose

Memory Cluster Networks (MCN) is a custom AI system that:
- **Records** all events (backtests, mutations, trades)
- **Learns** patterns from historical data
- **Retrieves** similar strategies/events for recommendations
- **Tracks** strategy lineage and overfitting risk

### Event Types Recorded

1. **Strategy Events:**
   - `strategy_created` - New strategy created
   - `strategy_backtest` - Backtest completed
   - `strategy_mutated` - Mutation created
   - `strategy_discarded` - Strategy discarded
   - `strategy_promoted` - Status changed

2. **Trade Events:**
   - `trade_executed` - Trade executed
   - `trade_signal` - Signal generated
   - `signal_generated` - AI signal created

3. **Market Events:**
   - `market_snapshot` - Market data snapshot
   - `regime_detected` - Market regime detected
   - `market_pattern` - Pattern identified

4. **User Events:**
   - `user_action` - User interaction
   - `user_preference` - Preference updated
   - `user_risk_update` - Risk profile changed

### Data Storage

**MCN Storage:**
- **Format:** NumPy arrays (`.npz` files)
- **Location:** `mcn_store/` directory
- **Categories:** Separate MCNs for regime, strategy, user, market, trade
- **Backup:** Automatic backups before mutations

**What is Saved:**
- Event vectors (embeddings)
- Metadata (strategy_id, timestamp, payload)
- Clusters (similar events grouped)
- Value scores (importance weighting)

**What is NOT Saved:**
- Full strategy rulesets (only embeddings)
- Full backtest results (only metrics)
- User personal data (only anonymized patterns)

### MCN Usage

**For Strategy Promotion:**
- Retrieve lineage memory (ancestor stability, overfitting risk)
- Check regime stability score
- Determine if strategy has overfit ancestors

**For Recommendations:**
- Find similar strategies based on embeddings
- Get historical patterns for similar strategies
- Calculate MCN similarity score

**For Learning:**
- Record all backtest results
- Record all mutations
- Learn which mutations work best
- Learn which strategies perform well in which regimes

### MCN Backup

**Frequency:** Before each evolution cycle
**Location:** `data/mcn_backups/`
**Format:** Timestamped `.npz` files
**Retention:** All backups kept (no automatic deletion)

---

## 📅 Data Lifecycle

### Creation

**Strategies Created When:**
1. User uploads strategy → `status = 'pending_review'`
2. Evolution worker mutates strategy → `status = 'experiment'`
3. Seed loader creates initial strategies → `status = 'experiment'`

**Initial Values:**
- `status = 'experiment'` (or `'pending_review'` for uploads)
- `evolution_attempts = 0`
- `score = NULL`
- `is_proposable = false`
- `is_active = true`
- `created_at = NOW()`

### Updates

**Updated Every Evolution Cycle:**
- `score` - Recalculated from backtest
- `last_backtest_at` - Current timestamp
- `last_backtest_results` - Latest backtest results
- `train_metrics` - In-sample metrics
- `test_metrics` - Out-of-sample metrics
- `evolution_attempts` - Incremented by 1
- `updated_at` - Auto-updated via trigger

**Updated on Status Change:**
- `status` - New status
- `is_proposable` - Boolean flag
- `updated_at` - Auto-updated

**Updated on Mutation:**
- Parent: `evolution_attempts` incremented
- Child: New record created

### Deletion

**Strategies are NEVER deleted from database.**

**Instead:**
- `status = 'discarded'` (soft delete)
- `is_active = false` (filtered out of queries)

**Why:**
- Preserve lineage history
- Legal compliance (royalty tracking)
- Audit trail

**Exception:**
- User-uploaded strategies can be deleted by user (hard delete)
- But evolution-generated strategies are never deleted

### Decay

**No automatic decay mechanism.**

**However:**
- Strategies with `last_backtest_at > 7 days` are prioritized for re-evaluation
- Discarded strategies (`is_active = false`) are excluded from evolution cycles
- Old backtest results are replaced (not accumulated)

### Cleanup

**What Gets Cleaned:**
- Expired OTP codes (email verification)
- Expired cache entries (Redis)
- Old MCN backups (manual, not automatic)

**What Does NOT Get Cleaned:**
- Strategies (even discarded ones)
- Backtest history
- Lineage records
- MCN events

---

## 🌳 Lineage Tracking

### Purpose

Track genetic relationships between strategies to:
- Prevent legal disputes (prove originality)
- Calculate royalties (mutations from user strategies)
- Visualize evolution tree
- Detect overfitting (ancestor stability)

### How It Works

**No Direct `parent_id` Column:**
- Parent relationships tracked via `strategy_lineage` table
- Allows multiple parents (crossover mutations)

**Lineage Record Creation:**
- Created when mutation/crossover occurs
- Links `parent_strategy_id` → `child_strategy_id`
- Stores `mutation_type`, `mutation_params`, `similarity_score`

**Generation Calculation:**
- **NOT stored** in database
- Calculated dynamically by traversing `strategy_lineage` table
- Counts number of mutations from original strategy

**Example:**
```
Original Strategy (gen 0)
  └─ Mutation 1 (gen 1)
      └─ Mutation 2 (gen 2)
          ├─ Crossover with Other (gen 3)
          └─ Mutation 3 (gen 3)
```

### Lineage Queries

**Get Parent:**
```python
parent_lineages = crud.get_strategy_lineages_by_child(db, strategy_id)
parent_id = parent_lineages[0].parent_strategy_id
```

**Get Children:**
```python
child_lineages = crud.get_strategy_lineages_by_parent(db, strategy_id)
child_ids = [l.child_strategy_id for l in child_lineages]
```

**Get Original Strategy:**
```python
# Recursively traverse backwards
original_id = find_original_strategy(strategy_id, db)
```

**Count Mutations:**
```python
# Count lineage depth from original
mutation_count = count_mutations_from_original(original_id, current_id, db)
```

### Royalty Eligibility

**Determined by:**
- Mutation count from original
- Similarity score (how different from original)
- Mutation type (crossover vs mutation)

**Rules:**
- < 3 mutations: User gets royalty
- >= 3 mutations: Brain-generated (no user royalty)
- Similarity < 0.5: Too different (no user royalty)

---

## 💰 Royalty System

### Purpose

Track and distribute royalties when user-uploaded strategies are mutated and used profitably.

### Royalty Calculation

**When Royalty is Paid:**
- User strategy is mutated
- Mutated strategy generates profit
- Original strategy creator gets royalty

**Royalty Percentage:**
- Determined by mutation count and similarity
- Decreases with each mutation
- Stops after 3+ mutations or similarity < 0.5

**Royalty Tracking:**
- `strategy_lineage.royalty_percent_parent` - % for parent creator
- `strategy_lineage.royalty_percent_child` - % for child creator
- `royalty_ledger` table - Records all royalty payments

### Mutation Royalty Calculator

**Eligibility Check:**
```python
royalty_eligibility = mutation_royalty_calculator.determine_royalty_eligibility(
    original_dict,
    mutated_dict,
    mutation_count
)
```

**Returns:**
- `is_eligible` - Boolean
- `royalty_percent` - Percentage (0-5%)
- `is_brain_generated` - Boolean (too mutated)

**Rules:**
- Mutation count < 3: Eligible
- Similarity >= 0.5: Eligible
- Otherwise: Brain-generated (no royalty)

---

## 📝 Summary

### Key Takeaways

1. **Strategies are NEVER deleted** - Only soft-deleted (`status = 'discarded'`, `is_active = false`)

2. **Generation is NOT stored** - Calculated dynamically from `strategy_lineage` table

3. **Parent relationships use `strategy_lineage` table** - Not direct `parent_id` column

4. **Evolution runs every 8 minutes** - Processes up to 301 strategies per cycle (rate-limited)

5. **Monitoring runs every 15 minutes** - Reviews new uploads and computes robustness

6. **MCN records all events** - But doesn't store full data (only embeddings and metrics)

7. **Status transitions have buffer zones** - Demotion thresholds lower than promotion (prevents oscillation)

8. **Two promotion paths** - High win rate (80%+) OR high Sharpe (1.5+) with 60%+ win rate

9. **Fail-fast discard rules** - Discard proven losers early (negative Sharpe, not learning)

10. **Tournament selection** - Not top 10% elite (increases genetic diversity)

### Critical Database Columns

**Must exist for evolution to work:**
- `status` - Tracks promotion state
- `score` - Unified ranking score
- `last_backtest_results` - Latest metrics
- `evolution_attempts` - Mutation count
- `is_proposable` - Promotion flag

**Calculated, not stored:**
- `generation` - From `strategy_lineage` traversal
- `parent_id` - From `strategy_lineage` queries

### Data Retention

- **Strategies:** Forever (never deleted)
- **Backtests:** Latest in `last_backtest_results`, all in `strategy_backtests` table
- **Lineage:** Forever (legal compliance)
- **MCN Events:** Forever (learning data)
- **MCN Backups:** All kept (manual cleanup)

---

**End of Report**

This report provides complete understanding of the Brain evolution system, database schema, thresholds, mutations, and data lifecycle. Use this as reference for understanding the entire system architecture.

