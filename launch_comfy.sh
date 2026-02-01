#!/bin/bash
# Helper script to launch ComfyUI with logging enabled
# Usage: ./launch_comfy.sh [additional args]

# Load .env if present
if [ -f "$(dirname "$0")/.env" ]; then
    export $(grep -v '^#' "$(dirname "$0")/.env" | xargs)
fi

# Check COMFYUI_PATH is set
if [ -z "$COMFYUI_PATH" ]; then
    echo "Error: COMFYUI_PATH not set"
    echo "Either set it in .env or export COMFYUI_PATH=/path/to/ComfyUI"
    exit 1
fi

# Default log location
COMFYUI_LOG="${COMFYUI_LOG:-$COMFYUI_PATH/comfyui.log}"

echo "Starting ComfyUI..."
echo "  Path: $COMFYUI_PATH"
echo "  Log:  $COMFYUI_LOG"
echo ""

cd "$COMFYUI_PATH"

# Check for venv/conda
if [ -f "venv/bin/python" ]; then
    PYTHON="venv/bin/python"
elif [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="python"
fi

echo "Using Python: $PYTHON"
echo "Additional args: $@"
echo ""
echo "--- ComfyUI Output ---"

# Run with tee to capture output
$PYTHON main.py "$@" 2>&1 | tee "$COMFYUI_LOG"
