#!/usr/bin/env bash
# Career Intelligence Agent – launcher
# Usage: bash run.sh [port]

PORT=${1:-8501}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🧠 Career Intelligence Agent"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Copy .env.example → .env if not present
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
    echo "  ⚙  Created .env from .env.example"
    echo "     Add your API keys to .env for AI-powered insights"
    echo ""
fi

# Check core deps
python3 -c "import streamlit, chromadb, pypdf, sklearn" 2>/dev/null || {
    echo "  📦 Installing dependencies..."
    pip install -r "$SCRIPT_DIR/requirements.txt" --break-system-packages -q --no-cache-dir
}

echo "  🚀 Starting on http://localhost:$PORT"
echo ""

# Suppress noisy HF warnings at process level
export TOKENIZERS_PARALLELISM=false
export TRANSFORMERS_VERBOSITY=error
export HF_HUB_VERBOSITY=error

cd "$SCRIPT_DIR"
python3 -W ignore -m streamlit run app.py \
    --server.port "$PORT" \
    --server.headless true \
    --theme.base dark \
    --theme.primaryColor "#00d4ff" \
    --theme.backgroundColor "#0d0f14" \
    --theme.secondaryBackgroundColor "#141820" \
    --theme.textColor "#e8eaf0"
