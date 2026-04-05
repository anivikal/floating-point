#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
# Floating Point Error Analyzer — One-Command Launcher
# ═══════════════════════════════════════════════════════════════════════
# Usage: ./start.sh
#
# This script starts both the backend (FastAPI) and frontend (static)
# servers, then opens the dashboard in your default browser.
# Press Ctrl+C to stop everything.
# ═══════════════════════════════════════════════════════════════════════

set -e

# ── Colors ────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
RESET='\033[0m'

BACKEND_PORT=8000
FRONTEND_PORT=3000
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Cleanup on exit ──────────────────────────────────────────────────
cleanup() {
    echo ""
    echo -e "${YELLOW}⏹  Shutting down servers...${RESET}"
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    wait $BACKEND_PID 2>/dev/null || true
    wait $FRONTEND_PID 2>/dev/null || true
    echo -e "${GREEN}✓  All servers stopped.${RESET}"
    exit 0
}
trap cleanup SIGINT SIGTERM

# ── Banner ────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}${BOLD}╔═══════════════════════════════════════════════════════════╗${RESET}"
echo -e "${CYAN}${BOLD}║       ⚡ Floating Point Error Analyzer                   ║${RESET}"
echo -e "${CYAN}${BOLD}║       IEEE 754 Precision Loss Detector & Visualizer      ║${RESET}"
echo -e "${CYAN}${BOLD}╚═══════════════════════════════════════════════════════════╝${RESET}"
echo ""

# ── Check Python ─────────────────────────────────────────────────────
echo -e "${BOLD}[1/5]${RESET} Checking Python..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗  Python 3 is not installed. Please install Python 3.10+.${RESET}"
    exit 1
fi
PYTHON_VERSION=$(python3 --version 2>&1)
echo -e "${GREEN}  ✓  $PYTHON_VERSION${RESET}"

# ── Install Python dependencies ──────────────────────────────────────
echo -e "${BOLD}[2/5]${RESET} Installing Python dependencies..."
pip3 install -q -r "$PROJECT_DIR/backend/requirements.txt" 2>/dev/null || {
    echo -e "${YELLOW}  ⚠  pip install had warnings (non-fatal)${RESET}"
}
echo -e "${GREEN}  ✓  Dependencies ready (fastapi, uvicorn, mpmath)${RESET}"

# ── Check Node.js (for npx serve) ───────────────────────────────────
echo -e "${BOLD}[3/5]${RESET} Checking Node.js..."
if ! command -v npx &> /dev/null; then
    echo -e "${YELLOW}  ⚠  npx not found. Will use Python's http.server for frontend.${RESET}"
    USE_PYTHON_SERVER=true
else
    NODE_VERSION=$(node --version 2>&1)
    echo -e "${GREEN}  ✓  Node.js $NODE_VERSION${RESET}"
    USE_PYTHON_SERVER=false
fi

# ── Start Backend ────────────────────────────────────────────────────
echo -e "${BOLD}[4/5]${RESET} Starting backend on port ${BACKEND_PORT}..."

# Kill any existing process on the backend port
lsof -ti:$BACKEND_PORT | xargs kill -9 2>/dev/null || true

python3 -m uvicorn main:app \
    --host 0.0.0.0 \
    --port $BACKEND_PORT \
    --app-dir "$PROJECT_DIR/backend" \
    --log-level warning &
BACKEND_PID=$!

# Wait for backend to be ready
echo -n "  Waiting for backend"
for i in $(seq 1 30); do
    if curl -s http://localhost:$BACKEND_PORT/api/health > /dev/null 2>&1; then
        echo ""
        echo -e "${GREEN}  ✓  Backend running → http://localhost:${BACKEND_PORT}${RESET}"
        echo -e "${GREEN}     API Docs → http://localhost:${BACKEND_PORT}/docs${RESET}"
        break
    fi
    echo -n "."
    sleep 0.5
done

# ── Start Frontend ───────────────────────────────────────────────────
echo -e "${BOLD}[5/5]${RESET} Starting frontend on port ${FRONTEND_PORT}..."

# Kill any existing process on the frontend port
lsof -ti:$FRONTEND_PORT | xargs kill -9 2>/dev/null || true

if [ "$USE_PYTHON_SERVER" = true ]; then
    python3 -m http.server $FRONTEND_PORT \
        --directory "$PROJECT_DIR/frontend" \
        --bind 0.0.0.0 > /dev/null 2>&1 &
else
    npx -y serve "$PROJECT_DIR/frontend" -l $FRONTEND_PORT -s > /dev/null 2>&1 &
fi
FRONTEND_PID=$!
sleep 1
echo -e "${GREEN}  ✓  Frontend running → http://localhost:${FRONTEND_PORT}${RESET}"

# ── Open Browser ─────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}${BOLD}══════════════════════════════════════════════════════════════${RESET}"
echo -e "${CYAN}${BOLD}  🚀 Dashboard ready: ${GREEN}http://localhost:${FRONTEND_PORT}${RESET}"
echo -e "${CYAN}${BOLD}══════════════════════════════════════════════════════════════${RESET}"
echo ""
echo -e "${YELLOW}  Press Ctrl+C to stop all servers${RESET}"
echo ""

# Try to open browser (macOS, Linux, WSL)
if command -v open &> /dev/null; then
    open "http://localhost:$FRONTEND_PORT"
elif command -v xdg-open &> /dev/null; then
    xdg-open "http://localhost:$FRONTEND_PORT"
elif command -v wslview &> /dev/null; then
    wslview "http://localhost:$FRONTEND_PORT"
fi

# ── Wait for termination ─────────────────────────────────────────────
wait
