#!/usr/bin/env python3
"""
TTube Quick Start Script
Run this to verify installation and get started
"""

import subprocess
import sys
import os
from pathlib import Path


def run_command(cmd, shell=False):
    """Run a command and return success status"""
    try:
        result = subprocess.run(cmd, shell=shell, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


def main():
    """Check system and run TTube"""
    base_dir = Path(__file__).parent
    venv_dir = base_dir / ".venv"
    
    print("\n" + "="*60)
    print("[*] TTube Quick Start")
    print("="*60 + "\n")
    
    # Check Python
    print("[>] Checking Python...")
    version_ok, stdout, _ = run_command([sys.executable, "--version"])
    if version_ok:
        print(f"[+] {stdout.strip()}")
    else:
        print("[!] Python version check failed")
        return 1
    
    # Check venv
    print("[>] Checking virtual environment...")
    if not venv_dir.exists():
        print("[!] Virtual environment not found!")
        print("[>] Run: python install_app.py")
        return 1
    print("[+] Virtual environment found")
    
    # Check dependencies
    print("[>] Checking dependencies...")
    is_windows = sys.platform == "win32"
    pip_exe = venv_dir / ("Scripts\\pip.exe" if is_windows else "bin/pip")
    
    if pip_exe.exists():
        ok, stdout, _ = run_command([str(pip_exe), "list"])
        if ok:
            required = ["yt-dlp", "sounddevice", "imageio-ffmpeg"]
            packages = [line.lower() for line in stdout.split('\n')]
            missing = [p for p in required if not any(p.lower() in pkg for pkg in packages)]
            
            if missing:
                print(f"[!] Missing packages: {', '.join(missing)}")
                print("[>] Run: pip install -r requirements.txt")
                return 1
            print("[+] All dependencies installed")
        else:
            print("[!] Could not verify dependencies")
    
    # Check FFmpeg
    print("[>] Checking FFmpeg...")
    ok, stdout, _ = run_command("ffmpeg -version", shell=True)
    if ok:
        print("[+] FFmpeg found in PATH")
    else:
        ffmpeg_local = base_dir / "ffmpeg" / "bin" / ("ffmpeg.exe" if is_windows else "ffmpeg")
        if ffmpeg_local.exists():
            print("[+] Local FFmpeg installation found")
        else:
            print("[*] FFmpeg not found (will use Python fallback)")
    
    print("\n" + "="*60)
    print("[+] System check passed!")
    print("[*] Starting TTube...")
    print("="*60 + "\n")
    
    # Run TTube
    python_exe = venv_dir / ("Scripts\\python.exe" if is_windows else "bin/python")
    result = subprocess.run([str(python_exe), "-m", "ttube"], cwd=base_dir)
    
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
