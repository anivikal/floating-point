"""
Floating Point Error Analyzer — Core Computation Engine
========================================================

This module is the mathematical heart of the system. It implements three
analysis modes that expose how IEEE 754 double-precision floating point
arithmetic silently destroys precision in common computations.

Each analyzer performs the SAME computation twice:
  1. Using Python's native `float` (IEEE 754 binary64, ~15.9 decimal digits)
  2. Using `mpmath` with 50-digit precision (the "Ground Truth")

The *difference* between these two results IS the floating point error
that most programmers never see.

Architecture Note:
  Each analysis function returns a standardized `TelemetryResult` dict
  compatible with the API response schema. This decouples the math from
  the transport layer.
"""

import math
import time
from typing import Any
import mpmath

# ──────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────

# Set mpmath to 50 decimal digits — far beyond float64's ~15.9 digits.
# This is our "ground truth" baseline. Any result that differs from this
# is evidence of floating point error.
mpmath.mp.dps = 50

# Safe math functions available in user expressions.
# We whitelist these to prevent arbitrary code execution via eval().
SAFE_FLOAT_FUNCS = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "exp": math.exp,
    "log": math.log,
    "abs": abs,
    "pi": math.pi,
    "e": math.e,
}

SAFE_MP_FUNCS = {
    "sqrt": mpmath.sqrt,
    "sin": mpmath.sin,
    "cos": mpmath.cos,
    "tan": mpmath.tan,
    "exp": mpmath.exp,
    "log": mpmath.log,
    "abs": abs,
    "pi": mpmath.pi,
    "e": mpmath.e,
}


# ──────────────────────────────────────────────────────────────────────
# Safe Expression Evaluator
# ──────────────────────────────────────────────────────────────────────

def _safe_eval_float(expression: str, variable: str, value: float) -> float:
    """
    Evaluate a math expression using standard Python floats.

    Security: We restrict the namespace to only whitelisted math functions.
    No builtins, no imports, no file access — just arithmetic.

    Args:
        expression: Math expression string, e.g. "(1 + x) - 1"
        variable: Variable name used in the expression, e.g. "x"
        value: The float value to substitute for the variable

    Returns:
        The float result of evaluating the expression
    """
    namespace = {"__builtins__": {}, variable: value}
    namespace.update(SAFE_FLOAT_FUNCS)
    return float(eval(expression, namespace))  # noqa: S307


def _safe_eval_mpmath(expression: str, variable: str, value) -> mpmath.mpf:
    """
    Evaluate the SAME expression using mpmath arbitrary precision.

    This is our "ground truth" — we compute with 50 digits of precision
    so we can measure exactly how much precision the float version lost.

    Args:
        expression: Math expression string (same as float version)
        variable: Variable name
        value: mpmath.mpf value for the variable

    Returns:
        The mpmath result (50-digit precision)
    """
    namespace = {"__builtins__": {}, variable: mpmath.mpf(value)}
    namespace.update(SAFE_MP_FUNCS)
    return mpmath.mpf(eval(expression, namespace))  # noqa: S307


# ──────────────────────────────────────────────────────────────────────
# Utility: Compute error metrics for a single data point
# ──────────────────────────────────────────────────────────────────────

def _compute_error_metrics(float_val: float, truth_val: mpmath.mpf) -> dict:
    """
    Compute comprehensive error metrics comparing float vs ground truth.

    "Bits lost" is the key metric for catastrophic cancellation:
    - 0 bits lost = perfect agreement
    - 52 bits lost = ALL precision destroyed (float64 has 52 mantissa bits)
    - >10 bits lost = generally considered "catastrophic"

    The formula: bits_lost = -log2(relative_error)
    But we must handle the edge case where the float result is exactly
    correct (relative_error = 0) or completely wrong (float = 0, truth ≠ 0).
    """
    truth_float = float(truth_val)
    abs_error = abs(float_val - truth_float)

    # Relative error: |float - truth| / |truth|
    # Edge case: if truth is 0, relative error is the absolute value of float
    if truth_float != 0:
        rel_error = abs_error / abs(truth_float)
    elif float_val != 0:
        rel_error = float("inf")
    else:
        rel_error = 0.0

    # Bits of precision lost
    # A float64 has 52 mantissa bits. If relative error is ~2^(-k),
    # then we've lost (52 - k) bits of precision.
    if rel_error == 0:
        bits_lost = 0
    elif rel_error >= 1.0:
        bits_lost = 52  # Total loss — result is meaningless
    else:
        try:
            bits_lost = max(0, min(52, int(-math.log2(rel_error))))
            bits_lost = 52 - bits_lost  # Invert: higher = worse
        except (ValueError, OverflowError):
            bits_lost = 52

    return {
        "float_value": float_val,
        "ground_truth": truth_float,
        "absolute_error": abs_error,
        "relative_error": min(rel_error, 1e308),  # Cap for JSON serialization
        "bits_lost": bits_lost,
    }


