-- ============================================================================
-- VERIFICATION QUERY: Check user_strategies table schema
-- ============================================================================
-- Run this in Supabase SQL Editor AFTER running fix_user_strategies_schema.sql
-- This will show you exactly what columns exist and their properties
-- ============================================================================

-- ============================================================================
-- 1. CHECK ALL COLUMNS EXIST
-- ============================================================================
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

-- ============================================================================
-- 2. CHECK CRITICAL COLUMNS EXIST (Detailed)
-- ============================================================================
SELECT 
    'Column Check' as check_type,
    column_name,
    CASE 
        WHEN column_name IS NOT NULL THEN '✅ EXISTS'
        ELSE '❌ MISSING'
    END as status,
    data_type,
    column_default
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
    'is_proposable',
    'is_active',
    'generalized',
    'per_symbol_performance',
    'explanation_human',
    'risk_note',
    'updated_at'
  )
ORDER BY 
    CASE column_name
        WHEN 'status' THEN 1
        WHEN 'score' THEN 2
        WHEN 'last_backtest_at' THEN 3
        WHEN 'last_backtest_results' THEN 4
        WHEN 'train_metrics' THEN 5
        WHEN 'test_metrics' THEN 6
        WHEN 'evolution_attempts' THEN 7
        WHEN 'is_proposable' THEN 8
        ELSE 9
    END;

-- ============================================================================
-- 3. CHECK INDEXES EXIST
-- ============================================================================
SELECT 
    'Index Check' as check_type,
    indexname as index_name,
    indexdef as index_definition
FROM pg_indexes
WHERE tablename = 'user_strategies'
  AND indexname IN (
    'idx_user_strategies_status',
    'idx_user_strategies_last_backtest_at'
  )
ORDER BY indexname;

-- ============================================================================
-- 4. CHECK TRIGGER EXISTS (for updated_at)
-- ============================================================================
SELECT 
    'Trigger Check' as check_type,
    trigger_name,
    event_manipulation,
    event_object_table,
    action_statement
FROM information_schema.triggers
WHERE event_object_table = 'user_strategies'
  AND trigger_name = 'update_user_strategies_updated_at';

-- ============================================================================
-- 5. SUMMARY: COUNT OF COLUMNS
-- ============================================================================
SELECT 
    'Summary' as check_type,
    COUNT(*) as total_columns,
    COUNT(CASE WHEN column_name IN ('status', 'score', 'last_backtest_at', 'last_backtest_results', 
                                    'train_metrics', 'test_metrics', 'evolution_attempts', 'is_proposable') 
              THEN 1 END) as critical_columns_count,
    CASE 
        WHEN COUNT(CASE WHEN column_name IN ('status', 'score', 'last_backtest_at', 'last_backtest_results', 
                                             'train_metrics', 'test_metrics', 'evolution_attempts', 'is_proposable') 
                       THEN 1 END) = 8 
        THEN '✅ ALL CRITICAL COLUMNS EXIST'
        ELSE '❌ MISSING CRITICAL COLUMNS'
    END as status
FROM information_schema.columns
WHERE table_name = 'user_strategies';

-- ============================================================================
-- 6. CHECK FOR MISSING CRITICAL COLUMNS
-- ============================================================================
WITH required_columns AS (
    SELECT unnest(ARRAY[
        'status',
        'score',
        'last_backtest_at',
        'last_backtest_results',
        'train_metrics',
        'test_metrics',
        'evolution_attempts',
        'is_proposable'
    ]) as column_name
),
existing_columns AS (
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'user_strategies'
)
SELECT 
    'Missing Columns' as check_type,
    rc.column_name,
    '❌ MISSING - Run migration!' as status
FROM required_columns rc
LEFT JOIN existing_columns ec ON rc.column_name = ec.column_name
WHERE ec.column_name IS NULL
ORDER BY rc.column_name;

-- ============================================================================
-- 7. SAMPLE DATA CHECK (if you have strategies)
-- ============================================================================
SELECT 
    'Data Check' as check_type,
    COUNT(*) as total_strategies,
    COUNT(CASE WHEN status IS NOT NULL THEN 1 END) as strategies_with_status,
    COUNT(CASE WHEN score IS NOT NULL THEN 1 END) as strategies_with_score,
    COUNT(CASE WHEN last_backtest_results IS NOT NULL THEN 1 END) as strategies_with_backtest_results,
    COUNT(CASE WHEN evolution_attempts > 0 THEN 1 END) as strategies_with_evolution_attempts,
    COUNT(CASE WHEN status = 'candidate' THEN 1 END) as candidate_strategies,
    COUNT(CASE WHEN status = 'proposable' THEN 1 END) as proposable_strategies,
    COUNT(CASE WHEN status = 'discarded' THEN 1 END) as discarded_strategies
FROM user_strategies;

-- ============================================================================
-- EXPECTED RESULTS:
-- ============================================================================
-- 1. Column Check: Should show 22 columns total
-- 2. Critical Columns: Should show all 8 critical columns exist
-- 3. Indexes: Should show 2 indexes (status, last_backtest_at)
-- 4. Trigger: Should show 1 trigger (update_user_strategies_updated_at)
-- 5. Summary: Should show "✅ ALL CRITICAL COLUMNS EXIST"
-- 6. Missing Columns: Should return 0 rows (no missing columns)
-- 7. Data Check: Shows current strategy counts by status
-- ============================================================================

