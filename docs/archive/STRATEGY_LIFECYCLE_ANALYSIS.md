# Strategy Lifecycle Timing Analysis & Contradiction Check

## How Long Until a Strategy Becomes Proposable?

### Current System Flow:

```
User Uploads Strategy
  ↓
Status: pending_review
  ↓
Monitoring Worker (runs every 15 minutes)
  ├─→ Duplicate Check (~1 second)
  ├─→ Sanity Check (lightweight backtest, ~30-60 seconds)
  └─→ Decision:
      ├─→ Duplicate → status: duplicate (STOP)
      ├─→ Failed → status: rejected (STOP)
      └─→ Passed → status: experiment ✅
  ↓
Evolution Worker (runs every 8 minutes, processes 3 at a time)
  ├─→ Full Backtest (~2-5 minutes per strategy)
  ├─→ Calculate Metrics (~1 second)
  ├─→ Determine Status
  └─→ Decision:
      ├─→ experiment → candidate (if meets thresholds)
      ├─→ candidate → proposable (if meets thresholds + MCN checks)
      ├─→ Mutate if needed (~1-2 minutes)
      └─→ Discard if failed
```

---

## Timeline Breakdown

### Phase 1: pending_review → experiment

**Time:** 15 minutes (worst case) to 0 minutes (best case)

**Process:**
- Strategy created with `status=pending_review`
- Monitoring Worker runs every 15 minutes
- If Monitoring Worker just ran, strategy waits up to 15 minutes
- If Monitoring Worker is about to run, strategy processed immediately

**Sanity Check Requirements:**
- Minimum 3 trades
- Max drawdown < 70%
- No NaN values

**Result:** Most strategies pass (very lenient thresholds)

---

### Phase 2: experiment → candidate

**Time:** 8 minutes (worst case) to several hours/days (best case)

**Process:**
- Evolution Worker runs every 8 minutes
- Processes 3 strategies in parallel
- Each backtest takes 2-5 minutes
- If 45 strategies are in queue, processing time = (45 / 3) * 8 minutes = 120 minutes = 2 hours per cycle

**Requirements for experiment → candidate:**
- `total_trades >= 50`
- `win_rate >= 0.75` (75%)
- `max_drawdown <= 0.30` (30%)

**Realistic Timeline:**
- **Best Case:** Strategy generates 50 trades in first backtest (200 days of data)
  - Time: 8 minutes (next Evolution Worker cycle)
  - **Total: ~23 minutes** (15 min Monitoring + 8 min Evolution)
  
- **Worst Case:** Strategy needs multiple backtests to generate 50 trades
  - If strategy generates 10 trades per backtest, needs 5 backtests
  - Time: 5 * 8 minutes = 40 minutes (if processed immediately)
  - **Total: ~55 minutes** (15 min Monitoring + 40 min Evolution)

- **Realistic Case:** Strategy generates 20-30 trades per backtest
  - Needs 2-3 backtests to reach 50 trades
  - Time: 2-3 * 8 minutes = 16-24 minutes
  - **Total: ~31-39 minutes**

---

### Phase 3: candidate → proposable

**Time:** 8 minutes (worst case) to several days (best case)

**Process:**
- Evolution Worker continues processing
- Monitoring Worker also checks robustness (every 15 minutes)

**Requirements for candidate → proposable:**

**Base Requirements:**
- `total_trades >= 50`
- `win_rate >= 0.90` (90%) - **VERY HIGH THRESHOLD**
- `sharpe_ratio >= 1.0`
- `profit_factor >= 1.2` (from Monitoring Worker) or `>= 1.3` (from status_manager)
- `max_drawdown <= 0.20` (20%)
- `score >= 0.70`
- `test_win_rate >= 0.75` (anti-overfitting)

**MCN Robustness Requirements:**
- `mcn_regime_stability_score >= 0.75` (pass 3 out of 4 regimes)
- `mcn_overfitting_risk = "Low"`

**Realistic Timeline:**
- **Best Case:** Strategy already meets all thresholds in first candidate backtest
  - Time: 8 minutes (next Evolution Worker cycle)
  - **Total: ~39-47 minutes** (from upload to proposable)

- **Worst Case:** Strategy needs multiple mutations to reach 90% win rate
  - If strategy has 75% win rate, needs improvement
  - Each mutation cycle: 8 minutes
  - May need 5-10 mutations to reach 90% win rate
  - Time: 5-10 * 8 minutes = 40-80 minutes
  - **Total: ~55-95 minutes** (if mutations are successful)

- **Realistic Case:** Strategy needs 2-3 mutations to improve from 75% to 90% win rate
  - Time: 2-3 * 8 minutes = 16-24 minutes
  - **Total: ~47-63 minutes**