# ──────────────────────────────────────────────────────────────────────
# Analysis Mode 1: Catastrophic Cancellation
# ──────────────────────────────────────────────────────────────────────

def analyze_catastrophic_cancellation(
    expression: str,
    variable: str = "x",
    range_start: float = -16,
    range_end: float = -1,
    num_points: int = 100,
) -> dict[str, Any]:
    """
    Detect catastrophic cancellation in an expression by sweeping a
    variable across magnitudes.

    THE CLASSIC EXAMPLE: f(x) = (1 + x) - 1
    ─────────────────────────────────────────
    Mathematically, this should always equal x. But in floating point:
    - When x = 1e-1:  float correctly returns 1e-1        ✓
    - When x = 1e-10: float returns 1.000000082...e-10    (small error)
    - When x = 1e-16: float returns **0**                 ← CATASTROPHE!

    Why? Because (1 + 1e-16) rounds to exactly 1.0 in float64.
    Subtracting 1 gives 0, not 1e-16. ALL significant digits are lost.

    This function sweeps x from 10^range_start to 10^range_end, computing
    the expression in both float and mpmath, measuring the error at each point.

    The output is an array of telemetry points perfect for plotting
    a divergence chart.
    """
    start_time = time.perf_counter()
    annotations = []

    # Generate logarithmically-spaced test points
    # Using log scale because floating point errors manifest across
    # orders of magnitude, not linear ranges
    exponents = [
        range_start + i * (range_end - range_start) / (num_points - 1)
        for i in range(num_points)
    ]

    labels = []
    float_values = []
    ground_truth_values = []
    absolute_errors = []
    relative_errors = []
    bits_lost_arr = []

    for idx, exp in enumerate(exponents):
        x_val = 10.0 ** exp

        try:
            # Compute with standard float (IEEE 754 double)
            f_result = _safe_eval_float(expression, variable, x_val)

            # Compute with 50-digit precision (Ground Truth)
            mp_result = _safe_eval_mpmath(expression, variable, mpmath.mpf(10) ** mpmath.mpf(exp))

            metrics = _compute_error_metrics(f_result, mp_result)

            labels.append(f"1e{exp:.1f}")
            float_values.append(metrics["float_value"])
            ground_truth_values.append(metrics["ground_truth"])
            absolute_errors.append(metrics["absolute_error"])
            relative_errors.append(metrics["relative_error"])
            bits_lost_arr.append(metrics["bits_lost"])

            # Annotate catastrophic events (>40 bits lost = nearly total loss)
            if metrics["bits_lost"] >= 40:
                annotations.append({
                    "index": idx,
                    "type": "catastrophic_cancellation",
                    "message": (
                        f"Catastrophic cancellation at x=1e{exp:.1f}: "
                        f"{metrics['bits_lost']} bits lost. "
                        f"Float={f_result}, Truth={float(mp_result)}"
                    ),
                    "severity": "critical",
                })
            elif metrics["bits_lost"] >= 20:
                annotations.append({
                    "index": idx,
                    "type": "significant_error",
                    "message": (
                        f"Significant precision loss at x=1e{exp:.1f}: "
                        f"{metrics['bits_lost']} bits lost."
                    ),
                    "severity": "warning",
                })

        except Exception as e:
            # If evaluation fails at a specific point, record NaN
            labels.append(f"1e{exp:.1f}")
            float_values.append(float("nan"))
            ground_truth_values.append(float("nan"))
            absolute_errors.append(float("nan"))
            relative_errors.append(float("nan"))
            bits_lost_arr.append(0)

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    return {
        "telemetry": {
            "labels": labels,
            "float_values": float_values,
            "ground_truth_values": ground_truth_values,
            "absolute_errors": absolute_errors,
            "relative_errors": relative_errors,
            "bits_lost": bits_lost_arr,
        },
        "annotations": annotations,
        "metadata": {
            "precision_digits": mpmath.mp.dps,
            "ieee_precision": "float64 (52-bit mantissa)",
            "computation_time_ms": round(elapsed_ms, 2),
            "expression": expression,
            "variable": variable,
            "range": f"10^{range_start} to 10^{range_end}",
            "num_points": num_points,
        },
    }


