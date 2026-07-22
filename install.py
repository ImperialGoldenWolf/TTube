import os
import sys
import shutil
import urllib.request
import zipfile
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
import win32com.client

class TTubeInstaller(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TTube Plus - Setup")
        self.geometry("500x350")
        self.resizable(False, False)
        self.configure(bg="#121212")

        # UI Styling
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure("TProgressbar", thickness=20, background="#7c3aed", troughcolor="#2a2a2a")

        # Header
        self.header = tk.Label(self, text="Install TTube Plus", font=("Inter", 20, "bold"), bg="#121212", fg="#ffffff")
        self.header.pack(pady=30)

        # Status
        self.status_var = tk.StringVar(value="Click Install to begin.")
        self.status_label = tk.Label(self, textvariable=self.status_var, font=("Inter", 10), bg="#121212", fg="#a0a0a0")
        self.status_label.pack(pady=10)

        # Progress
        self.progress = ttk.Progressbar(self, orient=tk.HORIZONTAL, length=400, mode='determinate', maximum=100)
        self.progress.pack(pady=10)

        # Install Button
        self.install_btn = tk.Button(self, text="Install", font=("Inter", 12, "bold"), bg="#7c3aed", fg="white", 
                                     activebackground="#6d28d9", activeforeground="white", borderwidth=0, padx=30, pady=10,
                                     command=self.start_install)
        self.install_btn.pack(pady=30)

        self.install_dir = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'TTube_Plus')
        self.src_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        # PyInstaller puts MEIPASS in temp, but we assume we are running from dist/
        if getattr(sys, 'frozen', False):
            self.base_dir = os.path.dirname(sys.executable)
        else:
            self.base_dir = os.path.dirname(os.path.abspath(__file__))

    def start_install(self):
        self.install_btn.config(state="disabled")
        self.progress['value'] = 0
        threading.Thread(target=self.install_process, daemon=True).start()

    def update_status(self, msg, progress):
        self.status_var.set(msg)
        self.progress['value'] = progress
        self.update_idletasks()

    def install_process(self):
        try:
            self.update_status("Creating installation directory...", 10)
            if not os.path.exists(self.install_dir):
                os.makedirs(self.install_dir)

            self.update_status("Copying application files...", 25)
            # Find the exe (since installer is in the same folder ideally)
            exe_src = os.path.join(self.base_dir, "TTube_Plus.exe")
            if not os.path.exists(exe_src):
                # Try finding it in dist/
                exe_src = os.path.join(self.base_dir, "dist", "TTube_Plus.exe")
            
            if os.path.exists(exe_src):
                shutil.copy2(exe_src, os.path.join(self.install_dir, "TTube_Plus.exe"))
            else:
                messagebox.showerror("Error", f"Could not find TTube_Plus.exe to install. Please place the installer next to it.")
                self.quit_app()
                return

            ico_src = os.path.join(self.base_dir, "ttube.ico")
            if os.path.exists(ico_src):
                shutil.copy2(ico_src, os.path.join(self.install_dir, "ttube.ico"))

            self.update_status("Downloading FFmpeg dependencies...", 40)
            ffmpeg_zip = os.path.join(self.install_dir, "ffmpeg.zip")
            if not os.path.exists(os.path.join(self.install_dir, "ffmpeg.exe")):
                url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
                urllib.request.urlretrieve(url, ffmpeg_zip)

                self.update_status("Extracting FFmpeg...", 70)
                with zipfile.ZipFile(ffmpeg_zip, 'r') as zip_ref:
                    for member in zip_ref.namelist():
                        if member.endswith('ffmpeg.exe') or member.endswith('ffprobe.exe'):
                            filename = os.path.basename(member)
                            source = zip_ref.open(member)
                            target = open(os.path.join(self.install_dir, filename), "wb")
                            with source, target:
                                shutil.copyfileobj(source, target)
                os.remove(ffmpeg_zip)

            self.update_status("Creating Start Menu and Desktop Shortcuts...", 90)
            self.create_shortcuts()

            self.update_status("Installation Complete!", 100)
            self.install_btn.config(text="Launch TTube Plus", state="normal", command=self.launch_app)
            messagebox.showinfo("Success", "TTube Plus has been successfully installed!")

        except Exception as e:
            messagebox.showerror("Installation Error", str(e))
            self.quit_app()

    def create_shortcuts(self):
        try:
            shell = win32com.client.Dispatch("WScript.Shell")
            
            # Desktop
            desktop = shell.SpecialFolders("Desktop")
            shortcut = shell.CreateShortCut(os.path.join(desktop, "TTube Plus.lnk"))
            shortcut.Targetpath = os.path.join(self.install_dir, "TTube_Plus.exe")
            shortcut.WorkingDirectory = self.install_dir
            shortcut.IconLocation = os.path.join(self.install_dir, "ttube.ico")
            shortcut.save()

            # Start Menu
            start_menu = shell.SpecialFolders("Programs")
            ttube_sm = os.path.join(start_menu, "TTube Plus")
            if not os.path.exists(ttube_sm):
                os.makedirs(ttube_sm)
            shortcut_sm = shell.CreateShortCut(os.path.join(ttube_sm, "TTube Plus.lnk"))
            shortcut_sm.Targetpath = os.path.join(self.install_dir, "TTube_Plus.exe")
            shortcut_sm.WorkingDirectory = self.install_dir
            shortcut_sm.IconLocation = os.path.join(self.install_dir, "ttube.ico")
            shortcut_sm.save()
        except Exception as e:
            print("Shortcut error:", e)

    def launch_app(self):
        subprocess.Popen([os.path.join(self.install_dir, "TTube_Plus.exe")], cwd=self.install_dir)
        self.destroy()

    def quit_app(self):
        self.destroy()

if __name__ == "__main__":
    app = TTubeInstaller()
    app.mainloop()