**BUT:** The 90% win rate threshold is **extremely high**. Most strategies will:
- Never reach 90% win rate
- Stay in `candidate` status indefinitely
- Get mutated repeatedly until they either:
  - Reach 90% win rate (rare)
  - Get discarded after 10 failed evolution attempts

---

## **ESTIMATED TOTAL TIME TO PROPOSABLE**

### Best Case Scenario:
- **~40-50 minutes** (if strategy is exceptional and meets all thresholds immediately)

### Realistic Case:
- **~1-3 hours** (if strategy needs 2-3 mutations to improve)

### Worst Case Scenario:
- **Never** (most strategies will never reach 90% win rate threshold)
- **Or ~1-2 hours** (if strategy gets lucky with mutations)

### Most Likely Outcome:
- **Strategies stay in `candidate` status for days/weeks** because:
  - 90% win rate is extremely difficult to achieve
  - Most strategies will hover around 75-85% win rate
  - They'll get mutated repeatedly but may never reach 90%

---

## Contradictions and Issues Found

### 1. **CONTRADICTION: Win Rate Threshold Too High** ⚠️

**Issue:**
- `WIN_RATE_THRESHOLD_PROPOSABLE = 0.90` (90%) is extremely high
- Most professional trading strategies have 50-70% win rate
- This threshold will prevent most strategies from becoming proposable

**Evidence:**
- Professional strategies: 55-65% win rate is considered excellent
- Current system: Requires 90% win rate
- Result: Most strategies will never become proposable

**Recommendation:**
- Lower to 0.75-0.80 (75-80%) for proposable
- Or use flexible thresholds: (win_rate >= 0.80 AND sharpe >= 1.0) OR (win_rate >= 0.55 AND sharpe >= 1.5)

---

### 2. **CONTRADICTION: Profit Factor Threshold Mismatch** ⚠️

**Issue:**
- `status_manager.py`: `profit_factor >= 1.2` for candidate → proposable
- `monitoring_worker.py`: `MONITORING_PROFIT_FACTOR_MIN = 1.3` for candidate → proposable
- **Different thresholds in different places**

**Evidence:**
```python
# status_manager.py (line 117)
profit_factor = metrics.get("profit_factor", 0.0) or backtest_results.get("profit_factor", 0.0)

# monitoring_worker.py (line 83)
MONITORING_PROFIT_FACTOR_MIN = 1.3
```

**Impact:**
- Status Manager might promote with 1.2 profit factor
- Monitoring Worker might require 1.3 profit factor
- Could cause inconsistent promotions

**Recommendation:**
- Use centralized config from `strategy_config.py`
- Both should use `MIN_PROFIT_FACTOR_FOR_PROPOSABLE = 1.2` or 1.3 (pick one)

---

### 3. **CONTRADICTION: Monitoring Worker vs Evolution Worker Promotion** ⚠️

**Issue:**
- **Monitoring Worker** can promote `candidate → proposable` (robustness check)
- **Evolution Worker** can also promote `candidate → proposable` (status_manager)
- Both use different logic and thresholds

**Evidence:**
- Monitoring Worker: Uses `_check_robustness_and_promote()` with robustness score
- Evolution Worker: Uses `determine_strategy_status()` with base metrics
- Could cause race conditions or double promotions

**Impact:**
- Strategy might be promoted twice (wasteful)
- Or one worker might demote what the other promoted

**Recommendation:**
- **Monitoring Worker should be the ONLY component that promotes candidate → proposable**
- Evolution Worker should only handle experiment → candidate and mutations
- This is already partially implemented but needs clarification

---

### 4. **CONTRADICTION: MCN Checks Only in Status Manager** ⚠️

**Issue:**
- MCN robustness checks (`mcn_regime_stability_score >= 0.75`, `mcn_overfitting_risk = "Low"`) are only in `status_manager.py`
- Monitoring Worker's `_check_robustness_and_promote()` doesn't use MCN checks
- But Monitoring Worker is supposed to be the gatekeeper for candidate → proposable

**Evidence:**
```python
# status_manager.py (line 119-150)
# Has MCN checks for candidate → proposable

# monitoring_worker.py (line 295-350)
# _check_robustness_and_promote() doesn't check MCN regime stability or overfitting risk
```

**Impact:**
- Monitoring Worker might promote without MCN checks
- Status Manager might promote with MCN checks
- Inconsistent behavior

**Recommendation:**
- Add MCN checks to Monitoring Worker's `_check_robustness_and_promote()`
- Or ensure Monitoring Worker calls `determine_strategy_status()` with `db` parameter for MCN checks

