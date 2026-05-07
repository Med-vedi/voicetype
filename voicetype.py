#!/usr/bin/env python3
"""
VoiceType — voice dictation for macOS using OpenAI Whisper
Dependencies: pip install openai pyaudio websockets pyperclip
"""

import asyncio
import json
import os
import sys
import wave
import tempfile
import threading
import subprocess
import webbrowser
import http.server
import socketserver
from pathlib import Path
from datetime import datetime

try:
    import pyaudio
    import websockets
    import openai
    import pyperclip
except ImportError as e:
    print(f"Error: missing dependency — {e}")
    print("Install with: pip install openai pyaudio websockets pyperclip")
    sys.exit(1)

# ─── Config ───────────────────────────────────────────────────────────────────

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
PORT_HTTP      = 8765
PORT_WS        = 8766
SAMPLE_RATE    = 16000
CHANNELS       = 1
CHUNK          = 1024
FORMAT         = pyaudio.paInt16
RECORD_SECONDS = 30          # maximum recording length
HTML_FILE      = Path(__file__).parent / "index.html"

# Session history (max 50 entries)
history: list[dict] = []

# ─── Audio ────────────────────────────────────────────────────────────────────

class AudioRecorder:
    def __init__(self):
        self.pa      = pyaudio.PyAudio()
        self.stream  = None
        self.frames  = []
        self.active  = False

    def start(self):
        self.frames = []
        self.active = True
        self.stream = self.pa.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK,
        )
        threading.Thread(target=self._record, daemon=True).start()

    def _record(self):
        max_chunks = int(SAMPLE_RATE / CHUNK * RECORD_SECONDS)
        count = 0
        while self.active and count < max_chunks:
            data = self.stream.read(CHUNK, exception_on_overflow=False)
            self.frames.append(data)
            count += 1

    def stop_and_save(self) -> str:
        """Stops recording and returns the path to the WAV file."""
        self.active = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        with wave.open(tmp.name, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(self.pa.get_sample_size(FORMAT))
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b"".join(self.frames))
        return tmp.name

    def cleanup(self):
        self.pa.terminate()


recorder = AudioRecorder()

# ─── Whisper ──────────────────────────────────────────────────────────────────

async def transcribe(wav_path: str, language: str = "auto") -> str:
    """Sends audio to Whisper and returns the transcribed text."""
    if not OPENAI_API_KEY:
        return "❌ OPENAI_API_KEY is not set. Enter your key in Settings."

    client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
    kwargs = {"model": "whisper-1", "response_format": "text"}
    if language != "auto":
        kwargs["language"] = language

    with open(wav_path, "rb") as f:
        result = await client.audio.transcriptions.create(file=f, **kwargs)

    os.unlink(wav_path)
    return str(result).strip()


async def ai_edit(text: str, instruction: str) -> str:
    """Edits text via GPT-4o based on a voice instruction."""
    if not OPENAI_API_KEY:
        return text

    client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a text editor. Apply the user's instruction to the text. "
                    "Reply with ONLY the edited text, no explanations."
                ),
            },
            {"role": "user", "content": f"Text:\n{text}\n\nInstruction: {instruction}"},
        ],
        max_tokens=1000,
    )
    return resp.choices[0].message.content.strip()

# ─── macOS system commands ────────────────────────────────────────────────────

COMMAND_MAP = {
    # browser
    "open browser":    lambda: subprocess.Popen(["open", "-a", "Safari"]),
    "open chrome":     lambda: subprocess.Popen(["open", "-a", "Google Chrome"]),
    "open firefox":    lambda: subprocess.Popen(["open", "-a", "Firefox"]),
    # apps
    "open terminal":   lambda: subprocess.Popen(["open", "-a", "Terminal"]),
    "open finder":     lambda: subprocess.Popen(["open", "-a", "Finder"]),
    "open notes":      lambda: subprocess.Popen(["open", "-a", "Notes"]),
    "open telegram":   lambda: subprocess.Popen(["open", "-a", "Telegram"]),
    "open vscode":     lambda: subprocess.Popen(["open", "-a", "Visual Studio Code"]),
    "open mail":       lambda: subprocess.Popen(["open", "-a", "Mail"]),
    "open calendar":   lambda: subprocess.Popen(["open", "-a", "Calendar"]),
    "open slack":      lambda: subprocess.Popen(["open", "-a", "Slack"]),
    # system
    "volume up":       lambda: subprocess.run(["osascript", "-e", "set volume output volume (output volume of (get volume settings) + 10)"]),
    "volume down":     lambda: subprocess.run(["osascript", "-e", "set volume output volume (output volume of (get volume settings) - 10)"]),
    "mute":            lambda: subprocess.run(["osascript", "-e", "set volume with output muted"]),
    "lock screen":     lambda: subprocess.run(["pmset", "displaysleepnow"]),
    "take screenshot": lambda: subprocess.Popen(["screencapture", "-i", f"{Path.home()}/Desktop/screenshot_{datetime.now():%H%M%S}.png"]),
}


