<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Chart.js-4-FF6384?style=for-the-badge&logo=chart.js&logoColor=white" alt="Chart.js">
  <img src="https://img.shields.io/badge/IEEE_754-float64-orange?style=for-the-badge" alt="IEEE 754">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
</p>

<h1 align="center">⚡ Floating Point Error Analyzer</h1>

<p align="center">
  <strong>A real-time, interactive web dashboard that detects, quantifies, and visualizes catastrophic cancellation, floating-point drift, and precision loss in mathematical operations.</strong>
</p>

<p align="center">
  <em>See exactly where IEEE 754 arithmetic silently destroys your results — before your users do.</em>
</p>

---

## 🚀 One-Command Launch

```bash
git clone https://github.com/anivikal/floating-point.git
cd floating-point
./start.sh
```

That's it. The script installs dependencies, starts both servers, and opens the dashboard in your browser.

---

## 🧠 Why This Exists

Every programmer uses floating-point math. Almost nobody understands how it fails.

```python
>>> (1 + 1e-16) - 1
0.0                    # ← Should be 1e-16. ALL 52 bits of precision: gone.
```

This happens silently in production code — in financial systems, physics simulations, machine learning training loops, and scientific computing. Existing tools to detect these errors are either:

- **Academic CLI tools** (Herbie, CADNA, FPDebug) — powerful but require compilation, binary instrumentation, or domain expertise
- **Language-specific linters** (FPChecker, CRAFT) — tied to C/C++ and LLVM toolchains
- **Benchmark suites** (FPBench) — define standards but don't provide interactive analysis

**There is no interactive, visual, web-based tool that lets anyone — student, developer, or researcher — type an expression and instantly see where and how floating-point arithmetic fails.**

This project fills that gap.

---

## 🔬 How It Works

The system performs the **same computation twice**, in parallel:

| Engine | Precision | Purpose |
|--------|-----------|---------|
| Python `float` | 64-bit IEEE 754 (~15.9 decimal digits) | What your code actually computes |
| `mpmath` | 50 decimal digits (arbitrary precision) | The mathematical **ground truth** |

The *difference* between these two results is the floating-point error — the invisible bug in every computation. The dashboard visualizes this difference across varying inputs, iterations, or series lengths.

```
  Your Code (float64)          Ground Truth (mpmath 50-digit)
  ┌──────────────────┐         ┌──────────────────────────────┐
  │ (1 + 1e-16) - 1  │         │ (1 + 1e-16) - 1             │
  │ = 0.0 ❌          │         │ = 1.0000000000000000e-16 ✓  │
  └──────────────────┘         └──────────────────────────────┘
             │                              │
             └──────── COMPARE ─────────────┘
                         │
                 ┌───────▼───────┐
                 │ 52 bits lost  │
                 │ Danger: 82    │
                 │ ■■■■■■■■□□    │
                 └───────────────┘
```

---

## ✨ Features & Novelties

### 🎯 What Makes This Different from Existing Tools

| Feature | Herbie | FPDebug | CADNA | FPChecker | **This Tool** |
|---------|--------|---------|-------|-----------|---------------|
| Interactive web UI | ✗ | ✗ | ✗ | ✗ | **✓** |
| No installation / compilation | ✗ | ✗ | ✗ | ✗ | **✓** |
| Real-time visualization | ✗ | ✗ | ✗ | ✗ | **✓** |
| Custom expression input | ✓ | ✗ | ✗ | ✗ | **✓** |
| Danger severity scoring | ✗ | ✗ | Partial | ✗ | **✓ (0-100)** |
| Iterative drift tracking | ✗ | ✗ | ✗ | ✗ | **✓** |
| Kahan vs naive comparison | ✗ | ✗ | ✗ | ✗ | **✓** |
| Bits-of-precision metric | ✗ | ✓ | ✗ | ✗ | **✓** |
| Pre-built demo scenarios | ✗ | ✗ | ✗ | ✗ | **✓ (5 demos)** |
| API-first (JSON telemetry) | ✗ | ✗ | ✗ | ✗ | **✓** |
| Language-agnostic | ✗ | C/C++ | Fortran/C | C/C++ | **✓ (any math expression)** |

