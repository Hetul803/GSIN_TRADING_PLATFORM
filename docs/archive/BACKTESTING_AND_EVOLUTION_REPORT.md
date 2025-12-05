# GSIN Backtesting and Evolution System - Complete Report

## Executive Summary

This report provides a comprehensive explanation of how the GSIN platform's backtesting and strategy evolution system works. It covers the complete lifecycle of strategies from creation to mutation, including how the Memory Cluster Network (MCN) learns from and influences strategy development.

---

## Table of Contents

1. [Strategy Lifecycle Overview](#1-strategy-lifecycle-overview)
2. [Backtesting Process - End to End](#2-backtesting-process---end-to-end)
3. [MCN Integration and Storage](#3-mcn-integration-and-storage)
4. [Strategy Status Management](#4-strategy-status-management)
5. [Evolution Worker Cycle](#5-evolution-worker-cycle)
6. [Mutation Engine](#6-mutation-engine)
7. [Complete Flow Diagrams](#7-complete-flow-diagrams)

---

## 1. Strategy Lifecycle Overview

### Strategy Types

**Strategy A: User-Uploaded Strategy**
- Created by a user through the `/strategies/upload` endpoint
- Initially has status: `experiment`
- Has `user_id` pointing to the creator
- No backtest results initially (`last_backtest_at = null`)
- `evolution_attempts = 0`

**Strategy B: Preseeded Strategy**
- Loaded from seed files during system initialization
- Created by system user (special user ID for Brain-generated strategies)
- Initially has status: `experiment` or `candidate` (depending on seed data)
- May have initial backtest results if seed file includes them
- `evolution_attempts = 0`

### Initial State Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    STRATEGY CREATION                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────┴─────────────────────┐
        │                                           │
        ▼                                           ▼
┌───────────────┐                          ┌───────────────┐
│ Strategy A    │                          │ Strategy B    │
│ (User Upload) │                          │ (Preseeded)   │
├───────────────┤                          ├───────────────┤
│ user_id: U1   │                          │ user_id: SYS  │
│ status:       │                          │ status:       │
│   experiment  │                          │   experiment  │
│ score: null   │                          │ score: null   │
│ last_backtest │                          │ last_backtest │
│   _at: null   │                          │   _at: null   │
│ evolution_    │                          │ evolution_    │
│   attempts: 0 │                          │   attempts: 0 │
└───────────────┘                          └───────────────┘
        │                                           │
        └───────────────────┬───────────────────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │  Evolution Worker     │
                │  (Runs every 2 min)   │
                └───────────────────────┘
```

---

## 2. Backtesting Process - End to End

### 2.1 Backtest Trigger

Backtests are triggered in two ways:

1. **Manual Backtest**: User clicks "Run Backtest" on strategy detail page
   - Creates a job in `BacktestWorker`
   - Returns immediately with `job_id`
   - Frontend polls for status

2. **Automatic Backtest**: Evolution Worker runs every 2 minutes
   - Processes strategies in priority order
   - Runs backtests in parallel (up to 5 concurrent)

### 2.2 Complete Backtest Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    BACKTEST EXECUTION FLOW                      │
└─────────────────────────────────────────────────────────────────┘

STEP 1: Strategy Selection
──────────────────────────
Evolution Worker queries database:
  - Filters: is_active = true, status != 'discarded'
  - Priority order:
    1. Never backtested (last_backtest_at = null)  ← Highest
    2. Old backtests (>7 days old)
    3. Experiment status
    4. Others

STEP 2: Market Data Fetching
─────────────────────────────
BacktestEngine requests historical data:
  - Symbol: From strategy.ruleset (e.g., "AAPL")
  - Timeframe: From strategy.ruleset (e.g., "1d")
  - Date Range: Last 200 days (to account for weekends/holidays)
  - Provider: Twelve Data (primary), with fallbacks

  Market Data Provider Flow:
    ┌─────────────┐
    │ Twelve Data │ ← Primary (377 credits/min limit)
    └──────┬──────┘
           │ (if fails)
           ▼
    ┌─────────────┐
    │   Alpaca    │ ← Fallback 1
    └──────┬──────┘
           │ (if fails)
           ▼
    ┌─────────────┐
    │   Polygon   │ ← Fallback 2
    └──────┬──────┘
           │ (if fails)
           ▼
    ┌─────────────┐
    │   Finnhub   │ ← Fallback 3
    └──────┬──────┘
           │ (if fails)
           ▼
    ┌─────────────┐
    │   Yahoo     │ ← Fallback 4 (free, less reliable)
    └─────────────┘

STEP 3: Strategy Execution Simulation
──────────────────────────────────────
BacktestEngine._execute_strategy():

  For each candle in historical data:
    1. Calculate indicators:
       - SMA (Simple Moving Average)
       - EMA (Exponential Moving Average)
       - RSI (Relative Strength Index)
       - MACD (Moving Average Convergence Divergence)
       - ATR (Average True Range)
       - Bollinger Bands
       - Volume indicators

    2. Parse ruleset:
       - Entry conditions (e.g., "RSI < 30 AND SMA(20) > SMA(50)")
       - Exit rules (stop loss, take profit, trailing stop)
       - Position sizing rules

    3. Check entry conditions:
       - If conditions met AND no open position:
         → Open position (BUY or SELL)
         → Set stop_loss and take_profit
         → Record entry_price, entry_time

    4. Check exit conditions:
       - If position open:
         → Check stop_loss hit?
         → Check take_profit hit?
         → Check trailing_stop hit?
         → Check exit conditions (e.g., "RSI > 70")
         → If any exit condition met:
           → Close position
           → Calculate P&L (percentage)
           → Record trade

STEP 4: Trade List Generation
──────────────────────────────
Result: List of trades with:
  - entry_time, exit_time
  - entry_price, exit_price
  - pnl (percentage return)
  - side (BUY/SELL)
  - symbol
  - stop_loss, take_profit (if used)

STEP 5: Metrics Calculation
─────────────────────────────
BacktestEngine._calculate_metrics():

  Input: List of trades
  Output: Comprehensive metrics

  Calculations:
    ┌─────────────────────────────────────────┐
    │ Basic Metrics                           │
    ├─────────────────────────────────────────┤
    │ • total_return = sum(all pnl)           │
    │ • win_rate = winning_trades / total      │
    │ • avg_pnl = mean(all pnl)               │
    │ • total_trades = count(trades)          │
    │                                         │
    │ • avg_win = mean(winning pnl)           │
    │ • avg_loss = abs(mean(losing pnl))     │
    │ • profit_factor = total_wins /          │
    │                    total_losses         │
    │                                         │
    │ • max_drawdown = max(peak - trough)     │
    │   (calculated from equity curve)       │
    │                                         │
    │ • sharpe_ratio = avg_pnl / std_pnl      │
    │   (risk-adjusted return)               │
    │                                         │
    │ • sortino_ratio = avg_return /          │
    │                    downside_std         │
    │   (only penalizes downside volatility) │
    └─────────────────────────────────────────┘

    ┌─────────────────────────────────────────┐
    │ Advanced Metrics                       │
    ├─────────────────────────────────────────┤
    │ • Equity Curve:                        │
    │   - Starting capital: $100,000         │
    │   - For each trade:                    │
    │     equity += (pnl% * capital)          │
    │   - Result: Array of {timestamp,       │
    │              equity} points            │
    │                                         │
    │ • Train/Test Split (70/30):            │
    │   - Split trades chronologically       │
    │   - Train: First 70% of trades         │
    │   - Test: Last 30% of trades           │
    │   - Calculate metrics for both         │
    │                                         │
    │ • Overfitting Detection:               │
    │   - If test_winrate < train_winrate *  │
    │     0.8: Overfitting detected          │
    │                                         │
    │ • Monte Carlo Simulation:              │
    │   - Run 1000 simulations               │
    │   - Randomly shuffle trade order       │
    │   - Calculate distribution of returns  │
    │   - Get 5th percentile (worst case)   │
    │                                         │
    │ • Walk-Forward Analysis:               │
    │   - Split into multiple periods        │
    │   - Test on each period                │
    │   - Calculate consistency score        │
    └─────────────────────────────────────────┘

STEP 6: Unified Score Calculation
───────────────────────────────────
ScoringEngine.score_strategy():

  Formula:
    score = (win_rate * 0.30) +
            (risk_adj_return * 0.20) -
            (drawdown_penalty * 0.20) +
            (stability * 0.15) +
            (sharpe_bonus * 0.05) +
            (wfa_consistency * 0.10) +
            (mc_robustness * 0.10)

  Where:
    - win_rate: 0-1 (normalized)
    - risk_adj_return: CAGR normalized by volatility
    - drawdown_penalty: max_drawdown / 0.50 (capped at 1.0)
    - stability: Low variance in monthly returns
    - sharpe_bonus: sharpe_ratio / 3.0 (capped at 1.0)
    - wfa_consistency: From walk-forward analysis
    - mc_robustness: From Monte Carlo simulation

  Result: Score between 0.0 and 1.0
    - 0.9+ = Elite (highly proposable)
    - 0.7-0.9 = Good (proposable with caution)
    - 0.5-0.7 = Acceptable (needs improvement)
    - <0.5 = Poor (should be discarded)

STEP 7: Database Update
────────────────────────
Backtest results saved to:
  1. StrategyBacktest table (historical record)
  2. UserStrategy.last_backtest_results (latest results)
  3. UserStrategy.last_backtest_at (timestamp)
  4. UserStrategy.score (unified score)

STEP 8: MCN Event Recording
────────────────────────────
MCNAdapter.record_event():

  Event Type: "strategy_backtest"
  Payload:
    {
      "strategy_id": "...",
      "win_rate": 0.75,
      "sharpe_ratio": 1.5,
      "total_return": 15.2,
      "max_drawdown": -8.5,
      "total_trades": 45,
      "score": 0.82,
      "status": "candidate",
      "timestamp": "2024-01-15T10:30:00Z"
    }

  MCN Processing:
    1. Convert payload to text representation
    2. Generate embedding vector (384-dim → 32-dim)
    3. Store in MCN with metadata:
       - event_type
       - strategy_id
       - user_id
       - timestamp
       - payload (full JSON)
    4. Auto-save to disk every 10 events
```

### 2.3 Backtest Result Structure

```json
{
  "total_return": 15.2,
  "win_rate": 0.75,
  "max_drawdown": -8.5,
  "avg_pnl": 0.34,
  "sharpe_ratio": 1.5,
  "sortino_ratio": 2.1,
  "profit_factor": 2.3,
  "total_trades": 45,
  "winning_trades": 34,
  "losing_trades": 11,
  "avg_win": 0.52,
  "avg_loss": -0.23,
  "equity_curve": [
    {"timestamp": "2024-01-01T00:00:00Z", "equity": 100000},
    {"timestamp": "2024-01-02T00:00:00Z", "equity": 100500},
    ...
  ],
  "train_metrics": {
    "win_rate": 0.78,
    "total_return": 12.5,
    ...
  },
  "test_metrics": {
    "win_rate": 0.70,
    "total_return": 2.7,
    ...
  },
  "overfitting_detected": false,
  "monte_carlo_results": {
    "mean_return": 14.8,
    "std_return": 3.2,
    "percentile_5": 8.5
  },
  "wfa_results": {
    "consistency_score": 0.85
  },
  "score": 0.82
}
```

---

## 3. MCN Integration and Storage

### 3.1 What MCN Stores

MCN (Memory Cluster Network) is a vector-based memory system that learns from historical patterns. It stores:

**Event Types Recorded:**

1. **strategy_backtest**
   - When: After every backtest completes
   - Who: Evolution Worker, Brain Service, Manual backtest
   - Payload:
     ```json
     {
       "strategy_id": "uuid",
       "win_rate": 0.75,
       "sharpe_ratio": 1.5,
       "total_return": 15.2,
       "max_drawdown": -8.5,
       "total_trades": 45,
       "score": 0.82,
       "status": "candidate"
     }
     ```

2. **strategy_mutated**
   - When: After mutation creates new strategy
   - Who: Evolution Worker, Brain Service
   - Payload:
     ```json
     {
       "parent_strategy_id": "uuid",
       "child_strategy_id": "uuid",
       "mutation_type": "parameter_tweak",
       "mutation_params": {"changed": ["sma_period", "rsi_threshold"]}
     }
     ```

3. **trade_executed**
   - When: When user executes a trade
   - Who: Broker Router
   - Payload:
     ```json
     {
       "trade_id": "uuid",
       "strategy_id": "uuid",
       "symbol": "AAPL",
       "side": "BUY",
       "entry_price": 150.25,
       "pnl": 2.5,
       "timestamp": "2024-01-15T10:30:00Z"
     }
     ```

4. **market_snapshot**
   - When: When regime is detected
   - Who: Regime Detector
   - Payload:
     ```json
     {
       "symbol": "AAPL",
       "regime": "bull",
       "volatility": 0.15,
       "momentum": 0.05,
       "trend_strength": 0.8
     }
     ```

5. **signal_generated**
   - When: When Brain generates trading signal
   - Who: Brain Service
   - Payload:
     ```json
     {
       "strategy_id": "uuid",
       "symbol": "AAPL",
       "side": "BUY",
       "confidence": 0.85,
       "entry": 150.25,
       "stop_loss": 145.00,
       "take_profit": 160.00
     }
     ```

### 3.2 MCN Storage Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MCN STORAGE LAYER                        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────┐
│   Event Input    │
│ (JSON Payload)  │
└────────┬─────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  MCNAdapter.record_event()         │
│                                     │
│  1. Convert to text:               │
│     "strategy_backtest: win_rate=   │
│      0.75, sharpe=1.5, ..."         │
│                                     │
│  2. Generate embedding:             │
│     SentenceTransformer            │
│     ('all-MiniLM-L6-v2')           │
│     384-dim → resize to 32-dim      │
│                                     │
│  3. Create metadata:                │
│     {                               │
│       event_type: "...",            │
│       strategy_id: "...",           │
│       user_id: "...",               │
│       timestamp: "...",             │
│       payload: {...}                │
│     }                               │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  MCNLayer.add()                     │
│                                     │
│  - Store vector in memory           │
│  - Store metadata                   │
│  - Update value estimates           │
│  - Cluster similar events           │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Persistent Storage                 │
│  (mcn_store/mcn_state.npz)          │
│                                     │
│  - Auto-save every 10 events        │
│  - Manual save on shutdown          │
│  - Contains:                        │
│    • Vector embeddings              │
│    • Metadata                       │
│    • Value estimates                │
│    • Cluster assignments            │
└─────────────────────────────────────┘
```

### 3.3 How MCN is Used

**1. Strategy Memory Retrieval**
```
MCNAdapter.get_memory_for_strategy(strategy_id):
  - Searches MCN for events with matching strategy_id
  - Returns top 10-20 similar patterns
  - Used by Brain to understand strategy's historical performance
```

**2. Regime Context**
```
MCNAdapter.get_regime_context(symbol):
  - Searches MCN for market_snapshot events
  - Finds most common regime (bull/bear/highVol/lowVol)
  - Estimates strategy performance in that regime
  - Used to adjust confidence scores
```

**3. Lineage Memory**
```
MCNAdapter.get_strategy_lineage_memory(strategy_id):
  - Queries database for parent/child relationships
  - Traverses up the tree to find ancestors
  - Checks MCN for ancestor performance
  - Detects overfitting patterns
  - Calculates robustness score
```

**4. Trade Recommendations**
```
MCNAdapter.recommend_trade(strategy_id, symbol):
  - Gets strategy memory
  - Gets current market state
  - Searches MCN for similar conditions
  - Generates adjustments based on historical patterns
```

---

## 4. Strategy Status Management

### 4.1 Status Hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│              STRATEGY STATUS LIFECYCLE                      │
└─────────────────────────────────────────────────────────────┘

    ┌──────────────┐
    │  EXPERIMENT  │ ← Initial state (newly created)
    │              │
    │ Requirements │
    │ to promote:  │
    │ • ≥50 trades │
    │ • ≥75% win   │
    │ • ≤30% DD    │
    └──────┬───────┘
           │
           ▼ (if meets criteria)
    ┌──────────────┐
    │  CANDIDATE   │ ← Promising strategy
    │              │
    │ Requirements │
    │ to promote:  │
    │ • ≥50 trades │
    │ • ≥75% win   │
    │ • Sharpe >0.4│
    │ • PF >1.2    │
    │ • ≤25% DD    │
    └──────┬───────┘
           │
           ▼ (if meets criteria)
    ┌──────────────┐
    │ PROPOSABLE   │ ← Elite strategy (can be used)
    │              │
    │ Requirements │
    │ to maintain: │
    │ • ≥50 trades │
    │ • ≥90% win   │
    │ • Sharpe >1.0│
    │ • ≤20% DD    │
    │ • Score ≥0.7 │
    └──────┬───────┘
           │
           ▼ (if metrics degrade)
    ┌──────────────┐
    │  CANDIDATE   │ ← Demoted
    └──────────────┘

    ┌──────────────┐
    │  DISCARDED   │ ← Failed too many times
    │              │
    │ Conditions:  │
    │ • ≥10 failed │
    │   attempts   │
    │ • Overfit +  │
    │   poor perf  │
    └──────────────┘
```

### 4.2 Promotion/Demotion Logic

**Experiment → Candidate:**
- `total_trades >= 50`
- `win_rate >= 0.75` (75%)
- `max_drawdown <= 0.30` (30%)
- No overfitting detected

**Candidate → Proposable:**
- `total_trades >= 50`
- `win_rate >= 0.75` (75%)
- `sharpe_ratio > 0.4`
- `profit_factor > 1.2`
- `max_drawdown < 0.25` (25%)

**Proposable → Candidate (Demotion):**
- If any of these fail:
  - `win_rate < 0.90` (90%)
  - `sharpe_ratio <= 1.0`
  - `max_drawdown > 0.20` (20%)
  - `score < 0.70`
  - `test_win_rate < 0.75` (overfitting)

**Any Status → Discarded:**
- `evolution_attempts >= 10` (failed 10 times)
- OR: `evolution_attempts >= 5` AND `win_rate < 0.50` AND `score < 0.40` AND `overfitting_detected`

### 4.3 Evolution Phases

The system adapts thresholds based on maturity:

**Phase 0: Cold Start** (First 72 hours OR <25 strategies)
- Lower thresholds to allow more strategies to progress
- `winrate_min = 0.25` (25%)
- `sharpe_min = 0.2`
- `trades_min = 5`

**Phase 1: Growth** (25+ strategies OR 200+ MCN events)
- Medium thresholds
- `winrate_min = 0.55` (55%)
- `sharpe_min = 0.5`
- `trades_min = 10`

**Phase 2: Mature** (200+ strategies AND 1000+ MCN events)
- High thresholds (elite only)
- `winrate_min = 0.90` (90%)
- `sharpe_min = 1.0`
- `trades_min = 30`
- `max_drawdown_max = 0.10` (10%)

---

## 5. Evolution Worker Cycle

### 5.1 Cycle Overview

The Evolution Worker runs continuously every 2 minutes (configurable):

```
┌─────────────────────────────────────────────────────────────┐
│              EVOLUTION WORKER CYCLE                         │
│              (Runs every 2 minutes)                          │
└─────────────────────────────────────────────────────────────┘

START
  │
  ▼
┌─────────────────────────────────────┐
│ 1. Detect Evolution Phase           │
│    - Count strategies in DB         │
│    - Count MCN events               │
│    - Determine: Cold Start /        │
│      Growth / Mature                │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 2. Query Active Strategies          │
│    - Filter: is_active = true       │
│    - Filter: status != 'discarded'  │
│    - Sort by priority:              │
│      1. Never backtested            │
│      2. Old backtests (>7 days)     │
│      3. Experiment status           │
│      4. Others                      │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 3. Rate Limit Check                 │
│    - Limit to 300 strategies/cycle  │
│      (80% of 377 credits/min)       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 4. Create MCN Backup                │
│    - Backup before mutations        │
│    - Store in mcn_backups/          │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 5. Process Strategies in Parallel   │
│    - ThreadPoolExecutor             │
│    - Max 5 concurrent backtests     │
│    - Each gets own DB session       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 6. For Each Strategy:               │
│    a. Run Backtest                  │
│    b. Calculate Score               │
│    c. Determine Status              │
│    d. Update Database               │
│    e. Record to MCN                 │
│    f. Mutate if needed              │
│    g. Discard if needed             │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 7. Enforce Strategy Limit            │
│    - Keep top 100 by score          │
│    - Discard worst performers       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 8. Log Summary                      │
│    - Total tested                   │
│    - Promoted                       │
│    - Mutated                        │
│    - Discarded                      │
└──────────────┬──────────────────────┘
               │
               ▼
END (Wait 2 minutes, repeat)
```

### 5.2 Strategy Processing Detail

For each strategy in the queue:

```
┌─────────────────────────────────────────────────────────────┐
│         PROCESSING A SINGLE STRATEGY                         │
└─────────────────────────────────────────────────────────────┘

Input: Strategy object from database
  │
  ▼
┌─────────────────────────────────────┐
│ A. Run Backtest                     │
│    - Fetch market data              │
│    - Execute strategy logic         │
│    - Calculate metrics              │
│    - Generate equity curve          │
│    - Detect overfitting             │
│    - Run Monte Carlo                │
│    - Run Walk-Forward Analysis      │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ B. Calculate Unified Score         │
│    - Combine all metrics            │
│    - Weighted formula               │
│    - Result: 0.0 to 1.0             │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ C. Determine New Status             │
│    - Check current status           │
│    - Check thresholds               │
│    - Promote/Demote/Keep            │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ D. Update Database                  │
│    - Save backtest results          │
│    - Update strategy.score          │
│    - Update strategy.status         │
│    - Update last_backtest_at        │
│    - Increment evolution_attempts   │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ E. Record to MCN                    │
│    - Event: "strategy_backtest"     │
│    - Include all metrics            │
│    - Store for future learning      │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ F. Decision: Mutate?                │
│    - If score < 0.7 AND             │
│      evolution_attempts < 10:       │
│      → YES, mutate                  │
│    - Else: → NO, keep as is         │
└──────────────┬──────────────────────┘
               │
        ┌───────┴───────┐
        │               │
        ▼               ▼
    ┌───────┐      ┌──────────┐
    │  YES  │      │    NO    │
    └───┬───┘      └────┬─────┘
        │               │
        ▼               ▼
┌───────────────┐  ┌──────────────┐
│ G. Mutate      │  │ H. Check     │
│    - Create    │  │    Discard   │
│      3-5        │  │    - If       │
│      variants   │  │      attempts│
│    - Backtest  │  │      >= 10:   │
│      each       │  │      →       │
│    - Keep best │  │      DISCARD  │
│      ones       │  │    - Else:   │
│    - Record    │  │      KEEP    │
│      lineage    │  └──────────────┘
└───────────────┘
```

---

## 6. Mutation Engine

### 6.1 Mutation Types

The Enhanced Mutation Engine supports 7 mutation types:

1. **parameter_tweak**
   - Adjusts numeric parameters by ±5% to ±20%
   - Example: SMA period 20 → 18 or 22
   - Mutation strength depends on strategy score

2. **indicator_substitution**
   - Replaces one indicator with another
   - Example: SMA → EMA, RSI → MACD
   - Maintains similar logic structure

3. **cross_asset_transplant**
   - Takes strategy from one symbol, applies to another
   - Tests if strategy is universal
   - Example: AAPL strategy → GOOGL

4. **timeframe_change**
   - Changes timeframe (1m, 5m, 15m, 1h, 1d)
   - Example: 1d → 1h (more frequent trades)

5. **indicator_threshold**
   - Adjusts indicator thresholds
   - Example: RSI < 30 → RSI < 25 (more sensitive)

6. **trailing_stop**
   - Adjusts trailing stop distance
   - Example: 2% → 1.5% or 2.5%

7. **volume_threshold**
   - Adjusts volume requirements
   - Example: volume > 1M → volume > 1.5M

### 6.2 Adaptive Mutation Strength

Mutation strength adapts based on strategy performance:

```
┌─────────────────────────────────────────────────────────────┐
│         ADAPTIVE MUTATION STRENGTH                           │
└─────────────────────────────────────────────────────────────┘

Strategy Score    │  Mutation Strength  │  Purpose
──────────────────┼─────────────────────┼─────────────────────
≥ 0.8 (Elite)     │  ±5%                │  Fine-tuning
                  │                      │  (small tweaks)
──────────────────┼─────────────────────┼─────────────────────
0.6 - 0.8 (Good)  │  ±10%               │  Moderate exploration
                  │                      │  (balanced)
──────────────────┼─────────────────────┼─────────────────────
< 0.6 (Poor)      │  ±20%               │  Large exploration
                  │                      │  (find new approach)
```

### 6.3 Mutation Process

```
┌─────────────────────────────────────────────────────────────┐
│              MUTATION PROCESS                                │
└─────────────────────────────────────────────────────────────┘

Input: Parent Strategy
  │
  ▼
┌─────────────────────────────────────┐
│ 1. Select Mutation Type             │
│    - Random choice from 7 types     │
│    - Or crossover (combine 2)       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 2. Apply Mutation                    │
│    - Create new ruleset              │
│    - Adjust parameters               │
│    - Maintain structure              │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 3. Create Child Strategy             │
│    - New UUID                        │
│    - Name: "Parent (Mutated)"        │
│    - status: "experiment"            │
│    - evolution_attempts: 0           │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 4. Create Lineage Record             │
│    - parent_strategy_id              │
│    - child_strategy_id               │
│    - mutation_type                   │
│    - mutation_params                 │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 5. Backtest Child                    │
│    - Same process as parent          │
│    - Calculate metrics               │
│    - Calculate score                 │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 6. Compare to Parent                 │
│    - If child.score > parent.score: │
│      → Keep child                    │
│    - Else:                           │
│      → Discard child                 │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 7. Record to MCN                     │
│    - Event: "strategy_mutated"       │
│    - Include parent/child IDs        │
│    - Include mutation type           │
└─────────────────────────────────────┘
```

### 6.4 Crossover (Genetic Algorithm)

When two strategies are combined:

```
┌─────────────────────────────────────────────────────────────┐
│              CROSSOVER PROCESS                               │
└─────────────────────────────────────────────────────────────┘

Parent 1: "Momentum Breakout"
  - SMA(20) > SMA(50)
  - RSI < 30
  - Stop loss: 2%

Parent 2: "Mean Reversion"
  - RSI < 25
  - Volume > 1M
  - Stop loss: 1.5%

        │
        ▼
    CROSSOVER
        │
        ▼
Child: "Momentum × Mean Reversion"
  - SMA(20) > SMA(50)  (from Parent 1)
  - RSI < 27.5         (average: 30 + 25 / 2)
  - Volume > 1M        (from Parent 2)
  - Stop loss: 1.75%  (average: 2% + 1.5% / 2)
```

### 6.5 What Metrics Change During Mutation

**Parameter Tweak Example:**
```
Original Strategy:
  - SMA period: 20
  - RSI threshold: 30
  - Stop loss: 2%

After Mutation (±10%):
  - SMA period: 18 or 22
  - RSI threshold: 27 or 33
  - Stop loss: 1.8% or 2.2%

Resulting Metrics Change:
  - total_trades: May increase/decrease
  - win_rate: May improve or degrade
  - sharpe_ratio: May change
  - max_drawdown: May change
  - score: Recalculated
```

**Indicator Substitution Example:**
```
Original Strategy:
  - Uses SMA(20) for trend
  - Win rate: 70%
  - Sharpe: 1.2

After Mutation:
  - Uses EMA(20) instead of SMA(20)
  - Win rate: 75% (improved!)
  - Sharpe: 1.5 (improved!)
  - score: 0.78 → 0.85 (improved!)

Result: Child strategy is kept, parent may be discarded
```

---

## 7. Complete Flow Diagrams

### 7.1 End-to-End: User-Uploaded Strategy (Strategy A)

```
┌─────────────────────────────────────────────────────────────┐
│         STRATEGY A: USER-UPLOADED LIFECYCLE                  │
└─────────────────────────────────────────────────────────────┘

DAY 1: User Uploads Strategy
─────────────────────────────
User → POST /api/strategies/upload
  │
  ▼
Database: UserStrategy created
  - id: "strategy-a-uuid"
  - user_id: "user-123"
  - name: "My Custom Strategy"
  - status: "experiment"
  - score: null
  - last_backtest_at: null
  - evolution_attempts: 0
  │
  ▼
MCN: No event recorded yet

───────────────────────────────────────────────────────────────

DAY 1: Evolution Worker Cycle (2 minutes later)
────────────────────────────────────────────────
Evolution Worker runs
  │
  ▼
Query: Finds Strategy A (priority: never backtested)
  │
  ▼
Backtest Execution:
  1. Fetch AAPL data (last 200 days)
  2. Execute strategy logic
  3. Generate 45 trades
  4. Calculate metrics:
     - win_rate: 0.68 (68%)
     - sharpe: 0.9
     - total_return: 12.5%
     - max_drawdown: -15%
     - score: 0.65
  │
  ▼
Status Check:
  - Current: "experiment"
  - Trades: 45 (≥50? NO)
  - Win rate: 0.68 (<0.75? YES)
  - Result: Stay "experiment"
  │
  ▼
Database Update:
  - last_backtest_at: now
  - last_backtest_results: {...}
  - score: 0.65
  - evolution_attempts: 1
  │
  ▼
MCN Event Recorded:
  - event_type: "strategy_backtest"
  - strategy_id: "strategy-a-uuid"
  - payload: {win_rate: 0.68, sharpe: 0.9, ...}

───────────────────────────────────────────────────────────────

DAY 7: Evolution Worker Cycle (after more data)
───────────────────────────────────────────────
Evolution Worker runs
  │
  ▼
Query: Finds Strategy A (priority: old backtest)
  │
  ▼
Backtest Execution:
  - Now has 52 trades (more data)
  - win_rate: 0.77 (77%)
  - sharpe: 1.1
  - score: 0.72
  │
  ▼
Status Check:
  - Current: "experiment"
  - Trades: 52 (≥50? YES)
  - Win rate: 0.77 (≥0.75? YES)
  - Max drawdown: -18% (≤30%? YES)
  - Result: PROMOTE to "candidate"
  │
  ▼
Database Update:
  - status: "candidate"
  - score: 0.72
  - evolution_attempts: 2
  │
  ▼
MCN Event Recorded:
  - event_type: "strategy_backtest"
  - status: "candidate"

───────────────────────────────────────────────────────────────

DAY 14: Evolution Worker Cycle
───────────────────────────────
Backtest Execution:
  - win_rate: 0.82 (82%)
  - sharpe: 1.3
  - profit_factor: 1.8
  - score: 0.78
  │
  ▼
Status Check:
  - Current: "candidate"
  - Trades: 58 (≥50? YES)
  - Win rate: 0.82 (≥0.75? YES)
  - Sharpe: 1.3 (>0.4? YES)
  - Profit factor: 1.8 (>1.2? YES)
  - Max drawdown: -22% (<25%? YES)
  - Result: PROMOTE to "proposable"
  │
  ▼
Database Update:
  - status: "proposable"
  - Now visible in marketplace!

───────────────────────────────────────────────────────────────

DAY 30: Strategy Degrades
─────────────────────────
Backtest Execution:
  - win_rate: 0.72 (72%) ← Degraded
  - sharpe: 0.8 ← Degraded
  - score: 0.65
  │
  ▼
Status Check:
  - Current: "proposable"
  - Win rate: 0.72 (<0.90? YES)
  - Result: DEMOTE to "candidate"
  │
  ▼
Database Update:
  - status: "candidate"
  - No longer in top recommendations
```

### 7.2 End-to-End: Preseeded Strategy (Strategy B)

```
┌─────────────────────────────────────────────────────────────┐
│         STRATEGY B: PRESEEDED LIFECYCLE                      │
└─────────────────────────────────────────────────────────────┘

SYSTEM STARTUP: Seed Loading
─────────────────────────────
Seed Loader runs
  │
  ▼
Read seed file: "momentum_breakout.json"
  - ruleset: {SMA(20) > SMA(50), RSI < 30}
  - initial_score: 0.75
  │
  ▼
Database: UserStrategy created
  - id: "strategy-b-uuid"
  - user_id: "system-user-id"
  - name: "Momentum Breakout (Brain Generated)"
  - status: "experiment"
  - score: 0.75
  - evolution_attempts: 0
  │
  ▼
MCN: Event recorded
  - event_type: "strategy_backtest"
  - strategy_id: "strategy-b-uuid"
  - status: "experiment"

───────────────────────────────────────────────────────────────

EVOLUTION CYCLE 1: First Backtest
──────────────────────────────────
Evolution Worker runs
  │
  ▼
Backtest Execution:
  - win_rate: 0.78 (78%)
  - sharpe: 1.2
  - score: 0.76
  │
  ▼
Status Check:
  - Trades: 48 (<50? YES)
  - Result: Stay "experiment"
  │
  ▼
Mutation Decision:
  - Score: 0.76 (≥0.7? YES)
  - Result: NO mutation needed

───────────────────────────────────────────────────────────────

EVOLUTION CYCLE 5: Promotion
─────────────────────────────
Backtest Execution:
  - win_rate: 0.80 (80%)
  - sharpe: 1.4
  - trades: 52
  - score: 0.79
  │
  ▼
Status Check:
  - Trades: 52 (≥50? YES)
  - Win rate: 0.80 (≥0.75? YES)
  - Result: PROMOTE to "candidate"
  │
  ▼
MCN: Event recorded
  - status: "candidate"

───────────────────────────────────────────────────────────────

EVOLUTION CYCLE 10: Mutation Triggered
───────────────────────────────────────
Backtest Execution:
  - win_rate: 0.73 (73%) ← Slightly degraded
  - sharpe: 1.1
  - score: 0.68 (<0.7? YES)
  │
  ▼
Mutation Decision:
  - Score: 0.68 (<0.7? YES)
  - Evolution attempts: 3 (<10? YES)
  - Result: MUTATE
  │
  ▼
Mutation Engine:
  - Type: "parameter_tweak"
  - Change: SMA(20) → SMA(18) (-10%)
  - Create child strategy
  │
  ▼
Backtest Child:
  - win_rate: 0.79 (79%) ← Improved!
  - sharpe: 1.3
  - score: 0.77
  │
  ▼
Comparison:
  - Child score (0.77) > Parent score (0.68)
  - Result: Keep child, parent stays for now
  │
  ▼
MCN: Event recorded
  - event_type: "strategy_mutated"
  - parent_id: "strategy-b-uuid"
  - child_id: "strategy-b-child-uuid"
  - mutation_type: "parameter_tweak"

───────────────────────────────────────────────────────────────

EVOLUTION CYCLE 15: Child Promoted
──────────────────────────────────
Child Strategy Backtest:
  - win_rate: 0.85 (85%)
  - sharpe: 1.6
  - profit_factor: 2.1
  - score: 0.84
  │
  ▼
Status Check:
  - Current: "experiment"
  - Trades: 55 (≥50? YES)
  - Win rate: 0.85 (≥0.75? YES)
  - Sharpe: 1.6 (>0.4? YES)
  - Profit factor: 2.1 (>1.2? YES)
  - Result: PROMOTE to "candidate"
  │
  ▼
Parent Strategy:
  - Still "candidate"
  - Score: 0.68
  - May be discarded if child continues to outperform
```

### 7.3 MCN Learning Over Time

```
┌─────────────────────────────────────────────────────────────┐
│         MCN LEARNING PATTERN                                 │
└─────────────────────────────────────────────────────────────┘

Time: T0 (System Start)
───────────────────────
MCN: Empty
  │
  ▼
Seed strategies loaded
  │
  ▼
MCN Events: 10 "strategy_backtest" events
  - Patterns: High win rate strategies
  - Clusters: Forming around good performers

───────────────────────────────────────────────────────────────

Time: T1 (After 100 backtests)
───────────────────────────────
MCN Events: 100+ events
  - Patterns: Clear clusters
    • High win rate + High Sharpe
    • Low win rate + High volatility
    • Medium performance
  │
  ▼
MCN Can Now:
  - Identify similar strategies
  - Predict performance in regimes
  - Suggest mutations based on patterns

───────────────────────────────────────────────────────────────

Time: T2 (After 1000 backtests)
───────────────────────────────
MCN Events: 1000+ events
  - Patterns: Rich clusters
  - Value estimates: High for proven patterns
  │
  ▼
MCN Can Now:
  - Recommend mutations that worked before
  - Identify overfitting early
  - Adjust confidence based on historical success
  - Find strategies that work in specific regimes

───────────────────────────────────────────────────────────────

Time: T3 (After 10,000 backtests)
─────────────────────────────────
MCN Events: 10,000+ events
  - Patterns: Deep learning
  - Value estimates: Highly accurate
  │
  ▼
MCN Can Now:
  - Predict strategy success before backtest
  - Suggest optimal mutations
  - Identify market regime changes
  - Learn from user behavior
```

---

## 8. Key Metrics and Their Meanings

### 8.1 Performance Metrics

| Metric | Calculation | Meaning | Good Value |
|--------|-------------|---------|------------|
| **Win Rate** | Winning trades / Total trades | Percentage of profitable trades | ≥75% |
| **Total Return** | Sum of all P&L percentages | Cumulative return | ≥10% |
| **Sharpe Ratio** | (Avg return - Risk-free) / Std dev | Risk-adjusted return | ≥1.0 |
| **Sortino Ratio** | (Avg return - Risk-free) / Downside std | Only penalizes losses | ≥1.5 |
| **Profit Factor** | Total wins / Total losses | Profitability ratio | ≥1.5 |
| **Max Drawdown** | Largest peak-to-trough decline | Worst loss period | ≤20% |
| **Average Win** | Mean of winning trades | Average profit per win | Higher is better |
| **Average Loss** | Mean of losing trades | Average loss per loss | Lower is better |

### 8.2 Risk Metrics

| Metric | Meaning | Threshold |
|--------|---------|-----------|
| **Max Drawdown** | Largest loss from peak | ≤20% for proposable |
| **Longest Drawdown Duration** | Days in longest losing streak | Lower is better |
| **Volatility** | Standard deviation of returns | Lower is better |
| **Overfitting Risk** | Train vs Test performance gap | Test ≥80% of train |

### 8.3 MCN Metrics

| Metric | Meaning | Calculation |
|--------|---------|-------------|
| **Robustness Score** | Strategy stability across conditions | From ancestor performance in MCN |
| **Novelty Score** | How unique the strategy is | Based on evolution attempts (fewer = more novel) |
| **Regime Stability** | Performance across market conditions | Tested in bull/bear/highVol/lowVol |
| **Lineage Depth** | Number of generations | Count of parent strategies |

---

## 9. Summary

### Key Takeaways

1. **Backtesting is Comprehensive**
   - Uses real historical market data
   - Calculates 15+ metrics
   - Detects overfitting
   - Runs Monte Carlo and Walk-Forward Analysis

2. **MCN Learns Continuously**
   - Records every backtest, mutation, and trade
   - Forms clusters of similar patterns
   - Improves predictions over time

3. **Evolution is Adaptive**
   - Better strategies get fine-tuned (small mutations)
   - Poor strategies get large mutations (exploration)
   - Failed strategies are discarded after 10 attempts

4. **Status Management is Strict**
   - Only elite strategies become "proposable"
   - Degraded strategies are demoted
   - Failed strategies are discarded

5. **Mutation is Intelligent**
   - 7 different mutation types
   - Crossover combines two strategies
   - Only keeps improvements

### System Flow Summary

```
User Upload / Seed Load
    ↓
Strategy Created (experiment)
    ↓
Evolution Worker (every 2 min)
    ↓
Backtest → Calculate Metrics → Score
    ↓
Status Check → Promote/Demote/Keep
    ↓
MCN Recording → Learn Patterns
    ↓
Mutation (if needed) → Create Variants
    ↓
Backtest Variants → Keep Best
    ↓
Repeat until proposable or discarded
```

---

## 10. Visual Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    GSIN STRATEGY EVOLUTION SYSTEM            │
└─────────────────────────────────────────────────────────────┘

                    ┌──────────────┐
                    │   User       │
                    │   Upload     │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │   Database    │
                    │  UserStrategy │
                    │   (experiment)│
                    └──────┬───────┘
                           │
        ┌──────────────────┴──────────────────┐
        │                                       │
        ▼                                       ▼
┌───────────────┐                      ┌───────────────┐
│ Seed Loader   │                      │ Evolution     │
│ (Startup)     │                      │ Worker        │
└───────┬───────┘                      │ (Every 2 min) │
        │                               └───────┬───────┘
        │                                       │
        └───────────────┬──────────────────────┘
                        │
                        ▼
                ┌───────────────┐
                │ Backtest      │
                │ Engine        │
                └───────┬───────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌───────────┐   ┌───────────┐   ┌───────────┐
│ Market    │   │ Strategy  │   │ Metrics   │
│ Data      │   │ Execution │   │ Calc      │
│ Provider  │   │ Logic     │   │           │
└───────────┘   └───────────┘   └─────┬─────┘
                                      │
                        ┌─────────────┼─────────────┐
                        │             │             │
                        ▼             ▼             ▼
                ┌───────────┐  ┌───────────┐  ┌───────────┐
                │ Scoring   │  │ Status    │  │ MCN       │
                │ Engine    │  │ Manager   │  │ Adapter   │
                └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
                      │              │              │
                      └──────┬───────┴──────┬───────┘
                             │              │
                             ▼              ▼
                    ┌──────────────┐  ┌──────────────┐
                    │   Database   │  │     MCN      │
                    │   Update     │  │   Storage    │
                    │              │  │  (Vectors)   │
                    └──────┬───────┘  └──────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   Mutation   │
                    │   Engine     │
                    │   (if needed)│
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   New       │
                    │   Variants   │
                    └──────┬───────┘
                           │
                           └───► (Loop back to Backtest)
```

---

**End of Report**

This report provides a complete understanding of how the GSIN backtesting and evolution system works. The system is designed to continuously learn and improve, with MCN serving as the memory that guides future strategy development.

