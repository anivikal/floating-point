"""
Floating Point Error Analyzer — Danger Score Calculator
=======================================================

Computes a 0-100 "Danger Score" that summarizes the severity of
floating point errors detected by the engine.

The score is designed for VISUAL IMPACT in demos:
  - 0-20:   SAFE (green)    — Errors are negligible
  - 21-40:  LOW (yellow)    — Minor precision loss, probably fine
  - 41-60:  MODERATE (orange) — Noticeable errors, may affect results
  - 61-80:  HIGH (red-orange) — Significant precision loss
  - 81-100: CRITICAL (red)  — Catastrophic errors, results are unreliable

The score is a weighted combination of four factors:
  1. Peak relative error (worst single point)
  2. Mean relative error (overall trend)
  3. Fraction of points exceeding safety thresholds
  4. Maximum bits of precision lost
"""

import math
from typing import Any


def compute_danger_score(telemetry: dict[str, Any]) -> dict[str, Any]:
    """
    Compute a danger score from engine telemetry data.

    Args:
        telemetry: The "telemetry" dict from any engine analysis function.
                   Must contain "relative_errors" and "bits_lost" arrays.

    Returns:
        dict with "score" (0-100), "label" (SAFE/LOW/MODERATE/HIGH/CRITICAL),
        and "summary" (human-readable explanation).
    """
    rel_errors = telemetry.get("relative_errors", [])
    bits_lost = telemetry.get("bits_lost", [])

    if not rel_errors:
        return {
            "score": 0,
            "label": "SAFE",
            "summary": "No data to analyze.",
        }

    # ── Factor 1: Peak relative error (0-25 points) ──
    # A single point of catastrophic failure should spike the score.
    # Scale: 1e-15 (perfect) → 0 points, 1.0 (total loss) → 25 points
    valid_errors = [e for e in rel_errors if not math.isnan(e) and not math.isinf(e)]
    if not valid_errors:
        return {"score": 0, "label": "SAFE", "summary": "No valid error measurements."}

    peak_error = max(valid_errors)
    if peak_error <= 0:
        peak_score = 0
    else:
        # log10 scale: -16 → 0, 0 → 25
        log_err = math.log10(max(peak_error, 1e-16))
        peak_score = max(0, min(25, (log_err + 16) * 25 / 16))

    # ── Factor 2: Mean relative error (0-25 points) ──
    # Sustained high error is worse than a single spike.
    mean_error = sum(valid_errors) / len(valid_errors)
    if mean_error <= 0:
        mean_score = 0
    else:
        log_mean = math.log10(max(mean_error, 1e-16))
        mean_score = max(0, min(25, (log_mean + 16) * 25 / 16))

    # ── Factor 3: Fraction of "dangerous" points (0-25 points) ──
    # How much of the input space is affected?
    # Threshold: relative error > 1e-6 (losing ~20+ bits)
    dangerous_count = sum(1 for e in valid_errors if e > 1e-6)
    danger_fraction = dangerous_count / len(valid_errors)
    fraction_score = danger_fraction * 25

    # ── Factor 4: Maximum bits lost (0-25 points) ──
    # Direct measure of catastrophic cancellation severity.
    # 52 bits = total loss → 25 points
    valid_bits = [b for b in bits_lost if not math.isnan(b)]
    max_bits = max(valid_bits) if valid_bits else 0
    bits_score = (max_bits / 52) * 25

    # ── Combine ──
    raw_score = peak_score + mean_score + fraction_score + bits_score
    score = int(max(0, min(100, round(raw_score))))

    # ── Label and Summary ──
    if score <= 20:
        label = "SAFE"
        summary = (
            f"Floating point errors are negligible. "
            f"Peak relative error: {peak_error:.2e}. "
            f"Maximum bits lost: {max_bits}/52."
        )
    elif score <= 40:
        label = "LOW"
        summary = (
            f"Minor precision loss detected. "
            f"Peak relative error: {peak_error:.2e}. "
            f"{dangerous_count}/{len(valid_errors)} points exceed safety threshold."
        )
    elif score <= 60:
        label = "MODERATE"
        summary = (
            f"Noticeable floating point errors. Results may be affected. "
            f"Peak relative error: {peak_error:.2e}, "
            f"max {max_bits} bits of precision lost."
        )
    elif score <= 80:
        label = "HIGH"
        summary = (
            f"Significant precision loss! "
            f"Peak relative error: {peak_error:.2e}. "
            f"{dangerous_count}/{len(valid_errors)} points show dangerous error levels. "
            f"Up to {max_bits}/52 mantissa bits corrupted."
        )
    else:
        label = "CRITICAL"
        summary = (
            f"CATASTROPHIC floating point errors detected! "
            f"Results are UNRELIABLE. "
            f"Peak relative error: {peak_error:.2e}. "
            f"{dangerous_count}/{len(valid_errors)} data points are corrupted. "
            f"{max_bits}/52 mantissa bits destroyed — nearly total precision loss."
        )

    return {
        "score": score,
        "label": label,
        "summary": summary,
        "breakdown": {
            "peak_error_score": round(peak_score, 1),
            "mean_error_score": round(mean_score, 1),
            "danger_fraction_score": round(fraction_score, 1),
            "bits_lost_score": round(bits_score, 1),
        },
    }
