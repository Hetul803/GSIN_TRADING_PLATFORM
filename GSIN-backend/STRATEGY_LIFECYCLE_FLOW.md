# 🔄 Strategy Lifecycle: Complete Flow & Thresholds

**Purpose:** Clear visual guide showing exactly what a strategy needs to do to get promoted, demoted, discarded, or mutated.

---

## 📊 Status Flow Diagram

```
┌─────────────────┐
│ pending_review  │ (New user upload)
└────────┬────────┘
         │
         ├─→ duplicate (if matches existing strategy)
         ├─→ rejected (if fails sanity check)
         └─→ experiment (if passes)
              │
              │
              ▼
┌─────────────────┐
│   experiment    │ (Newly created, not yet evaluated)
└────────┬────────┘
         │
         │ ✅ PROMOTE TO CANDIDATE IF:
         │    • total_trades >= 50
         │    • win_rate >= 0.75 (75%)
         │    • max_drawdown <= 0.30 (30%)
         │
         ├─→ candidate
         │
         │ ❌ DISCARD IF:
         │    • evolution_attempts >= 10
         │    • sharpe_ratio < 0 AND total_trades >= 50
         │    • evolution_attempts >= 5 AND score < 0.20
         │    • evolution_attempts >= 5 AND win_rate < 0.50 AND score < 0.40 AND overfitting_detected
         │
         └─→ discarded
              │
              ▼
┌─────────────────┐
│    candidate    │ (Passed initial backtest)
└────────┬────────┘
         │
         │ ✅ PROMOTE TO PROPOSABLE IF:
         │    (Path 1: High Win Rate)
         │    • total_trades >= 50
         │    • win_rate >= 0.80 (80%)
         │    • sharpe_ratio >= 1.0
         │    • profit_factor >= 1.2
         │    • max_drawdown <= 0.20 (20%)
         │    • score >= 0.70
         │    • test_win_rate >= 0.70 (anti-overfitting)
         │    • MCN: regime_stability_score >= 0.75
         │    • MCN: overfitting_risk == "Low"
         │
         │    OR (Path 2: High Sharpe)
         │    • total_trades >= 50
         │    • win_rate >= 0.60 (60%)
         │    • sharpe_ratio >= 1.5
         │    • profit_factor >= 1.2
         │    • max_drawdown <= 0.20 (20%)
         │    • score >= 0.70
         │    • test_win_rate >= 0.70 (anti-overfitting)
         │    • MCN: regime_stability_score >= 0.75
         │    • MCN: overfitting_risk == "Low"
         │
         ├─→ proposable
         │
         │ ⚠️ DEMOTE TO EXPERIMENT IF:
         │    • win_rate < 0.70 (buffer: 0.75 → 0.70)
         │    • max_drawdown > 0.40 (40%)
         │
         ├─→ experiment
         │
         │ ❌ DISCARD IF: (same as experiment)
         │
         └─→ discarded
              │
              ▼
┌─────────────────┐
│   proposable    │ (Ready to be proposed to users)
└────────┬────────┘
         │
         │ ⚠️ DEMOTE TO CANDIDATE IF:
         │    • win_rate < 0.70 (buffer: 0.80 → 0.70)
         │    • sharpe_ratio < 0.5 (buffer: 1.0 → 0.5)
         │    • score < 0.60 (buffer: 0.70 → 0.60)
         │    • max_drawdown > 0.30 (buffer: 0.20 → 0.30)
         │    • total_trades < 50
         │    • test_win_rate < 0.70
         │
         └─→ candidate
              │
              ▼
┌─────────────────┐
│   discarded     │ (Failed criteria, marked inactive)
└─────────────────┘
   (Never promoted again, is_active = false)
```

---

## 🧬 Mutation Triggers

### When Does a Strategy Get Mutated?

A strategy is mutated when **ANY** of these conditions are met:

#### Condition 1: Forced Mutation (After 3 Attempts)
```
IF evolution_attempts >= 3:
    → CREATE 1-2 MUTATIONS
    → evolution_attempts incremented
```

