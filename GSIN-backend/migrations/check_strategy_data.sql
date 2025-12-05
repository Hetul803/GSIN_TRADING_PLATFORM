-- ============================================================================
-- CHECK STRATEGY DATA: PostgreSQL-compatible query
-- ============================================================================
-- Run this to see your strategy status distribution and metrics
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

-- ============================================================================
-- ALTERNATIVE: If you want to see individual strategies
-- ============================================================================
SELECT 
    id,
    name,
    status,
    ROUND(score::numeric, 3) as score,
    evolution_attempts,
    is_proposable,
    last_backtest_at,
    CASE 
        WHEN last_backtest_results IS NOT NULL THEN '✅'
        ELSE '❌'
    END as has_backtest_results
FROM user_strategies
ORDER BY 
    CASE status
        WHEN 'proposable' THEN 1
        WHEN 'candidate' THEN 2
        WHEN 'experiment' THEN 3
        WHEN 'discarded' THEN 4
        ELSE 5
    END,
    score DESC NULLS LAST
LIMIT 20;

