# backend/tests/phase3/test_confidence_calibrator.py
"""
Unit tests for ConfidenceCalibrator.
"""
import pytest

from ...brain.confidence_calibrator import ConfidenceCalibrator


@pytest.fixture
def calibrator():
    """Create a ConfidenceCalibrator instance."""
    return ConfidenceCalibrator()


def test_calibrate_confidence_basic(calibrator):
    """Test basic confidence calibration."""
    raw_confidence = 0.7
    factors = {
        "regime_match": 0.8,
        "mtn_alignment_score": 0.9,
        "volume_strength": 0.6,
        "mcn_similarity": 0.75,
        "user_risk_tendency": "moderate",
        "strategy_stability": 0.8,
        "strategy_score": 0.7
    }
    
    calibrated = calibrator.calibrate_confidence(raw_confidence, factors)
    
    assert 0.0 <= calibrated <= 1.0
    assert calibrated > 0.0  # Should be positive


def test_calibrate_confidence_boundaries(calibrator):
    """Test confidence calibration at boundaries."""
    # Test with all factors at minimum
    factors_min = {
        "regime_match": 0.0,
        "mtn_alignment_score": 0.0,
        "volume_strength": 0.0,
        "mcn_similarity": 0.0,
        "user_risk_tendency": "low",
        "strategy_stability": 0.0,
        "strategy_score": 0.0
    }
    calibrated_min = calibrator.calibrate_confidence(0.0, factors_min)
    assert calibrated_min >= 0.0
    
    # Test with all factors at maximum
    factors_max = {
        "regime_match": 1.0,
        "mtn_alignment_score": 1.0,
        "volume_strength": 1.0,
        "mcn_similarity": 1.0,
        "user_risk_tendency": "high",
        "strategy_stability": 1.0,
        "strategy_score": 1.0
    }
    calibrated_max = calibrator.calibrate_confidence(1.0, factors_max)
    assert calibrated_max <= 1.0


def test_calibrate_confidence_monotonic(calibrator):
    """Test that calibration is monotonic (higher inputs → higher outputs)."""
    factors = {
        "regime_match": 0.5,
        "mtn_alignment_score": 0.5,
        "volume_strength": 0.5,
        "mcn_similarity": 0.5,
        "user_risk_tendency": "moderate",
        "strategy_stability": 0.5,
        "strategy_score": 0.5
    }
    
    conf1 = calibrator.calibrate_confidence(0.3, factors)
    conf2 = calibrator.calibrate_confidence(0.5, factors)
    conf3 = calibrator.calibrate_confidence(0.7, factors)
    
    assert conf1 <= conf2 <= conf3


def test_get_factor_breakdown(calibrator):
    """Test factor breakdown generation."""
    raw_confidence = 0.7
    factors = {
        "regime_match": 0.8,
        "mtn_alignment_score": 0.9,
        "volume_strength": 0.6,
        "mcn_similarity": 0.75,
        "user_risk_tendency": "moderate",
        "strategy_stability": 0.8,
        "strategy_score": 0.7
    }
    
    breakdown = calibrator.get_factor_breakdown(raw_confidence, factors)
    
    assert "raw_confidence" in breakdown
    assert "calibrated_confidence" in breakdown
    assert "contributions" in breakdown
    assert "base_confidence" in breakdown["contributions"]
    assert "regime_match" in breakdown["contributions"]