---

### 5. **CONTRADICTION: Evolution Worker Processes 3 at a Time, But Queue Has 45 Strategies** ⚠️

**Issue:**
- 45 seed strategies all start as `pending_review`
- Monitoring Worker processes them (15 min cycle)
- All 45 become `experiment` status
- Evolution Worker processes 3 at a time, every 8 minutes
- **Math:** 45 strategies / 3 per cycle = 15 cycles = 15 * 8 minutes = 120 minutes = 2 hours

**Impact:**
- First strategy processed: 8 minutes
- Last strategy processed: 2 hours later
- Strategies are processed sequentially in batches of 3

**This is NOT a contradiction, but a bottleneck:**
- System is designed this way to prevent rate limiting
- But it means strategies are processed slowly

---

### 6. **CONTRADICTION: Sanity Check vs Full Backtest Requirements** ⚠️

**Issue:**
- **Sanity Check (Monitoring Worker):** Requires 3 trades, max drawdown < 70%
- **Full Backtest (Evolution Worker):** Requires 50 trades for candidate
- **Gap:** Strategy might pass sanity (3 trades) but never generate 50 trades

**Evidence:**
```python
# monitoring_worker.py
SANITY_CHECK_MIN_TRADES = 3

# status_manager.py
MIN_TRADES_FOR_EVAL = 50  # For experiment → candidate
```

**Impact:**
- Strategy passes sanity check with 3 trades
- Gets promoted to `experiment`
- But might only generate 5-10 trades in full backtest
- Stays in `experiment` forever (never reaches 50 trades)

**Recommendation:**
- Sanity check should use longer time period or require more trades (e.g., 10-15 trades)
- Or adjust `MIN_TRADES_FOR_EVAL` to be lower (e.g., 30 trades)

---

### 7. **CONTRADICTION: Mutation Logic Unclear** ⚠️

**Issue:**
- Evolution Worker mutates strategies that don't meet thresholds
- But mutation might make strategy worse
- No clear logic for when to mutate vs when to discard

**Evidence:**
- `evolution_worker.py` mutates if strategy doesn't meet thresholds
- But doesn't check if strategy is improving or degrading
- Might mutate a strategy that's already good but just needs more trades

**Impact:**
- Good strategies might get mutated unnecessarily
- Bad strategies might get mutated repeatedly without improvement

**Recommendation:**
- Only mutate if strategy is close to thresholds (e.g., 70% win rate, needs 75%)
- Discard if strategy is far from thresholds (e.g., 40% win rate, needs 75%)

---

## Summary of Contradictions

| # | Contradiction | Severity | Impact |
|---|---------------|----------|--------|
| 1 | Win Rate Threshold Too High (90%) | **HIGH** | Most strategies never become proposable |
| 2 | Profit Factor Threshold Mismatch (1.2 vs 1.3) | **MEDIUM** | Inconsistent promotions |
| 3 | Monitoring Worker vs Evolution Worker Promotion | **MEDIUM** | Race conditions, double promotions |
| 4 | MCN Checks Only in Status Manager | **MEDIUM** | Inconsistent MCN validation |
| 5 | Evolution Worker Bottleneck (3 at a time) | **LOW** | Slow processing, but intentional |
| 6 | Sanity Check vs Full Backtest Gap | **MEDIUM** | Strategies stuck in experiment |
| 7 | Mutation Logic Unclear | **LOW** | Inefficient mutations |

---

## Recommendations

### Critical (Must Fix):
1. **Lower win rate threshold** from 90% to 75-80% OR use flexible thresholds
2. **Unify profit factor threshold** (use 1.2 or 1.3 consistently)
3. **Clarify promotion logic** (Monitoring Worker only for candidate → proposable)

### High Priority:
4. **Add MCN checks to Monitoring Worker** for consistency
5. **Improve sanity check** to require more trades (10-15) or longer period

### Medium Priority:
6. **Clarify mutation logic** (when to mutate vs discard)
7. **Add metrics tracking** for strategy improvement over time

---

## Conclusion

**Estimated Time to Proposable:**
- **Best Case:** ~40-50 minutes
- **Realistic Case:** ~1-3 hours (if strategy is good)
- **Most Likely:** **Never** (90% win rate is too high)

**Main Issue:**
The 90% win rate threshold is **unrealistically high** and will prevent most strategies from becoming proposable. Most professional trading strategies have 50-70% win rate, and requiring 90% means only exceptional strategies (or overfitted ones) will pass.

**Recommendation:**
Lower the threshold to 75-80% OR implement flexible thresholds that allow high-Sharpe strategies with lower win rates to become proposable.

