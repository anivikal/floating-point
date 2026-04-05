/**
 * Floating Point Error Analyzer — Frontend Application
 * =====================================================
 *
 * Handles:
 *  - Tab switching between analysis modes
 *  - Dynamic form rendering per mode
 *  - API communication with the backend
 *  - Chart.js initialization and live updates
 *  - Animated danger score gauge
 *  - Example scenario loading
 */

// ──────────────────────────────────────────────────────────────────────
// Configuration
// ──────────────────────────────────────────────────────────────────────

const API_BASE = "http://localhost:8000";

// Chart.js global defaults for dark theme
Chart.defaults.color = "#9090aa";
Chart.defaults.borderColor = "rgba(255, 255, 255, 0.04)";
Chart.defaults.font.family =
    "'Inter', -apple-system, BlinkMacSystemFont, sans-serif";

// ──────────────────────────────────────────────────────────────────────
// State
// ──────────────────────────────────────────────────────────────────────

let currentMode = "catastrophic_cancellation";
let divergenceChart = null;
let errorChart = null;
let examples = [];

// ──────────────────────────────────────────────────────────────────────
// Form Definitions — what inputs to show per mode
// ──────────────────────────────────────────────────────────────────────

const FORM_DEFINITIONS = {
    catastrophic_cancellation: [
        {
            key: "expression",
            label: "Expression",
            type: "text",
            value: "(1 + x) - 1",
            hint: 'Use x as the sweep variable. Functions: sqrt, sin, cos, exp, log',
            fullWidth: true,
        },
        { key: "variable", label: "Variable", type: "text", value: "x" },
        { key: "range_start", label: "Exponent Start", type: "number", value: -16, hint: "10^this" },
        { key: "range_end", label: "Exponent End", type: "number", value: -1, hint: "10^this" },
        { key: "num_points", label: "Data Points", type: "number", value: 80 },
    ],
    iterative_drift: [
        {
            key: "expression",
            label: "Iteration Expression",
            type: "text",
            value: "x * 1.0000001",
            hint: "x is the running value each iteration",
            fullWidth: true,
        },
        { key: "initial_value", label: "Initial Value", type: "number", value: 1.0 },
        { key: "iterations", label: "Iterations", type: "number", value: 50000 },
        { key: "sample_every", label: "Sample Every", type: "number", value: 500 },
    ],
    summation_error: [
        {
            key: "series",
            label: "Series Type",
            type: "select",
            options: [
                { value: "harmonic", label: "Harmonic (Σ 1/n)" },
                { value: "inverse_squares", label: "Basel (Σ 1/n²)" },
                { value: "alternating", label: "Alternating (Σ (-1)^(n+1)/n)" },
                { value: "geometric", label: "Geometric (Σ 0.9999^n)" },
            ],
            value: "harmonic",
        },
        { key: "terms", label: "Number of Terms", type: "number", value: 100000 },
        { key: "sample_every", label: "Sample Every", type: "number", value: 1000 },
    ],
};

// ──────────────────────────────────────────────────────────────────────
// Initialization
// ──────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
    initTabs();
    renderForm(currentMode);
    initCharts();
    fetchExamples();
    checkApiHealth();

    document.getElementById("btn-analyze").addEventListener("click", runAnalysis);
});

// ──────────────────────────────────────────────────────────────────────
// Tab Management
// ──────────────────────────────────────────────────────────────────────

function initTabs() {
    const tabs = document.querySelectorAll("#mode-tabs .tab");
    tabs.forEach((tab) => {
        tab.addEventListener("click", () => {
            tabs.forEach((t) => {
                t.classList.remove("active");
                t.setAttribute("aria-selected", "false");
            });
            tab.classList.add("active");
            tab.setAttribute("aria-selected", "true");

            currentMode = tab.dataset.mode;
            renderForm(currentMode);
        });
    });
}

// ──────────────────────────────────────────────────────────────────────
// Dynamic Form Rendering
// ──────────────────────────────────────────────────────────────────────

function renderForm(mode) {
    const container = document.getElementById("param-form");
    const fields = FORM_DEFINITIONS[mode];
    if (!fields) return;

    container.innerHTML = fields
        .map((f) => {
            let input = "";
            if (f.type === "select") {
                const opts = f.options
                    .map(
                        (o) =>
                            `<option value="${o.value}" ${o.value === f.value ? "selected" : ""}>${o.label}</option>`
                    )
                    .join("");
                input = `<select id="field-${f.key}" data-key="${f.key}">${opts}</select>`;
            } else {
                input = `<input type="${f.type}" id="field-${f.key}" data-key="${f.key}" value="${f.value}" />`;
            }

            const hint = f.hint ? `<span class="hint">${f.hint}</span>` : "";
            const style = f.fullWidth ? ' style="grid-column: 1 / -1"' : "";

            return `
                <div class="form-group"${style}>
                    <label for="field-${f.key}">${f.label}</label>
                    ${input}
                    ${hint}
                </div>
            `;
        })
        .join("");
}

