#!/usr/bin/env python3
"""
TTube Installation Script - Enhanced Installer
Installs Python packages, FFmpeg, and creates desktop shortcuts
"""

import os
import sys
import shutil
import subprocess
import json
from pathlib import Path
from urllib.request import urlopen
import zipfile
import tempfile


class TTubeInstaller:
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.venv_dir = self.base_dir / ".venv"
        self.ffmpeg_dir = self.base_dir / "ffmpeg"
        self.is_windows = sys.platform == "win32"
        self.is_admin = self._is_admin() if self.is_windows else True
        
    def _is_admin(self):
        """Check if running with admin privileges on Windows"""
        try:
            import ctypes
            return ctypes.windll.shell.IsUserAnAdmin()
        except:
            return False
    
    def _run_cmd(self, cmd, shell=False):
        """Run a command and return success status"""
        try:
            print(f"\n[>] Executing: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
            result = subprocess.run(
                cmd,
                shell=shell,
                check=False,
                capture_output=False
            )
            return result.returncode == 0
        except Exception as e:
            print(f"[!] Error: {e}")
            return False
    
    def _print_header(self, text):
        """Print a formatted header"""
        print(f"\n{'='*60}")
        print(f"[*] {text}")
        print(f"{'='*60}")
    
    def check_python(self):
        """Verify Python version"""
        self._print_header("Checking Python Installation")
        version = sys.version_info
        print(f"[+] Python {version.major}.{version.minor}.{version.micro} detected")
        
        if version.major < 3 or (version.major == 3 and version.minor < 10):
            print("[!] ERROR: Python 3.10+ is required!")
            return False
        return True
    
    def create_venv(self):
        """Create virtual environment"""
        self._print_header("Creating Virtual Environment")
        
        if self.venv_dir.exists():
            print("[+] Virtual environment already exists, skipping creation")
            return True
        
        print(f"[>] Creating venv at {self.venv_dir}")
        if not self._run_cmd([sys.executable, "-m", "venv", str(self.venv_dir)]):
            print("[!] Failed to create virtual environment")
            return False
        
        print("[+] Virtual environment created successfully")
        return True
    
    def get_pip_executable(self):
        """Get the pip executable path"""
        if self.is_windows:
            return str(self.venv_dir / "Scripts" / "pip.exe")
        else:
            return str(self.venv_dir / "bin" / "pip")
    
    def get_python_executable(self):
        """Get the python executable path"""
        if self.is_windows:
            return str(self.venv_dir / "Scripts" / "python.exe")
        else:
            return str(self.venv_dir / "bin" / "python")
    
    def install_dependencies(self):
        """Install Python dependencies"""
        self._print_header("Installing Python Dependencies")
        
        pip_exe = self.get_pip_executable()
        
        # Upgrade pip, setuptools, wheel
        print("[>] Upgrading pip and build tools...")
        self._run_cmd([pip_exe, "install", "--upgrade", "pip", "setuptools", "wheel"])
        
        # Install requirements
        requirements_file = self.base_dir / "requirements.txt"
        if requirements_file.exists():
            print(f"[>] Installing from requirements.txt...")
            if not self._run_cmd([pip_exe, "install", "-r", str(requirements_file)]):
                print("[!] Failed to install some dependencies")
                return False
        
        # Install the package in editable mode
        print("[>] Installing TTube package...")
        if not self._run_cmd([pip_exe, "install", "-e", str(self.base_dir)]):
            print("[!] Failed to install TTube")
            return False
        
        print("[+] Dependencies installed successfully")
        return True
    
    def download_ffmpeg(self):
        """Download and install FFmpeg (Windows only)"""
        if not self.is_windows:
            print("[*] Skipping FFmpeg (not Windows)")
            return True
        
        self._print_header("Checking FFmpeg Installation")
        
        # Check if ffmpeg is in PATH
        if shutil.which("ffmpeg"):
            print("[+] FFmpeg already in PATH")
            return True
        
        # Check if local ffmpeg exists
        if (self.ffmpeg_dir / "bin" / "ffmpeg.exe").exists():
            print("[+] FFmpeg already installed locally")
            self._add_ffmpeg_to_path()
            return True
        
        print("[>] Downloading FFmpeg...")
        try:
            # Download ffmpeg-release-essentials.zip
            url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-release-essentials.zip"
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                tmp_path = tmp.name
                
            print(f"[>] Downloading from {url}")
            with urlopen(url, timeout=30) as response:
                with open(tmp_path, 'wb') as out_file:
                    out_file.write(response.read())
            
            print("[>] Extracting FFmpeg...")
            self.ffmpeg_dir.mkdir(exist_ok=True)
            
            with zipfile.ZipFile(tmp_path, 'r') as zip_ref:
                zip_ref.extractall(str(self.ffmpeg_dir))
            
            # Find and move bin directory
            for item in self.ffmpeg_dir.iterdir():
                if item.is_dir() and "ffmpeg" in item.name.lower():
                    bin_src = item / "bin"
                    if bin_src.exists():
                        bin_dst = self.ffmpeg_dir / "bin"
                        if bin_dst.exists():
                            shutil.rmtree(bin_dst)
                        shutil.move(str(bin_src), str(bin_dst))
                        break
            
            # Cleanup
            os.remove(tmp_path)
            
            self._add_ffmpeg_to_path()
            print("[+] FFmpeg installed successfully")
            return True
            
        except Exception as e:
            print(f"[!] Failed to download FFmpeg: {e}")
            print("[*] You can install FFmpeg manually from: https://ffmpeg.org/download.html")
            return False
    
    def _add_ffmpeg_to_path(self):
        """Add FFmpeg to environment PATH"""
        ffmpeg_bin = self.ffmpeg_dir / "bin"
        if ffmpeg_bin.exists():
            os.environ['PATH'] = f"{ffmpeg_bin}{os.pathsep}{os.environ.get('PATH', '')}"
    
    def create_desktop_shortcut(self):
        """Create desktop shortcut (Windows only)"""
        if not self.is_windows:
            return True
        
        self._print_header("Creating Desktop Shortcut")
        
        try:
            import winshell
            
            desktop = Path(winshell.desktop())
            shortcut_path = desktop / "TTube.lnk"
            
            python_exe = self.get_python_executable()
            ttube_script = self.base_dir / "ttube.py"
            
            # Create batch launcher
            launcher_bat = self.base_dir / "ttube_launcher.bat"
            bat_content = f"""@echo off
cd /d "{self.base_dir}"
"{python_exe}" -m ttube
pause
"""
            with open(launcher_bat, 'w') as f:
                f.write(bat_content)
            
            print(f"[+] Created launcher at {launcher_bat}")
            print("[+] Desktop shortcut setup - manual approach")
            print(f"[>] You can manually create a shortcut to: {launcher_bat}")
            
        except ImportError:
            # Fallback: create a batch launcher
            self._print_header("Creating Batch Launcher")
            
            launcher_bat = self.base_dir / "ttube_launcher.bat"
            python_exe = self.get_python_executable()
            
            bat_content = f"""@echo off
REM TTube Launcher
title TTube - Terminal Audio Streamer
cd /d "{self.base_dir}"
"{python_exe}" -m ttube
pause
"""
            with open(launcher_bat, 'w') as f:
                f.write(bat_content)
            
            print(f"[+] Created launcher: {launcher_bat}")
            print("[!] To create a desktop shortcut:")
            print(f"[>] Right-click and create shortcut, or pin {launcher_bat} to your desktop")
        
        return True
    
    def create_start_menu_shortcut(self):
        """Create Start Menu shortcut (Windows only)"""
        if not self.is_windows:
            return True
        
        try:
            from pathlib import Path
            import os
            
            # Get Start Menu directory
            start_menu = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            
            if not start_menu.exists():
                return False
            
            launcher_bat = self.base_dir / "ttube_launcher.bat"
            if launcher_bat.exists():
                shortcut_path = start_menu / "TTube.lnk"
                
                # Using PowerShell to create shortcut
                ps_cmd = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('{shortcut_path}')
$Shortcut.TargetPath = '{launcher_bat}'
$Shortcut.WorkingDirectory = '{self.base_dir}'
$Shortcut.Description = 'TTube - Terminal YouTube Audio Streamer'
$Shortcut.IconLocation = '{self.base_dir}\\ttube.ico,0'
$Shortcut.Save()
'''
                self._run_cmd(["powershell", "-Command", ps_cmd], shell=True)
                print(f"[+] Start Menu shortcut created")
                return True
        except Exception as e:
            print(f"[!] Could not create Start Menu shortcut: {e}")
        
        return False
    
    def display_completion_info(self):
        """Display completion information"""
        self._print_header("Installation Complete!")
        
        print("\n[+] TTube has been successfully installed!")
        print("\n[>] Next steps:")
        
        if self.is_windows:
            launcher = self.base_dir / "ttube_launcher.bat"
            if launcher.exists():
                print(f"    1. Run: {launcher}")
                print(f"    2. Or use command: python -m ttube")
            else:
                print(f"    1. Use command: python -m ttube")
        else:
            python_exe = self.get_python_executable()
            print(f"    1. Run: {python_exe} -m ttube")
            print(f"    2. Or use: source {self.venv_dir}/bin/activate && ttube")
        
        print("\n[>] Usage:")
        print("    - Type to search YouTube")
        print("    - Enter to play selected result")
        print("    - P/Space to pause/resume")
        print("    - S to stop playback")
        print("    - Q to quit")
        print("    - Arrow keys to navigate")
        print("\n" + "="*60 + "\n")
    
    def run_install(self):
        """Run the complete installation process"""
        print("\n" + "="*60)
        print("[*] TTube Enhanced Installer v0.1")
        print("[*] Terminal YouTube Audio Streamer")
        print("="*60)
        
        steps = [
            ("Checking Python", self.check_python),
            ("Creating Virtual Environment", self.create_venv),
            ("Installing Dependencies", self.install_dependencies),
            ("Installing FFmpeg", self.download_ffmpeg),
            ("Creating Shortcuts", self.create_desktop_shortcut),
            ("Creating Start Menu Entry", self.create_start_menu_shortcut),
        ]
        
        for name, step_func in steps:
            try:
                if not step_func():
                    print(f"\n[!] Installation halted during: {name}")
                    if name == "Installing FFmpeg":
                        print("[*] Continuing without system FFmpeg (will use fallback)")
                        continue
                    return False
            except Exception as e:
                print(f"\n[!] Unexpected error during {name}: {e}")
                if name == "Installing FFmpeg":
                    print("[*] Continuing without system FFmpeg (will use fallback)")
                    continue
                return False
        
        self.display_completion_info()
        return True


def main():
    """Main entry point"""
    installer = TTubeInstaller()
    
    try:
        success = installer.run_install()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n[!] Installation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[!] Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
