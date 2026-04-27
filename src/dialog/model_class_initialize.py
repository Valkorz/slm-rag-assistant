import tkinter as tk
from tkinter import ttk
import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

os.chdir(project_root)

class ModelInitializeDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title(f"Initializing...")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self.transient(parent)
        self.grab_set()

        tk.Label(self, text=f"Please wait while the application is initializing...", pady=10).pack()
        self.progress = ttk.Progressbar(self, mode="indeterminate", length=300)
        self.progress.pack(padx=20, pady=10)
        self.status = tk.Label(self, text="Initializing model class...")
        self.status.pack(pady=5)

        self.progress.start()

    def set_status(self, message: str) -> None:
        self.status.config(text=message)

    def close(self, message: str = "Model loaded") -> None:
        self.progress.stop()
        self.status.config(text=message)
        self.after(300, self.destroy)

    def fail(self, message: str) -> None:
        self.progress.stop()
        self.status.config(text=message)
        self.after(2000, self.destroy)