function getFormParams() {
    const fields = FORM_DEFINITIONS[currentMode];
    const params = {};
    fields.forEach((f) => {
        const el = document.getElementById(`field-${f.key}`);
        if (!el) return;
        params[f.key] =
            f.type === "number" ? parseFloat(el.value) : el.value;
    });
    return params;
}

function setFormParams(mode, params) {
    // Switch to the correct tab first
    const tabs = document.querySelectorAll("#mode-tabs .tab");
    tabs.forEach((t) => {
        t.classList.remove("active");
        t.setAttribute("aria-selected", "false");
        if (t.dataset.mode === mode) {
            t.classList.add("active");
            t.setAttribute("aria-selected", "true");
        }
    });

    currentMode = mode;
    renderForm(mode);

    // Fill in the parameter values
    requestAnimationFrame(() => {
        Object.entries(params).forEach(([key, value]) => {
            const el = document.getElementById(`field-${key}`);
            if (el) el.value = value;
        });
    });
}

// ──────────────────────────────────────────────────────────────────────
// Examples
// ──────────────────────────────────────────────────────────────────────

async function fetchExamples() {
    try {
        const resp = await fetch(`${API_BASE}/api/examples`);
        const data = await resp.json();
        examples = data.examples;
        renderExamples();
    } catch (e) {
        console.warn("Could not fetch examples:", e);
        // Use fallback hardcoded examples
        examples = [];
    }
}

function renderExamples() {
    const grid = document.getElementById("examples-grid");
    if (!examples.length) {
        grid.innerHTML = '<p class="placeholder-text">Examples unavailable.</p>';
        return;
    }

    grid.innerHTML = examples
        .map(
            (ex, i) => `
        <button class="example-btn" data-index="${i}" id="example-${ex.id}">
            <span class="example-name">${ex.name}</span>
            <span class="example-desc">${ex.description}</span>
        </button>
    `
        )
        .join("");

    grid.querySelectorAll(".example-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            const ex = examples[parseInt(btn.dataset.index)];
            setFormParams(ex.mode, ex.params);
            // Auto-run the analysis after loading the example
            setTimeout(() => runAnalysis(), 200);
        });
    });
}

// ──────────────────────────────────────────────────────────────────────
// API Health Check
// ──────────────────────────────────────────────────────────────────────

async function checkApiHealth() {
    const dot = document.querySelector(".badge-dot");
    const status = document.getElementById("api-status");
    const btn = document.getElementById("btn-analyze");

    try {
        const resp = await fetch(`${API_BASE}/api/health`);
        if (resp.ok) {
            dot.classList.add("connected");
            status.textContent = "Engine Online";
            btn.disabled = false;
        }
    } catch {
        dot.classList.remove("connected");
        status.textContent = "Engine Offline";
        btn.disabled = true;

        // Retry every 3 seconds
        setTimeout(checkApiHealth, 3000);
    }
}

// ──────────────────────────────────────────────────────────────────────
// Analysis Execution
// ──────────────────────────────────────────────────────────────────────

async function runAnalysis() {
    const overlay = document.getElementById("loading-overlay");
    overlay.classList.remove("hidden");

    const params = getFormParams();

    try {
        const resp = await fetch(`${API_BASE}/api/analyze`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mode: currentMode, params }),
        });

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || "Analysis failed");
        }

        const data = await resp.json();
        renderResults(data);
    } catch (e) {
        alert("Analysis failed: " + e.message);
    } finally {
        overlay.classList.add("hidden");
    }
}

// ──────────────────────────────────────────────────────────────────────
// Results Rendering
// ──────────────────────────────────────────────────────────────────────

function renderResults(data) {
    updateDangerGauge(data.danger_score, data.danger_label, data.summary);
    updateDivergenceChart(data.telemetry, data.mode);
    updateErrorChart(data.telemetry);
    renderAnnotations(data.annotations);
    renderMetadata(data.metadata);
}

// ── Danger Gauge ─────────────────────────────────────────────────────

