-- ============================================================================
-- SQL Migration: Fix user_strategies table schema for Evolution Worker
-- ============================================================================
-- Purpose: Ensure all columns required by evolution_worker.py exist
-- Database: Supabase PostgreSQL
-- Date: 2025-01-05
-- ============================================================================

-- This migration uses DO blocks to safely add columns only if they don't exist
-- Run this entire script in Supabase SQL Editor

-- ============================================================================
-- 1. STATUS COLUMN (CRITICAL - Used for promotion tracking)
-- ============================================================================
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_strategies' AND column_name = 'status'
    ) THEN
        ALTER TABLE user_strategies 
        ADD COLUMN status VARCHAR(32) DEFAULT 'experiment';
        CREATE INDEX IF NOT EXISTS idx_user_strategies_status ON user_strategies(status);
        RAISE NOTICE 'Added status column';
    ELSE
        RAISE NOTICE 'status column already exists';
    END IF;
END $$;

-- ============================================================================
-- 2. SCORE COLUMN (CRITICAL - Used for ranking strategies)
-- ============================================================================
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_strategies' AND column_name = 'score'
    ) THEN
        ALTER TABLE user_strategies 
        ADD COLUMN score DOUBLE PRECISION;
        RAISE NOTICE 'Added score column';
    ELSE
        RAISE NOTICE 'score column already exists';
    END IF;
END $$;

-- ============================================================================
-- 3. LAST_BACKTEST_AT COLUMN (CRITICAL - Used for prioritization)
-- ============================================================================
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_strategies' AND column_name = 'last_backtest_at'
    ) THEN
        ALTER TABLE user_strategies 
        ADD COLUMN last_backtest_at TIMESTAMP WITH TIME ZONE;
        CREATE INDEX IF NOT EXISTS idx_user_strategies_last_backtest_at ON user_strategies(last_backtest_at);
        RAISE NOTICE 'Added last_backtest_at column';
    ELSE
        RAISE NOTICE 'last_backtest_at column already exists';
    END IF;
END $$;

-- ============================================================================
-- 4. LAST_BACKTEST_RESULTS COLUMN (CRITICAL - Stores backtest metrics)
-- ============================================================================
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_strategies' AND column_name = 'last_backtest_results'
    ) THEN
        ALTER TABLE user_strategies 
        ADD COLUMN last_backtest_results JSONB;
        RAISE NOTICE 'Added last_backtest_results column';
    ELSE
        RAISE NOTICE 'last_backtest_results column already exists';
    END IF;
END $$;

-- ============================================================================
-- 5. TRAIN_METRICS COLUMN (CRITICAL - Overfitting detection)
-- ============================================================================
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_strategies' AND column_name = 'train_metrics'
    ) THEN
        ALTER TABLE user_strategies 
        ADD COLUMN train_metrics JSONB;
        RAISE NOTICE 'Added train_metrics column';
    ELSE
        RAISE NOTICE 'train_metrics column already exists';
    END IF;
END $$;

-- ============================================================================
-- 6. TEST_METRICS COLUMN (CRITICAL - Overfitting detection)
-- ============================================================================
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_strategies' AND column_name = 'test_metrics'
    ) THEN
        ALTER TABLE user_strategies 
        ADD COLUMN test_metrics JSONB;
        RAISE NOTICE 'Added test_metrics column';
    ELSE
        RAISE NOTICE 'test_metrics column already exists';
    END IF;
END $$;

-- ============================================================================
-- 7. EVOLUTION_ATTEMPTS COLUMN (CRITICAL - Mutation tracking)
-- ============================================================================
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_strategies' AND column_name = 'evolution_attempts'
    ) THEN
        ALTER TABLE user_strategies 
        ADD COLUMN evolution_attempts INTEGER DEFAULT 0;
        RAISE NOTICE 'Added evolution_attempts column';
    ELSE
        RAISE NOTICE 'evolution_attempts column already exists';
    END IF;
END $$;

-- ============================================================================
-- 8. IS_PROPOSABLE COLUMN (CRITICAL - Promotion flag)
-- ============================================================================
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_strategies' AND column_name = 'is_proposable'
    ) THEN
        ALTER TABLE user_strategies 
        ADD COLUMN is_proposable BOOLEAN DEFAULT FALSE;
        RAISE NOTICE 'Added is_proposable column';
    ELSE
        RAISE NOTICE 'is_proposable column already exists';
    END IF;
