#!/usr/bin/env python3
"""
F1 Telemetry Launcher
=====================
Double-click this file (or run `python launch.py`) to start the F1 Telemetry
system.  It will:

  1. Create a virtual environment (if one doesn't exist yet).
  2. Install / update all required packages automatically.
  3. Start the web server and open your browser.

No command-line knowledge required!
"""

import os
import sys
import subprocess
import webbrowser
import time
import platform
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
REQUIREMENTS = ROOT / "f1_telemetry" / "backend" / "requirements.txt"
HOST = "0.0.0.0"
PORT = 8000


def _python():
    """Return the path to the venv Python interpreter."""
    if platform.system() == "Windows":
        return str(VENV_DIR / "Scripts" / "python.exe")
    return str(VENV_DIR / "bin" / "python")


def _pip():
    """Return the path to the venv pip."""
    if platform.system() == "Windows":
        return str(VENV_DIR / "Scripts" / "pip.exe")
    return str(VENV_DIR / "bin" / "pip")


def ensure_venv():
    """Create a virtual environment if it doesn't already exist."""
    if VENV_DIR.exists() and Path(_python()).exists():
        return
    print("\n>>> Creating virtual environment ...")
    subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])
    print("    Virtual environment created at", VENV_DIR)


def install_deps():
    """Install / update dependencies from requirements.txt."""
    print("\n>>> Installing dependencies (this may take a moment on first run) ...")
    subprocess.check_call(
        [_pip(), "install", "--upgrade", "pip"],
        stdout=subprocess.DEVNULL,
    )
    subprocess.check_call(
        [_pip(), "install", "-r", str(REQUIREMENTS)],
    )
    print("    All dependencies installed.")


def start_server():
    """Start the uvicorn server and open the browser."""
    url = f"http://localhost:{PORT}/dashboard"
    print(f"\n>>> Starting F1 Telemetry server on port {PORT} ...")
    print(f"    Dashboard will open at: {url}")
    print("    Press Ctrl+C to stop.\n")

    # Open the browser after a short delay
    def _open_browser():
        time.sleep(2)
        webbrowser.open(url)

    import threading
    threading.Thread(target=_open_browser, daemon=True).start()

    subprocess.call(
        [
            _python(), "-m", "uvicorn",
            "f1_telemetry.backend.app.main:app",
            "--host", HOST,
            "--port", str(PORT),
        ],
        cwd=str(ROOT),
    )


def main():
    print("=" * 56)
    print("        F1 TELEMETRY  —  Multi-Game Dashboard")
    print("        Supports F1 2019 · F1 2020 · F1 2021")
    print("=" * 56)

    try:
        ensure_venv()
        install_deps()
        start_server()
    except KeyboardInterrupt:
        print("\n\nServer stopped. Goodbye!")
    except Exception as exc:
        print(f"\n[ERROR] {exc}")
        input("\nPress Enter to close ...")
        sys.exit(1)


if __name__ == "__main__":
    main()