#### Condition 2: Poor Performance Mutation
```
IF win_rate < 0.60 
   AND status IN ['experiment', 'candidate']:
    → CREATE 1-2 MUTATIONS
    → Priority: Indicator substitution mutation
    → evolution_attempts incremented
```

### Mutation Types Created

1. **Parameter Tweak** - Adjust indicator parameters
   - Strength: Adaptive based on score
     - Score >= 0.8: ±5% (fine-tuning)
     - Score >= 0.6: ±10% (medium)
     - Score < 0.6: ±20% (exploration)

2. **Indicator Substitution** - Replace indicators
   - SMA ↔ EMA
   - RSI ↔ MACD
   - Random from indicator pool

3. **Timeframe Change** - Change timeframe
   - 1d ↔ 1h ↔ 15m ↔ 30m

4. **Cross-Asset Transplant** - Test on different symbols

5. **Crossover** - Combine two parent strategies (70% chance)

### Mutation Process

```
1. Evolution Worker detects mutation trigger
2. EnhancedMutationEngine creates mutation(s)
3. New UserStrategy record created:
   - status = 'experiment'
   - evolution_attempts = 0
   - user_id = parent.user_id
   - name = "{parent.name} (Mutated)"
4. StrategyLineage record created:
   - parent_strategy_id = original
   - child_strategy_id = new mutation
   - mutation_type = "mutation" or "crossover"
5. Parent's evolution_attempts incremented
6. Event recorded to MCN (non-blocking)
```

---

## ❌ Discard Rules (Fail-Fast)

### When Does a Strategy Get Discarded?

A strategy is discarded when **ANY** of these conditions are met:

#### Rule 1: Max Attempts Reached
```
IF evolution_attempts >= 10:
    → status = 'discarded'
    → is_active = false
    → NEVER promoted again
```

#### Rule 2: Proven Loser (Negative Sharpe)
```
IF sharpe_ratio < 0 
   AND total_trades >= 50:
    → status = 'discarded'
    → is_active = false
    → Reason: "Proven loser - negative Sharpe with enough sample size"
```

#### Rule 3: Not Learning
```
IF evolution_attempts >= 5 
   AND score < 0.20:
    → status = 'discarded'
    → is_active = false
    → Reason: "Not learning - many attempts but still very low score"
```

#### Rule 4: Consistently Poor Performance
```
IF evolution_attempts >= 5 
   AND win_rate < 0.50 
   AND score < 0.40 
   AND overfitting_detected == True:
    → status = 'discarded'
    → is_active = false
    → Reason: "Consistently poor - low win rate, low score, overfit"
```

### Discard Process

```
1. Evolution Worker detects discard condition
2. set_strategy_status() called:
   - status = 'discarded'
   - is_active = false
   - reason = specific discard reason
3. Event recorded to MCN (non-blocking)
4. Strategy excluded from future evolution cycles
5. Strategy NEVER deleted from database (soft delete only)
```

---

## ✅ Promotion Rules (Detailed)

### Experiment → Candidate

**Requirements (ALL must be met):**
- ✅ `total_trades >= 50`
- ✅ `win_rate >= 0.75` (75%)
- ✅ `max_drawdown <= 0.30` (30%)

**What Happens:**
- `status` updated to `'candidate'`
- `is_proposable = false`
- Notification sent to user (if user-uploaded)

**Example:**
```
Strategy has:
- total_trades = 60 ✅
- win_rate = 0.78 (78%) ✅
- max_drawdown = 0.25 (25%) ✅

→ PROMOTED TO CANDIDATE
```

---

### Candidate → Proposable

**Two Promotion Paths (choose ONE):**

#### Path 1: High Win Rate Path

**Requirements (ALL must be met):**
- ✅ `total_trades >= 50`
- ✅ `win_rate >= 0.80` (80%)
- ✅ `sharpe_ratio >= 1.0`
- ✅ `profit_factor >= 1.2`
- ✅ `max_drawdown <= 0.20` (20%)
- ✅ `score >= 0.70`
- ✅ `test_win_rate >= 0.70` (anti-overfitting)
- ✅ `MCN: regime_stability_score >= 0.75` (if DB available)
- ✅ `MCN: overfitting_risk == "Low"` (if DB available)