# ──────────────────────────────────────────────────────────────────────
# Analysis Mode 2: Iterative Drift
# ──────────────────────────────────────────────────────────────────────

def analyze_iterative_drift(
    expression: str,
    initial_value: float = 1.0,
    iterations: int = 10000,
    sample_every: int = 100,
) -> dict[str, Any]:
    """
    Track how floating point errors accumulate over repeated iterations.

    THE INSIGHT: Even a tiny per-step error (~1e-16) can compound into
    a MASSIVE error after enough iterations. This is exactly what happens
    in physics simulations, financial calculations, and ML training loops.

    EXAMPLE: x = x * 1.0000001 (repeated 10,000,000 times)
    - After 1M iterations: ~0.001% error
    - After 10M iterations: ~0.1% error
    - After 100M iterations: error DOMINATES the signal

    This function runs the expression iteratively in both float and mpmath,
    sampling at regular intervals to produce a time series of error growth.
    """
    start_time = time.perf_counter()
    annotations = []

    # Initialize both trackers
    float_x = float(initial_value)
    mp_x = mpmath.mpf(initial_value)

    labels = ["0"]
    float_values = [float_x]
    ground_truth_values = [float(mp_x)]
    absolute_errors = [0.0]
    relative_errors = [0.0]
    bits_lost_arr = [0]

    prev_rel_error = 0.0

    for i in range(1, iterations + 1):
        try:
            # Advance float version
            float_x = _safe_eval_float(expression, "x", float_x)
            # Advance ground truth version
            mp_x = _safe_eval_mpmath(expression, "x", mp_x)
        except Exception:
            break

        # Sample at regular intervals (don't record every single iteration
        # — that would be millions of data points and murder the chart)
        if i % sample_every == 0 or i == iterations:
            metrics = _compute_error_metrics(float_x, mp_x)

            labels.append(str(i))
            float_values.append(metrics["float_value"])
            ground_truth_values.append(metrics["ground_truth"])
            absolute_errors.append(metrics["absolute_error"])
            relative_errors.append(metrics["relative_error"])
            bits_lost_arr.append(metrics["bits_lost"])

            # Detect when error crosses critical thresholds
            curr_rel_error = metrics["relative_error"]
            if prev_rel_error < 0.01 and curr_rel_error >= 0.01:
                annotations.append({
                    "index": len(labels) - 1,
                    "type": "threshold_crossed",
                    "message": f"Error exceeded 1% at iteration {i}",
                    "severity": "warning",
                })
            if prev_rel_error < 0.1 and curr_rel_error >= 0.1:
                annotations.append({
                    "index": len(labels) - 1,
                    "type": "threshold_crossed",
                    "message": f"Error exceeded 10% at iteration {i}",
                    "severity": "critical",
                })
            prev_rel_error = curr_rel_error

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    return {
        "telemetry": {
            "labels": labels,
            "float_values": float_values,
            "ground_truth_values": ground_truth_values,
            "absolute_errors": absolute_errors,
            "relative_errors": relative_errors,
            "bits_lost": bits_lost_arr,
        },
        "annotations": annotations,
        "metadata": {
            "precision_digits": mpmath.mp.dps,
            "ieee_precision": "float64 (52-bit mantissa)",
            "computation_time_ms": round(elapsed_ms, 2),
            "expression": expression,
            "initial_value": initial_value,
            "iterations": iterations,
            "sample_every": sample_every,
        },
    }


# ──────────────────────────────────────────────────────────────────────
# Analysis Mode 3: Summation Error
# ──────────────────────────────────────────────────────────────────────

