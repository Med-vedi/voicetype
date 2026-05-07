# VoiceType 🎙

Voice dictation for macOS powered by OpenAI Whisper.

## Quick start

```bash
# 1. Install and run (one-time setup)
chmod +x install_and_run.sh
./install_and_run.sh

# 2. Or manually:
export OPENAI_API_KEY=sk-...
pip3 install openai pyaudio websockets pyperclip
python3 voicetype.py
```

The browser opens automatically at `http://localhost:8765`

## Usage

| Action | How |
|---|---|
| Start recording | Microphone button or `⌥ Space` |
| Stop recording | Same button / shortcut |
| Paste into app | Click "Paste" |
| AI text editing | Switch mode → "AI Edit" |
| System commands | "Commands" section |

## Voice commands

- "Open browser / Chrome / Firefox / Telegram / VSCode / Slack"
- "Volume up / Volume down / Mute"
- "Take screenshot"
- "Lock screen"

## Files

```
voicetype/
  voicetype.py        — Python server (WebSocket + HTTP)
  index.html          — UI
  install_and_run.sh  — Install and run script
  README.md           — This file
```

## Requirements

- macOS 12+
- Python 3.9+
- OpenAI API key (`sk-...`)
- Microphone access (System Preferences → Security → Microphone)
