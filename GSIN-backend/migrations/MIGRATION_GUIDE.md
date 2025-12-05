# 🚀 Migration Guide: Fix user_strategies Schema

## Overview

This migration adds all required columns for the Evolution Worker to function correctly. The migration is **safe** - it only adds columns that don't exist, so you can run it multiple times without issues.

---

## 📋 Step-by-Step Instructions

### Step 1: Open Supabase SQL Editor

1. Go to your Supabase project dashboard
2. Click on **SQL Editor** in the left sidebar
3. Click **New Query**

### Step 2: Run the Migration

1. Open the file: `migrations/fix_user_strategies_schema.sql`
2. Copy the **entire contents** (all 309 lines)
3. Paste into Supabase SQL Editor
4. Click **Run** (or press `Ctrl+Enter` / `Cmd+Enter`)

**Expected Output:**
You should see multiple `NOTICE` messages like:
```
NOTICE: Added status column
NOTICE: Added score column
...
```

If a column already exists, you'll see:
```
NOTICE: status column already exists
```

### Step 3: Verify Migration

Run the quick verification query:

1. Open the file: `migrations/QUICK_VERIFY.sql`
2. Copy and paste into Supabase SQL Editor
3. Click **Run**

**Expected Result:**
```
✅ MIGRATION COMPLETE - All critical columns exist!
```

If you see `❌ MIGRATION INCOMPLETE`, check the error messages and re-run the migration.

### Step 4: Detailed Verification (Optional)

For a comprehensive check, run:
1. Open the file: `migrations/verify_schema.sql`
2. Copy and paste into Supabase SQL Editor
3. Click **Run**

This will show you:
- All columns and their properties
- Indexes
- Triggers
- Data summary

---

## ✅ Verification Queries

### Quick Check (Single Query)

```sql
SELECT 
    CASE 
        WHEN COUNT(*) = 8 THEN '✅ MIGRATION COMPLETE - All critical columns exist!'
        ELSE '❌ MIGRATION INCOMPLETE - Missing ' || (8 - COUNT(*)) || ' critical columns'
    END as migration_status,
    COUNT(*) as critical_columns_found,
    8 as required_columns
FROM information_schema.columns
WHERE table_name = 'user_strategies'
  AND column_name IN (
    'status',
    'score',
    'last_backtest_at',
    'last_backtest_results',
    'train_metrics',
    'test_metrics',
    'evolution_attempts',
    'is_proposable'
  );
```

### Detailed Column Check

```sql
SELECT 
    column_name, 
    data_type, 
    is_nullable,
    column_default,
    CASE 
        WHEN column_name IN ('status', 'score', 'last_backtest_at', 'last_backtest_results', 
                             'train_metrics', 'test_metrics', 'evolution_attempts', 'is_proposable')
        THEN '⚠️ CRITICAL'
        ELSE '✓'
    END as importance
FROM information_schema.columns
WHERE table_name = 'user_strategies'
ORDER BY ordinal_position;
```

### Check Strategy Status Distribution

```sql
SELECT 
    status,
    COUNT(*) as count,
    COUNT(CASE WHEN is_proposable = true THEN 1 END) as proposable_count,
    AVG(score) as avg_score,
    AVG(evolution_attempts) as avg_attempts
FROM user_strategies
GROUP BY status
ORDER BY count DESC;
```

---

## 🔍 Troubleshooting

### Issue: "relation 'user_strategies' does not exist"

**Solution:** The table doesn't exist yet. You need to run Alembic migrations first:
```bash
cd GSIN-backend
alembic upgrade head
```

### Issue: "permission denied"

**Solution:** Make sure you're using a database user with ALTER TABLE permissions. In Supabase, the default user should have these permissions.

### Issue: Migration runs but columns still missing

**Solution:** 
1. Check for error messages in the SQL Editor output
2. Verify you're connected to the correct database
3. Try running individual column additions from the migration file

---

## 📊 Expected Results

After successful migration:

- **Total Columns:** 22
- **Critical Columns:** 8 (all present)
- **Indexes:** 2 (on `status` and `last_backtest_at`)
- **Trigger:** 1 (for auto-updating `updated_at`)

---

## 🎯 Next Steps

After migration is complete:

1. ✅ Verify all columns exist (run QUICK_VERIFY.sql)
2. ✅ Test evolution worker:
   ```python
   # In your backend
   from backend.workers.evolution_worker import run_evolution_worker_once
   stats = run_evolution_worker_once()
   print(stats)
   ```
3. ✅ Check database for promoted strategies:
   ```sql
   SELECT COUNT(*) FROM user_strategies WHERE status = 'candidate';
   SELECT COUNT(*) FROM user_strategies WHERE status = 'proposable';
   ```

---

## 📝 Notes

- The migration is **idempotent** - safe to run multiple times
- It only adds missing columns, won't modify existing data
- Default values are set appropriately (e.g., `status` defaults to `'experiment'`)
- Indexes are created for frequently queried columns

---

**Migration Date:** 2025-01-05  
**Status:** Ready to run