def analyze_summation_error(
    series: str = "harmonic",
    terms: int = 100000,
    sample_every: int = 1000,
) -> dict[str, Any]:
    """
    Compare naive floating point summation vs. ground truth for common series.

    THE PROBLEM WITH NAIVE SUMMATION:
    ────────────────────────────────
    When you add a tiny number to a large accumulator, the tiny number
    gets rounded away. This is called "swamping."

    Example (Harmonic Series: Σ 1/n):
    - After 10K terms, accumulator ≈ 9.78
    - Adding 1/10001 ≈ 0.0001 to 9.78
    - In float64, 9.78 + 0.0001 = 9.7801 (looks fine)
    - But the LAST few digits of 0.0001 are silently lost
    - After 100K terms, these tiny losses accumulate

    This function provides THREE traces:
    1. Naive float summation (just +=)
    2. Kahan compensated summation (error-correcting algorithm)
    3. mpmath ground truth (50-digit precision)

    Supported series: "harmonic" (1/n), "inverse_squares" (1/n²),
    "alternating" ((-1)^n/n), "geometric" (0.9999^n)
    """
    start_time = time.perf_counter()
    annotations = []

    # Series term generators
    series_funcs = {
        "harmonic": {
            "float": lambda n: 1.0 / n,
            "mp": lambda n: mpmath.mpf(1) / mpmath.mpf(n),
            "name": "Harmonic Series (Σ 1/n)",
        },
        "inverse_squares": {
            "float": lambda n: 1.0 / (n * n),
            "mp": lambda n: mpmath.mpf(1) / (mpmath.mpf(n) ** 2),
            "name": "Basel Series (Σ 1/n²)",
        },
        "alternating": {
            "float": lambda n: ((-1.0) ** (n + 1)) / n,
            "mp": lambda n: (mpmath.mpf(-1) ** (n + 1)) / mpmath.mpf(n),
            "name": "Alternating Harmonic (Σ (-1)^(n+1)/n)",
        },
        "geometric": {
            "float": lambda n: 0.9999 ** n,
            "mp": lambda n: mpmath.mpf("0.9999") ** mpmath.mpf(n),
            "name": "Geometric (Σ 0.9999^n)",
        },
    }

    if series not in series_funcs:
        series = "harmonic"

    sf = series_funcs[series]

    # ── Naive float sum ──
    naive_sum = 0.0
    # ── Kahan compensated sum ──
    kahan_sum = 0.0
    kahan_c = 0.0  # Compensation variable (running error)
    # ── Ground truth (mpmath) ──
    mp_sum = mpmath.mpf(0)

    labels = []
    float_values = []
    kahan_values = []
    ground_truth_values = []
    absolute_errors = []
    relative_errors = []
    bits_lost_arr = []

    for n in range(1, terms + 1):
        # Compute the n-th term
        f_term = sf["float"](n)
        mp_term = sf["mp"](n)

        # Naive summation: just add. No error tracking.
        naive_sum += f_term

        # Kahan summation: the clever trick.
        # `kahan_c` tracks the small bits that got rounded off.
        # Each step, we add back the compensation before adding the new term.
        y = f_term - kahan_c
        t = kahan_sum + y
        kahan_c = (t - kahan_sum) - y  # Recovers the lost low-order bits
        kahan_sum = t

        # Ground truth: mpmath just handles it with 50 digits
        mp_sum += mp_term

        # Sample at intervals
        if n % sample_every == 0 or n == terms:
            truth = float(mp_sum)
            naive_err = abs(naive_sum - truth)
            naive_rel = naive_err / abs(truth) if truth != 0 else 0.0

            if naive_rel == 0:
                bl = 0
            elif naive_rel >= 1.0:
                bl = 52
            else:
                try:
                    bl = max(0, min(52, 52 - int(-math.log2(naive_rel))))
                except (ValueError, OverflowError):
                    bl = 52

            labels.append(str(n))
            float_values.append(naive_sum)
            kahan_values.append(kahan_sum)
            ground_truth_values.append(truth)
            absolute_errors.append(naive_err)
            relative_errors.append(naive_rel)
            bits_lost_arr.append(bl)

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    return {
        "telemetry": {
            "labels": labels,
            "float_values": float_values,
            "kahan_values": kahan_values,
            "ground_truth_values": ground_truth_values,
            "absolute_errors": absolute_errors,
            "relative_errors": relative_errors,
            "bits_lost": bits_lost_arr,
        },
        "annotations": annotations,
        "metadata": {
            "precision_digits": mpmath.mp.dps,
            "ieee_precision": "float64 (52-bit mantissa)",
            "computation_time_ms": round(elapsed_ms, 2),
            "series": series,
            "series_name": sf["name"],
            "terms": terms,
            "sample_every": sample_every,
        },
    }
