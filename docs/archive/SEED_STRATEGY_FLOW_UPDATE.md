# Seed Strategy Flow Update

## Changes Made

### 1. Seed Strategies Now Go Through Monitoring Worker First ✅

**Before:**
- Seed strategies created with `status=experiment`
- Skipped Monitoring Worker checks
- Went directly to Evolution Worker

**After:**
- Seed strategies created with `status=pending_review`
- Go through Monitoring Worker first (same as user uploads)
- Monitoring Worker checks:
  - Duplicate detection (fingerprinting)
  - Basic sanity check (lightweight backtest)
  - Promotes to `experiment` if passes

**Flow:**
```
Seed Strategy Created
  ↓
status = pending_review
is_active = True
  ↓
Monitoring Worker (every 15 min)
  ├─→ Duplicate Check
  ├─→ Sanity Check (lightweight backtest)
  └─→ Decision:
      ├─→ Duplicate → status: duplicate
      ├─→ Failed → status: rejected
      └─→ Passed → status: experiment ✅
  ↓
Evolution Worker (every 8 min, 3 at a time)
  ├─→ Full Backtest
  ├─→ Calculate Metrics
  ├─→ Determine Status (experiment → candidate → proposable)
  ├─→ Mutate if needed
  └─→ Discard if failed
```

---

### 2. All 45 Seed Strategies Marked as Active ✅

**Implementation:**
- `seed_loader.py` explicitly sets `is_active=True` for all seed strategies
- Even though they start as `pending_review`, they are active
- This ensures Monitoring Worker picks them up

**Code:**
```python
strategy = crud.create_user_strategy(
    ...
    initial_status=StrategyStatus.PENDING_REVIEW,
)

crud.update_user_strategy(
    db=db,
    strategy_id=strategy.id,
    is_active=True,  # ✅ All seed strategies are active
    status=StrategyStatus.PENDING_REVIEW,
)
```

---

### 3. Evolution Worker Processes 3 Strategies at a Time ✅

**Before:**
- `PARALLEL_WORKERS = 5` (processed 5 strategies simultaneously)

**After:**
- `PARALLEL_WORKERS = 3` (processes 3 strategies simultaneously)

**Configuration:**
- Can be overridden via `EVOLUTION_PARALLEL_WORKERS` environment variable
- Default: 3 strategies in parallel

**Benefits:**
- Lower memory usage
- More controlled rate limiting
- Better resource management

---

## Summary

✅ **All 45 seed strategies** are marked as `is_active=True`  
✅ **Seed strategies** go through **Monitoring Worker** first (same as user uploads)  
✅ **Evolution Worker** processes **3 strategies at a time** (instead of 5)  
✅ **Unified flow** for both seed and user-uploaded strategies

---

## Testing

When you start the backend:

1. **Seed Loader** runs on startup
   - Loads 45 strategies from `proven_strategies.json` + individual files
   - Deduplicates using fingerprints
   - Creates strategies with `status=pending_review`, `is_active=True`

2. **Monitoring Worker** runs every 15 minutes
   - Picks up strategies with `status=pending_review`
   - Checks duplicates and sanity
   - Promotes to `experiment` if passes

3. **Evolution Worker** runs every 8 minutes
   - Processes 3 strategies in parallel
   - Runs backtests, calculates metrics
   - Promotes/demotes/discards based on performance

---

## Files Modified

1. `GSIN-backend/backend/strategy_engine/seed_loader.py`
   - Changed `initial_status` from `EXPERIMENT` to `PENDING_REVIEW`
   - Updated comments to reflect new flow

2. `GSIN-backend/backend/workers/evolution_worker.py`
   - Changed `PARALLEL_WORKERS` from 5 to 3

