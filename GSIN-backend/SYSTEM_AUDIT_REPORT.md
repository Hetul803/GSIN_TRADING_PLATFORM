# 🔍 SYSTEM AUDIT REPORT: Genetic Evolution Worker Schema Mismatch

**Date:** 2025-01-05  
**Component:** Backend Database Schema vs Evolution Worker  
**Issue:** Evolution worker completes cycles but strategies aren't being saved/promoted

---

## 📊 EXECUTIVE SUMMARY

**Status:** ✅ **MODEL IS CORRECT** - The `UserStrategy` model has all required fields.  
**Root Cause:** Database table likely missing columns or not migrated properly.

The evolution worker (`evolution_worker.py`) is trying to save strategies with all the correct fields, but the database table `user_strategies` may be missing critical columns.

---

## 🔬 DETAILED ANALYSIS

### 1. THE STORAGE (`backend/db/models.py`)

**Model:** `UserStrategy` (lines 282-311)

#### ✅ **EXISTING COLUMNS (All Present):**

| Column | Type | Required | Used By Evolution Worker |
|--------|------|----------|-------------------------|
| `id` | String (UUID) | ✅ | Yes |
| `user_id` | String (FK) | ✅ | Yes |
| `name` | String(255) | ✅ | Yes |
| `status` | String(32) | ✅ | **CRITICAL** - Used for promotion tracking |
| `score` | Float (nullable) | ✅ | **CRITICAL** - Used for ranking |
| `last_backtest_at` | DateTime (nullable) | ✅ | **CRITICAL** - Used for prioritization |
| `last_backtest_results` | JSON (nullable) | ✅ | **CRITICAL** - Stores backtest metrics |
| `train_metrics` | JSON (nullable) | ✅ | **CRITICAL** - Overfitting detection |
| `test_metrics` | JSON (nullable) | ✅ | **CRITICAL** - Overfitting detection |
| `evolution_attempts` | Integer (default=0) | ✅ | **CRITICAL** - Mutation tracking |
| `is_active` | Boolean (default=True) | ✅ | Yes |
| `is_proposable` | Boolean (default=False) | ✅ | **CRITICAL** - Promotion flag |
| `generalized` | Boolean (default=False) | ✅ | Yes |
| `per_symbol_performance` | JSON (nullable) | ✅ | Yes |

#### ❌ **MISSING COLUMNS (Not Needed):**

- `generation` - **NOT NEEDED** - Calculated dynamically from `StrategyLineage` table
- `parent_id` - **NOT NEEDED** - Tracked via `StrategyLineage` table (many-to-many relationship)

**Verdict:** ✅ Model is **COMPLETE** - All required fields exist.

---

### 2. THE PRODUCER (`backend/workers/evolution_worker.py`)

**Key Operations:**

1. **Status Updates** (lines 437-464):
   ```python
   crud.update_user_strategy(
       db=db,
       strategy_id=strategy_id,
       score=score,                    # ✅ Field exists
       status=new_status,              # ✅ Field exists
       is_proposable=is_proposable,    # ✅ Field exists
       last_backtest_at=datetime.now(timezone.utc),  # ✅ Field exists
       last_backtest_results=backtest_results,       # ✅ Field exists
       train_metrics=backtest_results.get("train_metrics"),  # ✅ Field exists
       test_metrics=backtest_results.get("test_metrics"),    # ✅ Field exists
       evolution_attempts=current_attempts,          # ✅ Field exists
   )
   ```

2. **Strategy Creation** (lines 594-602):
   ```python
   new_strategy = crud.create_user_strategy(
       db=db,
       user_id=strategy.user_id,
       name=mutated_data.get("name", f"{strategy.name} (Mutated)"),
       parameters=mutated_data.get("parameters", strategy.parameters),
       ruleset=mutated_data.get("ruleset", strategy.ruleset),
       asset_type=mutated_data.get("asset_type", strategy.asset_type),
   )
   ```

**Verdict:** ✅ Evolution worker is using **CORRECT** field names that match the model.

---

### 3. THE CONNECTION (Database Configuration)

**Issue:** Database table may not match the model definition.

**Possible Causes:**
1. Alembic migrations not run
2. Manual table creation without all columns
3. Supabase schema out of sync with models

---

## 🎯 GAP ANALYSIS

### **CRITICAL FINDING:**

The model definition is **100% correct**. The issue is likely:

1. **Database table missing columns** - The `user_strategies` table in Supabase may be missing:
   - `status` (most critical - if missing, promotions fail silently)
   - `score`
   - `last_backtest_results`
   - `evolution_attempts`
   - `is_proposable`

2. **Migration not applied** - Alembic migrations may not have been run on Supabase.

---

## 🔧 SOLUTION

### Step 1: Verify Current Database Schema

Run this SQL in Supabase SQL Editor to check existing columns:

```sql
SELECT 
    column_name, 
    data_type, 
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'user_strategies'
ORDER BY ordinal_position;
```

### Step 2: Apply Missing Columns (SQL Migration)

If columns are missing, run this SQL migration:

