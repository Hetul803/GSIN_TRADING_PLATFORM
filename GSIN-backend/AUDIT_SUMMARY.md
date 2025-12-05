# 🔍 System Audit Summary: Evolution Worker Schema

## ✅ FINDINGS

**Model Status:** ✅ **COMPLETE** - All required fields exist in `UserStrategy` model  
**Worker Status:** ✅ **CORRECT** - Evolution worker uses correct field names  
**Database Status:** ⚠️ **UNKNOWN** - Table may be missing columns (needs verification)

---

## 📋 DELIVERABLES

### 1. ✅ Gap Analysis Report
**File:** `SYSTEM_AUDIT_REPORT.md`

**Key Finding:** The `UserStrategy` model has ALL required fields for genetic algorithm evolution:
- ✅ `status` - Tracks progression (experiment → candidate → proposable → discarded)
- ✅ `score` - Unified ranking score (0-1)
- ✅ `last_backtest_results` - Stores backtest metrics
- ✅ `evolution_attempts` - Tracks mutation attempts
- ✅ `is_proposable` - Promotion flag
- ✅ `train_metrics` / `test_metrics` - Overfitting detection

**Missing Fields (Not Needed):**
- ❌ `generation` - Calculated dynamically from `StrategyLineage` table
- ❌ `parent_id` - Tracked via `StrategyLineage` table (allows multiple parents)

---

### 2. ✅ Fixed `backend/db/models.py`
**File:** `backend/db/models.py` (lines 282-311)

**Changes Made:**
- Added comprehensive docstring explaining genetic algorithm fields
- Added inline comments marking CRITICAL fields for evolution worker
- Clarified that parent relationships use `StrategyLineage` table, not direct `parent_id`

**Status:** Model was already correct, now better documented.

---

### 3. ✅ SQL Migration Commands
**File:** `migrations/fix_user_strategies_schema.sql`

**Purpose:** Safely add missing columns to `user_strategies` table in Supabase

**Critical Columns Added:**
1. `status` VARCHAR(32) DEFAULT 'experiment' ⚠️ **MOST CRITICAL**
2. `score` DOUBLE PRECISION
3. `last_backtest_at` TIMESTAMP WITH TIME ZONE
4. `last_backtest_results` JSONB
5. `train_metrics` JSONB
6. `test_metrics` JSONB
7. `evolution_attempts` INTEGER DEFAULT 0
8. `is_proposable` BOOLEAN DEFAULT FALSE

**Safety Features:**
- Uses `DO $$` blocks to check if columns exist before adding
- Won't duplicate columns if migration is run multiple times
- Includes indexes on frequently queried columns (`status`, `last_backtest_at`)

---

## 🚀 ACTION PLAN

### Step 1: Verify Current Schema
Run in Supabase SQL Editor:
```sql
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'user_strategies'
ORDER BY ordinal_position;
```

### Step 2: Apply Migration
1. Open Supabase SQL Editor
2. Copy contents of `migrations/fix_user_strategies_schema.sql`
3. Paste and execute
4. Check for "NOTICE" messages indicating which columns were added

### Step 3: Verify Migration
Run the verification query again and confirm all 22 columns exist.

### Step 4: Test Evolution Worker
1. Run an evolution cycle
2. Check logs for "promoted" messages
3. Query database: `SELECT COUNT(*) FROM user_strategies WHERE status = 'candidate';`
4. Query database: `SELECT COUNT(*) FROM user_strategies WHERE status = 'proposable';`

---

## 🔍 ROOT CAUSE ANALYSIS

**Most Likely Issue:** The `user_strategies` table in Supabase is missing the `status` column.

**Why This Causes Silent Failures:**
- Evolution worker tries to set `strategy.status = 'candidate'`
- If column doesn't exist, SQLAlchemy may:
  1. Silently ignore the assignment (no error)
  2. Or raise an error that's caught and logged but not visible

**Evidence:**
- User reports: "Evolution cycle complete" but "0 promoted strategies"
- This suggests the worker runs but status updates fail silently

---

## ✅ VERIFICATION CHECKLIST

After applying migration:

- [ ] All 22 columns exist in `user_strategies` table
- [ ] `status` column has default value 'experiment'
- [ ] Index exists on `status` column
- [ ] Index exists on `last_backtest_at` column
- [ ] Evolution cycle runs without errors
- [ ] Strategies are promoted to 'candidate' status
- [ ] Strategies are promoted to 'proposable' status
- [ ] `evolution_attempts` increments correctly
- [ ] `last_backtest_results` contains data

---

## 📝 NOTES

1. **Generation Field:** Not stored in database. Calculated by traversing `StrategyLineage` table. This is by design for flexibility.

2. **Parent Relationships:** Tracked via `StrategyLineage` table, not direct `parent_id`. This allows:
   - Multiple parents (crossover mutations)
   - Complex lineage trees
   - Mutation history tracking

3. **Status Values:** Valid values are:
   - `"experiment"` - Newly created, not yet evaluated
   - `"candidate"` - Passed initial backtest
   - `"proposable"` - Ready to be proposed to users
   - `"discarded"` - Failed criteria

---

**Report Date:** 2025-01-05  
**Next Steps:** Apply SQL migration and verify evolution worker functionality