### 📊 Three Analysis Modes

#### 1. Catastrophic Cancellation Detector
Sweeps a variable across orders of magnitude (10⁻¹⁶ to 10⁻¹), exposing where subtraction of nearly-equal numbers destroys all significant digits.

**Classic test case:** `(1 + x) - 1` should always equal `x`. In float64, it returns **0** when x < 10⁻¹⁶.

#### 2. Iterative Drift Analyzer
Tracks how microscopic per-step rounding errors (10⁻¹⁶) compound into macroscopic errors over thousands of iterations. This is how financial calculations, physics engines, and ML training loops silently diverge from mathematical reality.

#### 3. Summation Error Comparator
Compares **three** summation strategies side-by-side:
- **Naive summation** — just `+=` (what most code does)
- **Kahan compensated summation** — error-correcting algorithm that recovers lost low-order bits
- **mpmath ground truth** — mathematically exact result

Supports: Harmonic (Σ 1/n), Basel (Σ 1/n²), Alternating Harmonic (Σ (-1)^(n+1)/n), Geometric (Σ 0.9999^n)

### 🎨 Dashboard Features

- **Animated Danger Gauge** — 0-100 severity score with color-coded conic gradient (SAFE → CRITICAL)
- **Divergence Line Chart** — Float vs Ground Truth plotted in real-time
- **Precision Loss Bar Chart** — Color-coded bits lost per data point (green/yellow/orange/red)
- **Point-by-point Annotations** — Exact locations and severity of each catastrophic event
- **Computation Metadata** — Precision digits, IEEE format, computation time, expression details
- **5 One-click Demo Scenarios** — Instant showcasing with pre-tuned parameters
- **Auto Health Check** — Live API status indicator with auto-reconnect

### 🏗️ Architecture

- **Decoupled full-stack** — Backend API and frontend are fully independent
- **Structured JSON telemetry** — API returns chart-ready data arrays, not raw numbers
- **Safe expression evaluation** — Whitelist-based sandboxed `eval()` with no builtins, no imports
- **Swagger/OpenAPI docs** — Auto-generated at `/docs`
- **CORS-enabled** — Ready for any frontend or external integration

---

## 📁 Project Structure

```
floating-point/
├── start.sh                  # One-command launcher (installs deps, starts servers, opens browser)
├── backend/
│   ├── main.py               # FastAPI app — routes, CORS, Pydantic models, 5 demo scenarios
│   ├── engine.py              # Core computation engine — 3 analysis modes, safe expression eval
│   ├── danger_score.py        # Weighted 0-100 severity scoring (peak error, mean, bits lost)
│   └── requirements.txt       # Python dependencies
├── frontend/
│   ├── index.html             # Dashboard layout — tabs, panels, charts, gauge
│   ├── index.css              # Dark-mode design system — glassmorphism, animations
│   └── app.js                 # Chart.js integration, dynamic forms, API calls, animated gauge
├── .gitignore
└── README.md
```

---

## 🔌 API Reference

### `POST /api/analyze`

Run a floating-point error analysis.

**Request:**
```json
{
  "mode": "catastrophic_cancellation",
  "params": {
    "expression": "(1 + x) - 1",
    "variable": "x",
    "range_start": -16,
    "range_end": -1,
    "num_points": 80
  }
}
```

**Response:**
```json
{
  "status": "success",
  "mode": "catastrophic_cancellation",
  "danger_score": 82,
  "danger_label": "CRITICAL",
  "summary": "CATASTROPHIC floating point errors detected! 52/52 mantissa bits destroyed...",
  "telemetry": {
    "labels": ["1e-16.0", "1e-14.7", "..."],
    "float_values": [0.0, 4.66e-15, "..."],
    "ground_truth_values": [1e-16, 4.64e-15, "..."],
    "absolute_errors": [1e-16, "..."],
    "relative_errors": [1.0, "..."],
    "bits_lost": [52, 49, "..."]
  },
  "annotations": [
    {
      "index": 0,
      "type": "catastrophic_cancellation",
      "severity": "critical",
      "message": "Catastrophic cancellation at x=1e-16.0: 52 bits lost. Float=0.0, Truth=1e-16"
    }
  ],
  "metadata": {
    "precision_digits": 50,
    "ieee_precision": "float64 (52-bit mantissa)",
    "computation_time_ms": 9.72
  }
}
```

