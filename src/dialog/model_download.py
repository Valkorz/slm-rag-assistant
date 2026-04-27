import tkinter as tk
from tkinter import ttk
import threading
import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

os.chdir(project_root)

from src.model_manager import ModelManager

class ModelDownloadDialog(tk.Toplevel):
    def __init__(self, parent, manager: ModelManager, model_name: str):
        super().__init__(parent)
        self.title(f"Downloading {model_name}")
        self.resizable(False, False)
        self.manager = manager
        self.model_name = model_name

        tk.Label(self, text=f"Downloading {model_name}...", pady=10).pack()
        self.progress = ttk.Progressbar(self, mode="indeterminate", length=300)
        self.progress.pack(padx=20, pady=10)
        self.status = tk.Label(self, text="Connecting to HuggingFace...")
        self.status.pack(pady=5)

        self.progress.start()
        threading.Thread(target=self._download, daemon=True).start()

    def _download(self):
        try:
            path = self.manager.download(self.model_name)
            self.after(0, lambda: self._done(f"Saved to {path}"))
        except Exception as e:
            self.after(0, lambda: self._done(f"Error: {e}"))

    def _done(self, message: str):
        self.progress.stop()
        self.status.config(text=message)
        self.after(2000, self.destroy)