function updateDangerGauge(score, label, summary) {
    const gaugeValue = document.getElementById("gauge-value");
    const gaugeLabel = document.getElementById("gauge-label");
    const gaugeFill = document.getElementById("gauge-fill");
    const dangerSummary = document.getElementById("danger-summary");
    const dangerCard = document.getElementById("danger-card");

    // Determine color based on score
    let color;
    let className;
    if (score <= 20) {
        color = getComputedStyle(document.documentElement).getPropertyValue("--safe").trim();
        className = "danger-safe";
    } else if (score <= 40) {
        color = getComputedStyle(document.documentElement).getPropertyValue("--low").trim();
        className = "danger-low";
    } else if (score <= 60) {
        color = getComputedStyle(document.documentElement).getPropertyValue("--moderate").trim();
        className = "danger-moderate";
    } else if (score <= 80) {
        color = getComputedStyle(document.documentElement).getPropertyValue("--high").trim();
        className = "danger-high";
    } else {
        color = getComputedStyle(document.documentElement).getPropertyValue("--critical").trim();
        className = "danger-critical";
    }

    // Remove old danger classes
    dangerCard.classList.remove(
        "danger-safe", "danger-low", "danger-moderate", "danger-high", "danger-critical"
    );
    dangerCard.classList.add(className);

    // Animate the gauge fill
    const degrees = (score / 100) * 360;
    gaugeFill.style.background = `conic-gradient(
        ${color} 0deg,
        ${color} ${degrees}deg,
        rgba(30, 30, 50, 0.3) ${degrees}deg
    )`;

    // Animate the number counting up
    animateCounter(gaugeValue, score);
    gaugeLabel.textContent = label;
    gaugeLabel.style.color = color;
    gaugeValue.style.color = color;

    dangerSummary.textContent = summary;
}

function animateCounter(element, target) {
    const duration = 800;
    const start = parseInt(element.textContent) || 0;
    const diff = target - start;
    const startTime = performance.now();

    function step(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);

        // Ease out cubic
        const eased = 1 - Math.pow(1 - progress, 3);
        element.textContent = Math.round(start + diff * eased);

        if (progress < 1) {
            requestAnimationFrame(step);
        }
    }

    requestAnimationFrame(step);
}

// ── Divergence Chart ────────────────────────────────────────────────