```sql
-- Add status column if missing
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_strategies' AND column_name = 'status'
    ) THEN
        ALTER TABLE user_strategies 
        ADD COLUMN status VARCHAR(32) DEFAULT 'experiment';
        CREATE INDEX IF NOT EXISTS idx_user_strategies_status ON user_strategies(status);
    END IF;
END $$;

-- Add score column if missing
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_strategies' AND column_name = 'score'
    ) THEN
        ALTER TABLE user_strategies 
        ADD COLUMN score DOUBLE PRECISION;
    END IF;
END $$;

-- Add last_backtest_at column if missing
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_strategies' AND column_name = 'last_backtest_at'
    ) THEN
        ALTER TABLE user_strategies 
        ADD COLUMN last_backtest_at TIMESTAMP WITH TIME ZONE;
        CREATE INDEX IF NOT EXISTS idx_user_strategies_last_backtest_at ON user_strategies(last_backtest_at);
    END IF;
END $$;

-- Add last_backtest_results column if missing
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_strategies' AND column_name = 'last_backtest_results'
    ) THEN
        ALTER TABLE user_strategies 
        ADD COLUMN last_backtest_results JSONB;
    END IF;
END $$;

-- Add train_metrics column if missing
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_strategies' AND column_name = 'train_metrics'
    ) THEN
        ALTER TABLE user_strategies 
        ADD COLUMN train_metrics JSONB;
    END IF;
END $$;

-- Add test_metrics column if missing
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_strategies' AND column_name = 'test_metrics'
    ) THEN
        ALTER TABLE user_strategies 
        ADD COLUMN test_metrics JSONB;
    END IF;
END $$;

-- Add evolution_attempts column if missing
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_strategies' AND column_name = 'evolution_attempts'
    ) THEN
        ALTER TABLE user_strategies 
        ADD COLUMN evolution_attempts INTEGER DEFAULT 0;
    END IF;
END $$;

-- Add is_proposable column if missing
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_strategies' AND column_name = 'is_proposable'
    ) THEN
        ALTER TABLE user_strategies 
        ADD COLUMN is_proposable BOOLEAN DEFAULT FALSE;
    END IF;
END $$;

-- Add is_active column if missing
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_strategies' AND column_name = 'is_active'
    ) THEN
        ALTER TABLE user_strategies 
        ADD COLUMN is_active BOOLEAN DEFAULT TRUE;
    END IF;
END $$;

-- Add generalized column if missing
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_strategies' AND column_name = 'generalized'
    ) THEN
        ALTER TABLE user_strategies 
        ADD COLUMN generalized BOOLEAN DEFAULT FALSE;
    END IF;
END $$;

-- Add per_symbol_performance column if missing
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_strategies' AND column_name = 'per_symbol_performance'
    ) THEN
        ALTER TABLE user_strategies 
        ADD COLUMN per_symbol_performance JSONB;
    END IF;
END $$;

-- Add explanation_human column if missing
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_strategies' AND column_name = 'explanation_human'
    ) THEN
        ALTER TABLE user_strategies 
        ADD COLUMN explanation_human TEXT;
    END IF;
END $$;

-- Add risk_note column if missing
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_strategies' AND column_name = 'risk_note'
    ) THEN
        ALTER TABLE user_strategies 
        ADD COLUMN risk_note TEXT;
    END IF;
END $$;

-- Add updated_at column if missing (with trigger for auto-update)
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_strategies' AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE user_strategies 
        ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
        
        -- Create trigger to auto-update updated_at
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        
        DROP TRIGGER IF EXISTS update_user_strategies_updated_at ON user_strategies;
        CREATE TRIGGER update_user_strategies_updated_at
            BEFORE UPDATE ON user_strategies
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;
```

### Step 3: Verify Migration

After running the migration, verify all columns exist:

```sql
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'user_strategies'
ORDER BY ordinal_position;
```

Expected columns (in order):
1. `id`
2. `user_id`
3. `name`
4. `description`
5. `parameters`
6. `ruleset`
7. `asset_type`
8. `score` ⚠️ **CRITICAL**
9. `status` ⚠️ **CRITICAL**
10. `last_backtest_at` ⚠️ **CRITICAL**
11. `last_backtest_results` ⚠️ **CRITICAL**
12. `train_metrics` ⚠️ **CRITICAL**
13. `test_metrics` ⚠️ **CRITICAL**
14. `is_active`
15. `is_proposable` ⚠️ **CRITICAL**
16. `evolution_attempts` ⚠️ **CRITICAL**
17. `generalized`
18. `per_symbol_performance`
19. `explanation_human`
20. `risk_note`
21. `created_at`
22. `updated_at`

---

## ✅ VERIFICATION CHECKLIST

After applying the migration, verify:

- [ ] Run evolution cycle and check logs for "promoted" messages
- [ ] Query database: `SELECT COUNT(*) FROM user_strategies WHERE status = 'candidate';`
- [ ] Query database: `SELECT COUNT(*) FROM user_strategies WHERE status = 'proposable';`
- [ ] Check that `evolution_attempts` is incrementing: `SELECT id, evolution_attempts FROM user_strategies LIMIT 10;`
- [ ] Verify `last_backtest_results` contains data: `SELECT id, last_backtest_results FROM user_strategies WHERE last_backtest_results IS NOT NULL LIMIT 1;`

---

## 📝 NOTES

1. **Generation Field:** The `generation` field is **NOT stored** in the database. It's calculated dynamically by traversing the `StrategyLineage` table. This is by design for flexibility.

2. **Parent ID:** Parent relationships are tracked via the `StrategyLineage` table, not a direct `parent_id` column. This allows for:
   - Multiple parents (crossover mutations)
   - Complex lineage trees
   - Mutation history tracking

3. **Status Values:** Valid status values are:
   - `"experiment"` - Newly created, not yet evaluated
   - `"candidate"` - Passed initial backtest, needs more validation
   - `"proposable"` - Ready to be proposed to users
   - `"discarded"` - Failed criteria, marked inactive

---

## 🚨 CRITICAL ACTION ITEMS

1. **IMMEDIATE:** Run the SQL migration in Supabase SQL Editor
2. **VERIFY:** Check that all columns exist using the verification query
3. **TEST:** Run an evolution cycle and monitor logs
4. **CONFIRM:** Query database to see promoted strategies

---

**Report Generated:** 2025-01-05  
**Next Review:** After migration applied

