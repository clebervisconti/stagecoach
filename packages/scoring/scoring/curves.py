"""Piecewise-linear curve interpolation."""


def validate_curve(curve: list[list[float]]) -> None:
    """Validate that a curve is well-formed.

    Args:
        curve: List of [x, y] points

    Raises:
        ValueError: If curve is invalid
    """
    if not curve or len(curve) < 2:
        raise ValueError("Curve must have at least 2 points")

    for i, point in enumerate(curve):
        if len(point) != 2:
            raise ValueError(f"Point {i} must have exactly 2 values")

        x, y = point
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            raise ValueError(f"Point {i} must have numeric values")

        if not (0 <= y <= 100):
            raise ValueError(f"Point {i} y-value {y} must be in [0, 100]")

        if i > 0 and x <= curve[i - 1][0]:
            raise ValueError(f"Point {i} x-value {x} must be greater than previous x-value")


def interpolate_curve(curve: list[list[float]], x: float) -> float:
    """Interpolate a piecewise-linear curve at point x.

    The curve is defined by a list of [x, y] anchor points.
    Values are linearly interpolated between points and clamped
    at the ends.

    Args:
        curve: List of [x, score] points sorted by x
        x: Input value

    Returns:
        Interpolated score in [0, 100]

    Example:
        >>> curve = [[0, 100], [5, 55], [12, 10]]
        >>> interpolate_curve(curve, 2.5)
        77.5
    """
    if not curve:
        raise ValueError("Curve cannot be empty")

    # Clamp at the left end
    if x <= curve[0][0]:
        return float(curve[0][1])

    # Clamp at the right end
    if x >= curve[-1][0]:
        return float(curve[-1][1])

    # Find the two points to interpolate between
    for i in range(len(curve) - 1):
        x1, y1 = curve[i]
        x2, y2 = curve[i + 1]

        if x1 <= x <= x2:
            # Linear interpolation
            if x2 == x1:
                # Avoid division by zero (shouldn't happen with validated curves)
                return float(y1)

            t = (x - x1) / (x2 - x1)
            y = y1 + t * (y2 - y1)
            return float(y)

    # Should never reach here with a valid curve
    raise ValueError(f"Failed to interpolate x={x} on curve")