function initCharts() {
    const divCtx = document.getElementById("chart-divergence").getContext("2d");
    const errCtx = document.getElementById("chart-error").getContext("2d");

    divergenceChart = new Chart(divCtx, {
        type: "line",
        data: {
            labels: [],
            datasets: [
                {
                    label: "Float (IEEE 754)",
                    data: [],
                    borderColor: "#ff5252",
                    backgroundColor: "rgba(255, 82, 82, 0.08)",
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    tension: 0.3,
                    fill: false,
                },
                {
                    label: "Ground Truth (mpmath)",
                    data: [],
                    borderColor: "#00e88f",
                    backgroundColor: "rgba(0, 232, 143, 0.08)",
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    tension: 0.3,
                    fill: false,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 600, easing: "easeOutCubic" },
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: {
                    position: "top",
                    labels: {
                        usePointStyle: true,
                        padding: 20,
                        font: { size: 12, weight: 600 },
                    },
                },
                tooltip: {
                    backgroundColor: "rgba(10, 10, 20, 0.9)",
                    borderColor: "rgba(255,255,255,0.1)",
                    borderWidth: 1,
                    padding: 12,
                    titleFont: { size: 13, weight: 700 },
                    bodyFont: { family: "'JetBrains Mono', monospace", size: 12 },
                    callbacks: {
                        label: function (ctx) {
                            return `${ctx.dataset.label}: ${ctx.parsed.y.toExponential(6)}`;
                        },
                    },
                },
            },
            scales: {
                x: {
                    ticks: { maxTicksLimit: 12, font: { size: 10 } },
                    grid: { color: "rgba(255,255,255,0.03)" },
                },
                y: {
                    type: "linear",
                    ticks: {
                        font: { size: 10 },
                        callback: (v) => v.toExponential(1),
                    },
                    grid: { color: "rgba(255,255,255,0.03)" },
                },
            },
        },
    });

    errorChart = new Chart(errCtx, {
        type: "bar",
        data: {
            labels: [],
            datasets: [
                {
                    label: "Bits Lost (/52)",
                    data: [],
                    backgroundColor: [],
                    borderColor: [],
                    borderWidth: 1,
                    borderRadius: 2,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 600, easing: "easeOutCubic" },
            plugins: {
                legend: {
                    position: "top",
                    labels: {
                        usePointStyle: true,
                        padding: 20,
                        font: { size: 12, weight: 600 },
                    },
                },
                tooltip: {
                    backgroundColor: "rgba(10, 10, 20, 0.9)",
                    borderColor: "rgba(255,255,255,0.1)",
                    borderWidth: 1,
                    padding: 12,
                    bodyFont: { family: "'JetBrains Mono', monospace", size: 12 },
                },
            },
            scales: {
                x: {
                    ticks: { maxTicksLimit: 12, font: { size: 10 } },
                    grid: { color: "rgba(255,255,255,0.03)" },
                },
                y: {
                    min: 0,
                    max: 52,
                    ticks: { font: { size: 10 }, stepSize: 10 },
                    grid: { color: "rgba(255,255,255,0.03)" },
                    title: {
                        display: true,
                        text: "Bits Lost",
                        font: { size: 11, weight: 600 },
                        color: "#9090aa",
                    },
                },
            },
        },
    });
}

function updateDivergenceChart(telemetry, mode) {
    const labels = telemetry.labels;
    let datasets;

    if (mode === "summation_error" && telemetry.kahan_values) {
        // For summation mode, show 3 lines: naive, kahan, truth
        datasets = [
            {
                label: "Naive Float Sum",
                data: telemetry.float_values,
                borderColor: "#ff5252",
                backgroundColor: "rgba(255, 82, 82, 0.08)",
                borderWidth: 2,
                pointRadius: 0,
                pointHoverRadius: 4,
                tension: 0.3,
                fill: false,
            },
            {
                label: "Kahan Compensated",
                data: telemetry.kahan_values,
                borderColor: "#00d4ff",
                backgroundColor: "rgba(0, 212, 255, 0.08)",
                borderWidth: 2,
                pointRadius: 0,
                pointHoverRadius: 4,
                tension: 0.3,
                fill: false,
            },
            {
                label: "Ground Truth (mpmath)",
                data: telemetry.ground_truth_values,
                borderColor: "#00e88f",
                backgroundColor: "rgba(0, 232, 143, 0.08)",
                borderWidth: 2,
                borderDash: [6, 3],
                pointRadius: 0,
                pointHoverRadius: 4,
                tension: 0.3,
                fill: false,
            },
        ];
    } else {
        datasets = [
            {
                label: "Float (IEEE 754)",
                data: telemetry.float_values,
                borderColor: "#ff5252",
                backgroundColor: "rgba(255, 82, 82, 0.08)",
                borderWidth: 2,
                pointRadius: 0,
                pointHoverRadius: 4,
                tension: 0.3,
                fill: false,
            },
            {
                label: "Ground Truth (mpmath)",
                data: telemetry.ground_truth_values,
                borderColor: "#00e88f",
                backgroundColor: "rgba(0, 232, 143, 0.08)",
                borderWidth: 2,
                pointRadius: 0,
                pointHoverRadius: 4,
                tension: 0.3,
                fill: false,
            },
        ];
    }

    divergenceChart.data.labels = labels;
    divergenceChart.data.datasets = datasets;
    divergenceChart.update("active");
}

function updateErrorChart(telemetry) {
    const labels = telemetry.labels;
    const bitsLost = telemetry.bits_lost;

    // Color each bar by severity
    const colors = bitsLost.map((b) => {
        if (b >= 40) return { bg: "rgba(255, 23, 68, 0.7)", border: "#ff1744" };
        if (b >= 20) return { bg: "rgba(255, 159, 67, 0.7)", border: "#ff9f43" };
        if (b >= 10) return { bg: "rgba(240, 224, 64, 0.7)", border: "#f0e040" };
        return { bg: "rgba(0, 232, 143, 0.5)", border: "#00e88f" };
    });

    errorChart.data.labels = labels;
    errorChart.data.datasets[0].data = bitsLost;
    errorChart.data.datasets[0].backgroundColor = colors.map((c) => c.bg);
    errorChart.data.datasets[0].borderColor = colors.map((c) => c.border);
    errorChart.update("active");
}

// ── Annotations ─────────────────────────────────────────────────────

function renderAnnotations(annotations) {
    const container = document.getElementById("annotations-list");

    if (!annotations || annotations.length === 0) {
        container.innerHTML =
            '<p class="placeholder-text">No critical annotations for this analysis.</p>';
        return;
    }

    container.innerHTML = annotations
        .slice(0, 20) // Cap at 20 to keep it readable
        .map(
            (ann, i) => `
        <div class="annotation-item ${ann.severity}" style="animation-delay: ${i * 50}ms">
            <span class="annotation-badge ${ann.severity}">${ann.severity}</span>
            <span class="annotation-message">${ann.message}</span>
        </div>
    `
        )
        .join("");
}

// ── Metadata ────────────────────────────────────────────────────────

function renderMetadata(metadata) {
    const container = document.getElementById("metadata-content");

    const items = Object.entries(metadata).map(
        ([key, value]) => `
        <div class="meta-item">
            <span class="meta-key">${key.replace(/_/g, " ")}</span>
            <span class="meta-value">${value}</span>
        </div>
    `
    );

    container.innerHTML = items.join("");
}
