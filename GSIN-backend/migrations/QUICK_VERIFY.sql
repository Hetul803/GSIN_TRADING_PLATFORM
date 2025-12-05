-- ============================================================================
-- QUICK VERIFICATION: One query to check if migration is complete
-- ============================================================================
-- Run this single query to quickly verify all critical columns exist
-- ============================================================================

SELECT 
    CASE 
        WHEN COUNT(*) = 8 THEN '✅ MIGRATION COMPLETE - All critical columns exist!'
        ELSE '❌ MIGRATION INCOMPLETE - Missing ' || (8 - COUNT(*)) || ' critical columns'
    END as migration_status,
    COUNT(*) as critical_columns_found,
    8 as required_columns,
    STRING_AGG(column_name, ', ' ORDER BY column_name) as found_columns
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

-- ============================================================================
-- If this shows "✅ MIGRATION COMPLETE", you're good to go!
-- If it shows "❌ MIGRATION INCOMPLETE", run fix_user_strategies_schema.sql
-- ============================================================================

-- ============================================================================
-- BONUS: Check strategy status distribution (PostgreSQL-compatible)
-- ============================================================================
SELECT 
    COALESCE(status, 'NULL') as status,
    COUNT(*) as count,
    COUNT(CASE WHEN is_proposable = true THEN 1 END) as proposable_count,
    ROUND(AVG(score)::numeric, 3) as avg_score,
    ROUND(AVG(evolution_attempts)::numeric, 1) as avg_attempts,
    COUNT(CASE WHEN last_backtest_results IS NOT NULL THEN 1 END) as with_backtest_results
FROM user_strategies
GROUP BY status
ORDER BY count DESC;