**Example:**
```
Strategy has:
- total_trades = 80 ✅
- win_rate = 0.82 (82%) ✅
- sharpe_ratio = 1.2 ✅
- profit_factor = 1.5 ✅
- max_drawdown = 0.15 (15%) ✅
- score = 0.75 ✅
- test_win_rate = 0.75 (75%) ✅
- MCN: regime_stability = 0.80 ✅
- MCN: overfitting_risk = "Low" ✅

→ PROMOTED TO PROPOSABLE (Path 1)
```

#### Path 2: High Sharpe Path

**Requirements (ALL must be met):**
- ✅ `total_trades >= 50`
- ✅ `win_rate >= 0.60` (60%)
- ✅ `sharpe_ratio >= 1.5`
- ✅ `profit_factor >= 1.2`
- ✅ `max_drawdown <= 0.20` (20%)
- ✅ `score >= 0.70`
- ✅ `test_win_rate >= 0.70` (anti-overfitting)
- ✅ `MCN: regime_stability_score >= 0.75` (if DB available)
- ✅ `MCN: overfitting_risk == "Low"` (if DB available)

**Example:**
```
Strategy has:
- total_trades = 100 ✅
- win_rate = 0.65 (65%) ✅
- sharpe_ratio = 1.8 ✅
- profit_factor = 1.4 ✅
- max_drawdown = 0.18 (18%) ✅
- score = 0.78 ✅
- test_win_rate = 0.72 (72%) ✅
- MCN: regime_stability = 0.78 ✅
- MCN: overfitting_risk = "Low" ✅

→ PROMOTED TO PROPOSABLE (Path 2)
```

**What Happens:**
- `status` updated to `'proposable'`
- `is_proposable = true`
- Notification sent to user (if user-uploaded)
- Strategy can now be proposed to users

---

## ⚠️ Demotion Rules (Buffer Zones)

### Proposable → Candidate

**Demote if ANY condition is met (buffer zones prevent oscillation):**

- ❌ `win_rate < 0.70` (buffer: 0.80 → 0.70)
- ❌ `sharpe_ratio < 0.5` (buffer: 1.0 → 0.5)
- ❌ `score < 0.60` (buffer: 0.70 → 0.60)
- ❌ `max_drawdown > 0.30` (buffer: 0.20 → 0.30)
- ❌ `total_trades < 50`
- ❌ `test_win_rate < 0.70`

**Example:**
```
Strategy was proposable with:
- win_rate = 0.82
- sharpe_ratio = 1.2
- score = 0.75

Now has:
- win_rate = 0.68 (68%) ❌ < 0.70
- sharpe_ratio = 0.4 ❌ < 0.5
- score = 0.58 ❌ < 0.60

→ DEMOTED TO CANDIDATE
```

**What Happens:**
- `status` updated to `'candidate'`
- `is_proposable = false`
- Strategy no longer proposed to users

---

### Candidate → Experiment

**Demote if ANY condition is met:**

- ❌ `win_rate < 0.70` (buffer: 0.75 → 0.70)
- ❌ `max_drawdown > 0.40` (40%)

**Example:**
```
Strategy was candidate with:
- win_rate = 0.78
- max_drawdown = 0.25

Now has:
- win_rate = 0.65 (65%) ❌ < 0.70
- max_drawdown = 0.45 (45%) ❌ > 0.40

→ DEMOTED TO EXPERIMENT
```

**What Happens:**
- `status` updated to `'experiment'`
- Strategy must re-qualify for candidate status

---

## 📋 Complete Threshold Reference Table

