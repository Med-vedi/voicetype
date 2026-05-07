#!/bin/bash
# VoiceType — install dependencies and run on macOS
set -e

echo "────────────────────────────────────────────"
echo "  VoiceType — installing dependencies"
echo "────────────────────────────────────────────"

# Check for Python
if ! command -v python3 &> /dev/null; then
  echo "❌ Python 3 not found. Install from https://python.org"
  exit 1
fi

echo "✓ Python: $(python3 --version)"

# Upgrade pip first so it can resolve modern wheels
echo ""
echo "Upgrading pip..."
python3 -m pip install --quiet --upgrade pip

# Install PyTorch from the official CPU index (avoids resolver issues)
echo "Installing PyTorch (CPU)..."
pip3 install --quiet torch --index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies
echo "Installing remaining dependencies..."
pip3 install --quiet --upgrade openai-whisper pyaudio websockets pyperclip

echo "✓ Dependencies installed"
echo ""


echo "────────────────────────────────────────────"
echo "  Starting VoiceType..."
echo "────────────────────────────────────────────"

# Launch the app
python3 "$(dirname "$0")/voicetype.py"
