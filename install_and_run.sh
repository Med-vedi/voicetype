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

# Install dependencies
echo ""
echo "Installing dependencies..."
pip3 install --quiet --upgrade openai-whisper pyaudio websockets pyperclip

echo "✓ Dependencies installed"
echo ""

# Check API key
if [ -z "$OPENAI_API_KEY" ]; then
  echo "⚠  OPENAI_API_KEY is not set."
  echo "   Option 1: export OPENAI_API_KEY=sk-..."
  echo "   Option 2: enter the key in the interface (Settings)"
  echo ""
fi

echo "────────────────────────────────────────────"
echo "  Starting VoiceType..."
echo "────────────────────────────────────────────"

# Launch the app
python3 "$(dirname "$0")/voicetype.py"