END $$;

-- ============================================================================
-- 9. IS_ACTIVE COLUMN (Used for filtering active strategies)
-- ============================================================================
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_strategies' AND column_name = 'is_active'
    ) THEN
        ALTER TABLE user_strategies 
        ADD COLUMN is_active BOOLEAN DEFAULT TRUE;
        RAISE NOTICE 'Added is_active column';
    ELSE
        RAISE NOTICE 'is_active column already exists';
    END IF;
END $$;

-- ============================================================================
-- 10. GENERALIZED COLUMN (Multi-asset performance tracking)
-- ============================================================================
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_strategies' AND column_name = 'generalized'
    ) THEN
        ALTER TABLE user_strategies 
        ADD COLUMN generalized BOOLEAN DEFAULT FALSE;
        RAISE NOTICE 'Added generalized column';
    ELSE
        RAISE NOTICE 'generalized column already exists';
    END IF;
END $$;

-- ============================================================================
-- 11. PER_SYMBOL_PERFORMANCE COLUMN (Multi-asset metrics)
-- ============================================================================
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_strategies' AND column_name = 'per_symbol_performance'
    ) THEN
        ALTER TABLE user_strategies 
        ADD COLUMN per_symbol_performance JSONB;
        RAISE NOTICE 'Added per_symbol_performance column';
    ELSE
        RAISE NOTICE 'per_symbol_performance column already exists';
    END IF;
END $$;

-- ============================================================================
-- 12. EXPLANATION_HUMAN COLUMN (Human-readable strategy explanation)
-- ============================================================================
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_strategies' AND column_name = 'explanation_human'
    ) THEN
        ALTER TABLE user_strategies 
        ADD COLUMN explanation_human TEXT;
        RAISE NOTICE 'Added explanation_human column';
    ELSE
        RAISE NOTICE 'explanation_human column already exists';
    END IF;
END $$;

-- ============================================================================
-- 13. RISK_NOTE COLUMN (Risk warning for users)
-- ============================================================================
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_strategies' AND column_name = 'risk_note'
    ) THEN
        ALTER TABLE user_strategies 
        ADD COLUMN risk_note TEXT;
        RAISE NOTICE 'Added risk_note column';
    ELSE
        RAISE NOTICE 'risk_note column already exists';
    END IF;
END $$;

-- ============================================================================
-- 14. UPDATED_AT COLUMN (Auto-updated timestamp)
-- ============================================================================
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_strategies' AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE user_strategies 
        ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
        
        -- Create trigger function if it doesn't exist
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        
        -- Create trigger
        DROP TRIGGER IF EXISTS update_user_strategies_updated_at ON user_strategies;
        CREATE TRIGGER update_user_strategies_updated_at
            BEFORE UPDATE ON user_strategies
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
        
        RAISE NOTICE 'Added updated_at column and trigger';
    ELSE
        RAISE NOTICE 'updated_at column already exists';
    END IF;
END $$;

-- ============================================================================
-- VERIFICATION QUERY
-- ============================================================================
-- Run this after the migration to verify all columns exist:
/*
SELECT 
    column_name, 
    data_type, 
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'user_strategies'
ORDER BY ordinal_position;
*/

-- ============================================================================
-- EXPECTED RESULT: 22 columns total
-- ============================================================================
-- 1. id
-- 2. user_id
-- 3. name
-- 4. description
-- 5. parameters
-- 6. ruleset
-- 7. asset_type
-- 8. score ⚠️ CRITICAL
-- 9. status ⚠️ CRITICAL
-- 10. last_backtest_at ⚠️ CRITICAL
-- 11. last_backtest_results ⚠️ CRITICAL
-- 12. train_metrics ⚠️ CRITICAL
-- 13. test_metrics ⚠️ CRITICAL
-- 14. is_active
-- 15. is_proposable ⚠️ CRITICAL
-- 16. evolution_attempts ⚠️ CRITICAL
-- 17. generalized
-- 18. per_symbol_performance
-- 19. explanation_human
-- 20. risk_note
-- 21. created_at
-- 22. updated_at