### `GET /api/examples`
Returns all 5 pre-built demo scenarios with their parameters.

### `GET /api/health`
Engine health check.

### Swagger Docs
Interactive API docs available at `http://localhost:8000/docs` when the server is running.

---

## 🎓 The Math Behind It

### Why Do These Errors Happen?

**IEEE 754 double-precision** stores numbers in 64 bits:
- 1 sign bit
- 11 exponent bits
- **52 mantissa bits** (~15.9 decimal digits of precision)

This means `float64` can only represent a **finite subset** of real numbers. Every arithmetic operation rounds the mathematical result to the nearest representable float. Usually this is fine — but three patterns cause catastrophic failures:

| Pattern | What Happens | Example |
|---------|-------------|---------|
| **Catastrophic Cancellation** | Subtracting nearly-equal numbers amplifies relative error | `(1+1e-16) - 1 = 0` instead of `1e-16` |
| **Iterative Drift** | Tiny per-step rounding errors compound exponentially | `x *= 1.0000001` × 10M iterations |
| **Swamping** | Adding a tiny number to a large accumulator loses the small bits | `Σ 1/n` for large n |

### The Danger Score Algorithm

The score (0-100) is a weighted sum of four independent factors:

| Factor | Weight | What It Measures |
|--------|--------|-----------------|
| Peak relative error | 25 pts | Worst single point (log₁₀ scale) |
| Mean relative error | 25 pts | Overall error trend |
| Danger fraction | 25 pts | % of points exceeding 10⁻⁶ relative error |
| Max bits lost | 25 pts | Worst-case mantissa corruption (out of 52) |

---

## 🛠️ Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Backend API | Python 3.10+ / FastAPI | Async, auto-docs, Pydantic validation |
| Ground Truth | mpmath (50-digit) | Gold standard arbitrary-precision library |
| Standard Precision | Python `float` | Native IEEE 754 binary64 — same as C `double` |
| Frontend | Vanilla JS + Chart.js 4 | Zero build step, beautiful animated charts |
| Styling | Vanilla CSS | Glassmorphism, dark-mode, micro-animations |
| Launcher | Bash | Cross-platform (macOS/Linux), zero config |

---

## 📚 Prior Art & References

This project builds on decades of floating-point research:

| Tool/Paper | What It Does | Limitation This Project Addresses |
|-----------|-------------|----------------------------------|
| [Herbie](https://herbie.uwplse.org/) (UW/Utah) | Auto-rewrites expressions for accuracy | No visualization, no web UI, no iterative analysis |
| [FPBench](https://fpbench.org/) | Benchmark standard for FP tools | Defines standards, not interactive analysis |
| [FPDebug](https://github.com/fbenz/FPDebug) | Shadow execution error detection | Requires binary instrumentation, C/C++ only |
| [CADNA](https://cadna.lip6.fr/) | Stochastic arithmetic error estimation | Fortran/C only, no web interface |
| [CRAFT](https://github.com/crafthpc/craft) | Mixed-precision analysis via Dyninst | Requires compilation, C/C++ only |
| [FPChecker](https://github.com/LLNL/FPChecker) | LLVM-based FP exception detection | Tied to LLVM/Clang toolchain |
| [Goldberg 1991](https://docs.oracle.com/cd/E19957-01/806-3568/ncg_goldberg.html) | "What Every Computer Scientist Should Know About Floating-Point Arithmetic" | Foundational paper — no tooling |
| [Kahan Summation](https://en.wikipedia.org/wiki/Kahan_summation_algorithm) | Error-compensated summation algorithm | Our tool visualizes *why* it works |

---

## 📄 License

MIT — use it, fork it, learn from it.

---

<p align="center">
  <strong>Built to make the invisible visible.</strong><br>
  <em>Because every digit you lose is a bug you didn't know you had.</em>
</p>
