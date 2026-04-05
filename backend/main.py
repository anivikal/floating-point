"""
Floating Point Error Analyzer — FastAPI Application
====================================================

REST API that exposes the computation engine to the frontend dashboard.

Endpoints:
  POST /api/analyze      — Run a floating point analysis
  GET  /api/examples     — Get pre-built demo scenarios
  GET  /api/health       — Health check

Security:
  - CORS enabled for local development
  - Expression inputs are sandboxed (no builtins, whitelist only)
  - Request validation via Pydantic models
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Any

from engine import (
    analyze_catastrophic_cancellation,
    analyze_iterative_drift,
    analyze_summation_error,
)
from danger_score import compute_danger_score

# ──────────────────────────────────────────────────────────────────────
# FastAPI App Setup
# ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Floating Point Error Analyzer",
    description=(
        "Detects, analyzes, and visualizes catastrophic cancellation, "
        "floating-point drift, and precision loss in mathematical operations."
    ),
    version="1.0.0",
)

# Enable CORS for frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, lock this down
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────────────────────────────
# Request / Response Models
# ──────────────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    """
    Unified request model for all analysis modes.

    The `mode` field determines which engine to invoke,
    and `params` contains mode-specific parameters.
    """
    mode: str = Field(
        ...,
        description="Analysis mode: 'catastrophic_cancellation', 'iterative_drift', or 'summation_error'",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Mode-specific parameters",
    )


class AnalyzeResponse(BaseModel):
    """Structured response with telemetry, danger score, and annotations."""
    status: str
    mode: str
    danger_score: int
    danger_label: str
    summary: str
    telemetry: dict[str, Any]
    annotations: list[dict[str, Any]]
    metadata: dict[str, Any]


# ──────────────────────────────────────────────────────────────────────
# Pre-built Demo Scenarios
# ──────────────────────────────────────────────────────────────────────

EXAMPLES = [
    {
        "id": "classic_cancellation",
        "name": "The Classic: (1+x) − 1",
        "description": (
            "Subtracting nearly-equal numbers destroys significant digits. "
            "When x is tiny, (1+x) rounds to 1.0, making the result 0 instead of x."
        ),
        "mode": "catastrophic_cancellation",
        "params": {
            "expression": "(1 + x) - 1",
            "variable": "x",
            "range_start": -16,
            "range_end": -1,
            "num_points": 80,
        },
    },
    {
        "id": "quadratic_instability",
        "name": "Quadratic Formula Instability",
        "description": (
            "Computing sqrt(b² - 4ac) when b² ≈ 4ac causes catastrophic "
            "cancellation in the discriminant. Common in scientific computing."
        ),
        "mode": "catastrophic_cancellation",
        "params": {
            "expression": "sqrt((1 + x)**2 - 1)",
            "variable": "x",
            "range_start": -10,
            "range_end": -1,
            "num_points": 80,
        },
    },
    {
        "id": "compound_interest_drift",
        "name": "Compound Interest Drift",
        "description": (
            "Tiny per-step rounding errors compound over thousands of iterations. "
            "This simulates how financial calculations silently lose precision."
        ),
        "mode": "iterative_drift",
        "params": {
            "expression": "x * 1.0000001",
            "initial_value": 1.0,
            "iterations": 50000,
            "sample_every": 500,
        },
    },
    {
        "id": "harmonic_series",
        "name": "Harmonic Series Summation",
        "description": (
            "Summing 1/n for large N. Each small term gets its low-order bits "
            "swamped by the large accumulator, silently losing precision."
        ),
        "mode": "summation_error",
        "params": {
            "series": "harmonic",
            "terms": 100000,
            "sample_every": 1000,
        },
    },
    {
        "id": "alternating_series",
        "name": "Alternating Series Cancellation",
        "description": (
            "Σ (-1)^(n+1)/n: alternating signs amplify cancellation errors. "
            "Positive and negative terms fight each other, destroying precision."
        ),
        "mode": "summation_error",
        "params": {
            "series": "alternating",
            "terms": 100000,
            "sample_every": 1000,
        },
    },
]


# ──────────────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "engine": "Floating Point Error Analyzer v1.0"}


@app.get("/api/examples")
async def get_examples():
    """Return the pre-built demo scenarios for the frontend."""
    return {"examples": EXAMPLES}


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    """
    Run a floating point error analysis.

    Dispatches to the appropriate engine based on `mode`,
    then computes the danger score from the telemetry.
    """
    mode = request.mode
    params = request.params

    try:
        if mode == "catastrophic_cancellation":
            result = analyze_catastrophic_cancellation(
                expression=params.get("expression", "(1 + x) - 1"),
                variable=params.get("variable", "x"),
                range_start=float(params.get("range_start", -16)),
                range_end=float(params.get("range_end", -1)),
                num_points=int(params.get("num_points", 100)),
            )
        elif mode == "iterative_drift":
            result = analyze_iterative_drift(
                expression=params.get("expression", "x * 1.0000001"),
                initial_value=float(params.get("initial_value", 1.0)),
                iterations=min(int(params.get("iterations", 10000)), 500000),  # Cap at 500K
                sample_every=max(int(params.get("sample_every", 100)), 1),
            )
        elif mode == "summation_error":
            result = analyze_summation_error(
                series=params.get("series", "harmonic"),
                terms=min(int(params.get("terms", 100000)), 500000),  # Cap at 500K
                sample_every=max(int(params.get("sample_every", 1000)), 1),
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown mode: '{mode}'. Must be 'catastrophic_cancellation', 'iterative_drift', or 'summation_error'.",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Engine error: {str(e)}. Check your expression syntax.",
        )

    # Compute the danger score from telemetry
    danger = compute_danger_score(result["telemetry"])

    return AnalyzeResponse(
        status="success",
        mode=mode,
        danger_score=danger["score"],
        danger_label=danger["label"],
        summary=danger["summary"],
        telemetry=result["telemetry"],
        annotations=result["annotations"],
        metadata=result["metadata"],
    )


# ──────────────────────────────────────────────────────────────────────
# Entry Point
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