| Transition | Metric | Threshold | Buffer Zone |
|------------|--------|-----------|-------------|
| **Experiment → Candidate** |
| | `total_trades` | >= 50 | - |
| | `win_rate` | >= 0.75 (75%) | - |
| | `max_drawdown` | <= 0.30 (30%) | - |
| **Candidate → Proposable (Path 1: High Win)** |
| | `total_trades` | >= 50 | - |
| | `win_rate` | >= 0.80 (80%) | - |
| | `sharpe_ratio` | >= 1.0 | - |
| | `profit_factor` | >= 1.2 | - |
| | `max_drawdown` | <= 0.20 (20%) | - |
| | `score` | >= 0.70 | - |
| | `test_win_rate` | >= 0.70 (70%) | - |
| | `MCN regime_stability` | >= 0.75 (75%) | - |
| | `MCN overfitting_risk` | == "Low" | - |
| **Candidate → Proposable (Path 2: High Sharpe)** |
| | `total_trades` | >= 50 | - |
| | `win_rate` | >= 0.60 (60%) | - |
| | `sharpe_ratio` | >= 1.5 | - |
| | `profit_factor` | >= 1.2 | - |
| | `max_drawdown` | <= 0.20 (20%) | - |
| | `score` | >= 0.70 | - |
| | `test_win_rate` | >= 0.70 (70%) | - |
| | `MCN regime_stability` | >= 0.75 (75%) | - |
| | `MCN overfitting_risk` | == "Low" | - |
| **Proposable → Candidate (Demotion)** |
| | `win_rate` | < 0.70 (70%) | Buffer: 0.80 → 0.70 |
| | `sharpe_ratio` | < 0.5 | Buffer: 1.0 → 0.5 |
| | `score` | < 0.60 | Buffer: 0.70 → 0.60 |
| | `max_drawdown` | > 0.30 (30%) | Buffer: 0.20 → 0.30 |
| | `total_trades` | < 50 | - |
| | `test_win_rate` | < 0.70 (70%) | - |
| **Candidate → Experiment (Demotion)** |
| | `win_rate` | < 0.70 (70%) | Buffer: 0.75 → 0.70 |
| | `max_drawdown` | > 0.40 (40%) | - |
| **Any → Discarded** |
| | `evolution_attempts` | >= 10 | - |
| | `sharpe_ratio` | < 0 AND `total_trades` >= 50 | - |
| | `evolution_attempts` | >= 5 AND `score` < 0.20 | - |
| | `evolution_attempts` | >= 5 AND `win_rate` < 0.50 AND `score` < 0.40 AND `overfitting_detected` | - |
| **Mutation Triggers** |
| | `evolution_attempts` | >= 3 | - |
| | `win_rate` | < 0.60 AND status IN ['experiment', 'candidate'] | - |

---

## 🔄 Evolution Cycle Flow

### What Happens Every 8 Minutes

```
1. GET all active strategies (is_active=true, status != 'discarded')
2. PRIORITIZE:
   - Highest: Never backtested (last_backtest_at == NULL)
   - Second: Old backtests (>7 days old)
   - Third: Experiment status
   - Lower: Already evaluated
3. LIMIT to MAX_REQUESTS_PER_CYCLE (301 strategies, rate-limited)
4. PROCESS in parallel (3 workers):
   
   FOR EACH STRATEGY:
   a. RUN BACKTEST:
      - 200 days history
      - Rolling walk-forward analysis
      - Train/test split (70/30)
      - Monte Carlo simulation (1000 iterations)
   
   b. CALCULATE SCORE:
      - Unified score (0-1) from multiple metrics
      - Uses test metrics for validation
   
   c. DETERMINE STATUS:
      - Check promotion thresholds
      - Check demotion thresholds
      - Check discard rules
      - Update status if changed
   
   d. UPDATE DATABASE:
      - score
      - status (if changed)
      - last_backtest_at
      - last_backtest_results
      - train_metrics
      - test_metrics
      - evolution_attempts (incremented by 1)
      - is_proposable (if status changed)
   
   e. CHECK MUTATION:
      IF evolution_attempts >= 3:
         → CREATE 1-2 MUTATIONS
      ELIF win_rate < 0.60 AND status IN ['experiment', 'candidate']:
         → CREATE 1-2 MUTATIONS (priority: indicator substitution)
   
   f. CHECK DISCARD:
      IF any discard rule met:
         → status = 'discarded'
         → is_active = false
         → NEVER promoted again

5. ENFORCE LIMIT:
   - Keep top 100 strategies by score
   - Mark excess as inactive

6. RECORD TO MCN:
   - All backtest events
   - All mutations
   - All status changes
   - (Non-blocking, errors don't stop evolution)
```

---