def handle_command(text: str) -> dict:
    """Finds and executes a voice command. Returns the result."""
    lower = text.lower().strip()
    for trigger, action in COMMAND_MAP.items():
        if trigger in lower:
            try:
                action()
                return {"ok": True, "message": f"✓ Executed: «{trigger}»"}
            except Exception as e:
                return {"ok": False, "message": f"Error: {e}"}
    return {"ok": False, "message": "Command not recognized"}

# ─── WebSocket server ─────────────────────────────────────────────────────────

async def ws_handler(ws):
    """Handles messages from the frontend."""
    global recorder, OPENAI_API_KEY
    async for raw in ws:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue

        kind = msg.get("type")

        # ── set API key ──
        if kind == "set_key":
            OPENAI_API_KEY = msg.get("key", "")
            await ws.send(json.dumps({"type": "key_saved"}))

        # ── start recording ──
        elif kind == "start":
            recorder.start()
            await ws.send(json.dumps({"type": "recording_started"}))

        # ── stop and transcribe ──
        elif kind == "stop":
            wav = recorder.stop_and_save()
            await ws.send(json.dumps({"type": "transcribing"}))
            lang = msg.get("language", "auto")
            text = await transcribe(wav, lang)

            entry = {
                "id":   len(history),
                "time": datetime.now().strftime("%H:%M"),
                "text": text,
            }
            history.insert(0, entry)
            if len(history) > 50:
                history.pop()

            await ws.send(json.dumps({"type": "transcript", "text": text, "entry": entry}))

        # ── paste text into active app ──
        elif kind == "paste":
            text = msg.get("text", "")
            pyperclip.copy(text)
            subprocess.run([
                "osascript", "-e",
                'tell application "System Events" to keystroke "v" using command down'
            ])
            await ws.send(json.dumps({"type": "pasted"}))

        # ── AI edit ──
        elif kind == "edit":
            original    = msg.get("text", "")
            instruction = msg.get("instruction", "")
            edited = await ai_edit(original, instruction)
            await ws.send(json.dumps({"type": "edited", "text": edited}))

        # ── run command ──
        elif kind == "command":
            text   = msg.get("text", "")
            result = handle_command(text)
            await ws.send(json.dumps({"type": "command_result", **result}))

        # ── get history ──
        elif kind == "get_history":
            await ws.send(json.dumps({"type": "history", "items": history}))

        # ── clear history ──
        elif kind == "clear_history":
            history.clear()
            await ws.send(json.dumps({"type": "history_cleared"}))


async def start_ws():
    print(f"🎙  WebSocket running on ws://localhost:{PORT_WS}")
    async with websockets.serve(ws_handler, "localhost", PORT_WS):
        await asyncio.Future()

# ─── HTTP server for the frontend ─────────────────────────────────────────────

class SilentHTTPHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def translate_path(self, path):
        # always serve index.html from the script directory
        return str(HTML_FILE)


def start_http():
    with socketserver.TCPServer(("localhost", PORT_HTTP), SilentHTTPHandler) as srv:
        print(f"🌐  Interface:  http://localhost:{PORT_HTTP}")
        srv.serve_forever()

# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("─" * 46)
    print("  VoiceType — voice dictation for macOS")
    print("─" * 46)

    if not OPENAI_API_KEY:
        print("⚠  OPENAI_API_KEY is not set.")
        print("   Set it in the interface or via an environment variable.")

    # Start HTTP in a background thread
    threading.Thread(target=start_http, daemon=True).start()

    # Open browser after one second
    def open_browser():
        import time; time.sleep(1)
        webbrowser.open(f"http://localhost:{PORT_HTTP}")
    threading.Thread(target=open_browser, daemon=True).start()

    # Start WebSocket (main thread)
    try:
        asyncio.run(start_ws())
    except KeyboardInterrupt:
        print("\n👋  VoiceType stopped.")
        recorder.cleanup()
