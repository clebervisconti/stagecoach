"""Tests for curve interpolation."""

import pytest

from scoring.curves import interpolate_curve, validate_curve


class TestCurveInterpolation:
    """Test piecewise-linear interpolation."""

    def test_interpolate_at_left_end(self):
        """Values left of the first point clamp to first y."""
        curve = [[5, 100], [12, 10]]
        assert interpolate_curve(curve, 0) == 100
        assert interpolate_curve(curve, 5) == 100

    def test_interpolate_at_right_end(self):
        """Values right of the last point clamp to last y."""
        curve = [[5, 100], [12, 10]]
        assert interpolate_curve(curve, 12) == 10
        assert interpolate_curve(curve, 20) == 10

    def test_interpolate_midpoint(self):
        """Linear interpolation between points."""
        curve = [[0, 100], [10, 50]]
        assert interpolate_curve(curve, 5) == 75.0

    def test_interpolate_complex_curve(self):
        """Filler sounds curve from config."""
        curve = [[0, 100], [1, 95], [2, 85], [3.5, 70], [5, 55], [8, 35], [12, 10]]

        assert interpolate_curve(curve, 0) == 100
        assert interpolate_curve(curve, 1) == 95
        assert interpolate_curve(curve, 1.5) == 90.0
        assert interpolate_curve(curve, 3.5) == 70
        assert interpolate_curve(curve, 6.5) == 45.0
        assert interpolate_curve(curve, 15) == 10

    def test_interpolate_target_band_curve(self):
        """WPM target-band curve (best inside, falls off outside)."""
        curve = [[90, 20], [130, 95], [165, 95], [210, 25]]

        assert interpolate_curve(curve, 80) == 20  # Too slow
        assert interpolate_curve(curve, 110) == pytest.approx(57.5, abs=0.1)
        assert interpolate_curve(curve, 147.5) == 95  # In band
        assert interpolate_curve(curve, 187.5) == pytest.approx(60.0, abs=0.1)
        assert interpolate_curve(curve, 220) == 25  # Too fast

    def test_empty_curve_raises(self):
        """Empty curve raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            interpolate_curve([], 5)


class TestCurveValidation:
    """Test curve validation."""

    def test_valid_curve_passes(self):
        """A well-formed curve validates."""
        curve = [[0, 100], [5, 50], [10, 0]]
        validate_curve(curve)  # Should not raise

    def test_curve_with_one_point_fails(self):
        """Curve with < 2 points fails."""
        with pytest.raises(ValueError, match="at least 2 points"):
            validate_curve([[5, 50]])

    def test_curve_with_invalid_y_fails(self):
        """y values outside [0, 100] fail."""
        with pytest.raises(ValueError, match="must be in \\[0, 100\\]"):
            validate_curve([[0, -10], [10, 50]])

        with pytest.raises(ValueError, match="must be in \\[0, 100\\]"):
            validate_curve([[0, 50], [10, 150]])

    def test_curve_with_unsorted_x_fails(self):
        """x values must be strictly increasing."""
        with pytest.raises(ValueError, match="must be greater than previous"):
            validate_curve([[10, 50], [5, 100]])

        with pytest.raises(ValueError, match="must be greater than previous"):
            validate_curve([[5, 50], [5, 100]])