## 📊 Score Calculation

### What is the "score"?

The `score` is a unified 0-1 value that ranks strategies. It's calculated from:

```
score = (0.30 * win_rate_score)
      + (0.20 * risk_adjusted_return_score)
      + (0.20 * drawdown_score)  # Penalty
      + (0.15 * stability_score)
      + (0.05 * sharpe_score)
      + (0.10 * walk_forward_consistency_score)
      + (0.10 * monte_carlo_robustness_score)
```

### Score Interpretation

- **0.9+** = Elite strategy (highly proposable)
- **0.7-0.9** = Good strategy (proposable with caution)
- **0.5-0.7** = Acceptable (needs improvement)
- **<0.5** = Poor (should be discarded or heavily mutated)

### Score Requirements

- **Promotion to Proposable:** `score >= 0.70`
- **Demotion from Proposable:** `score < 0.60` (buffer zone)
- **Discard (Not Learning):** `score < 0.20` after 5+ attempts

---

## 🎯 Quick Reference: What Strategy Needs

### To Get Promoted to Candidate:
- ✅ At least 50 trades
- ✅ Win rate >= 75%
- ✅ Max drawdown <= 30%

### To Get Promoted to Proposable:
**Path 1 (High Win Rate):**
- ✅ At least 50 trades
- ✅ Win rate >= 80%
- ✅ Sharpe >= 1.0
- ✅ Profit factor >= 1.2
- ✅ Max drawdown <= 20%
- ✅ Score >= 0.70
- ✅ Test win rate >= 70%

**Path 2 (High Sharpe):**
- ✅ At least 50 trades
- ✅ Win rate >= 60%
- ✅ Sharpe >= 1.5
- ✅ Profit factor >= 1.2
- ✅ Max drawdown <= 20%
- ✅ Score >= 0.70
- ✅ Test win rate >= 70%

### To Get Mutated:
- ✅ `evolution_attempts >= 3` (forced)
- ✅ OR `win_rate < 0.60` AND status in ['experiment', 'candidate']

### To Get Discarded:
- ✅ `evolution_attempts >= 10` (max attempts)
- ✅ OR `sharpe_ratio < 0` AND `total_trades >= 50` (proven loser)
- ✅ OR `evolution_attempts >= 5` AND `score < 0.20` (not learning)
- ✅ OR `evolution_attempts >= 5` AND `win_rate < 0.50` AND `score < 0.40` AND `overfitting_detected` (consistently poor)

### To Get Demoted:
**From Proposable to Candidate:**
- ❌ `win_rate < 0.70` (buffer: 0.80 → 0.70)
- ❌ `sharpe_ratio < 0.5` (buffer: 1.0 → 0.5)
- ❌ `score < 0.60` (buffer: 0.70 → 0.60)
- ❌ `max_drawdown > 0.30` (buffer: 0.20 → 0.30)

**From Candidate to Experiment:**
- ❌ `win_rate < 0.70` (buffer: 0.75 → 0.70)
- ❌ `max_drawdown > 0.40` (40%)

---

## 🔍 Monitoring Worker (Additional Checks)

### Sanity Check (for pending_review strategies)

**Requirements:**
- ✅ At least 10 trades
- ✅ Max drawdown <= 70% (very lenient)
- ✅ No NaN values

**If fails:** → `status = 'rejected'`

### Robustness Check (for experiment/candidate strategies)

**Robustness Score (0-100):**
- Regime diversity (tested across different volatility regimes)
- Walk-forward stability (first half vs second half)
- Parameter sensitivity (small perturbations)

**Promote to Proposable if:**
- ✅ `robustness_score >= 70`
- ✅ `sharpe_ratio >= 1.0`
- ✅ `profit_factor >= 1.2`
- ✅ `max_drawdown <= 25%`
- ✅ `total_trades >= 20`

**Discard if:**
- ❌ `robustness_score < 40`
- ❌ `total_trades >= 20`
- ❌ `evaluation_cycles >= 3`

---

**End of Flow Document**

This document provides complete clarity on all thresholds, promotion paths, demotion rules, mutation triggers, and discard conditions for strategies in the GSIN Brain system.

