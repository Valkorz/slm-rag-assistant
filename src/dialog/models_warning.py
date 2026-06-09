import tkinter as tk
from tkinter import filedialog
import webbrowser

HUGGINGFACE_MODELS_URL = "https://huggingface.co/models?pipeline_tag=text-generation&library=gguf&sort=trending"

_INSTRUCTIONS = """\
Language models are large files that run entirely on your computer.
Follow the steps below to download one and point the app to it.

STEP 1 — Open HuggingFace
  Click "Open HuggingFace" below. HuggingFace is a free website
  that hosts thousands of open-source language models.

STEP 2 — Pick a model
  Search for one of these beginner-friendly options:
    • Llama-3.1-8B-Instruct
    • gemma-4-E2B-it  (lighter, good for low-end hardware)
    • DeepSeek-R1-Distill-Qwen-1.5B  (very fast, less accurate)

STEP 3 — Go to "Files and versions"
  On the model page, click the "Files and versions" tab.

STEP 4 — Download the right file  ← IMPORTANT
  You must download a file that:
    ✓  Ends in  .gguf
    ✓  Contains  Q4_K  or  Q5_K  in the filename
       (e.g.  model-Q4_K_M.gguf)

  These are "quantized" versions — compressed to run on normal
  consumer hardware without a data-center GPU.

  ✗  Do NOT download  .bin,  .safetensors,  or any other format.
  ✗  Avoid  Q8  or  fp16  files — they require much more RAM/VRAM.

STEP 5 — Save to a dedicated folder
  Create a folder such as  C:\\Models  and place the .gguf file
  inside it. You can store multiple models in the same folder.

STEP 6 — Select the folder
  Click "Select Folder" below and navigate to where you saved
  the .gguf file. The app will detect it automatically.\
"""


class ModelsWarningDialog(tk.Toplevel):
    def __init__(self, parent, on_folder_selected=None):
        super().__init__(parent)
        self._on_folder_selected = on_folder_selected
        self.title("No models found")
        self.resizable(False, False)
        self.transient(parent)
        self._build_warning_view() 
        self.update_idletasks()
        self.lift()
        self.focus_force()
        try:
            self.grab_set()
        except tk.TclError:
            pass 


    def _clear(self):
        for widget in self.winfo_children():
            widget.destroy()

    def _build_warning_view(self):
        tk.Label(
            self,
            text="No models found.\nWould you like to see how to install one?",
            pady=14,
            padx=24,
            justify="center",
        ).pack()

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=(0, 14))

        tk.Button(btn_frame, text="YES", width=10, command=self._on_yes).pack(side="left", padx=6)
        tk.Button(btn_frame, text="NO",  width=10, command=self.destroy).pack(side="left", padx=6)


    def _on_yes(self):
        self._clear()
        self.resizable(True, True)
        self.title("How to install a language model")
        self._build_instructions_view()

    def _build_instructions_view(self):
        tk.Label(
            self,
            text="How to install a language model",
            font=("Segoe UI", 11, "bold"),
            anchor="w",
            padx=16,
            pady=8,
        ).pack(fill="x")

        tk.Frame(self, height=1, bg="#cccccc").pack(fill="x", padx=16)

        text_frame = tk.Frame(self)
        text_frame.pack(fill="both", expand=True, padx=16, pady=(8, 4))

        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")

        text_box = tk.Text(
            text_frame,
            wrap="word",
            width=62,
            height=20,
            yscrollcommand=scrollbar.set,
            relief="flat",
            bg="#f7f7f7",
            padx=12,
            pady=10,
            font=("Consolas", 9),
            state="normal",
            cursor="arrow",
        )
        text_box.insert("1.0", _INSTRUCTIONS)
        text_box.config(state="disabled")
        text_box.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=text_box.yview)

        tk.Frame(self, height=1, bg="#cccccc").pack(fill="x", padx=16, pady=(4, 0))

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=10)

        tk.Button(
            btn_frame,
            text="Open HuggingFace",
            width=20,
            command=lambda: webbrowser.open(HUGGINGFACE_MODELS_URL),
        ).pack(side="left", padx=6)

        tk.Button(
            btn_frame,
            text="Select Folder",
            width=16,
            command=self._select_folder,
        ).pack(side="left", padx=6)

        tk.Button(
            btn_frame,
            text="Cancel",
            width=10,
            command=self.destroy,
        ).pack(side="left", padx=6)

        self.update_idletasks()
        self.geometry("")


    def _select_folder(self):
        selected = filedialog.askdirectory(
            parent=self,
            title="Select the folder containing your .gguf model files",
        )
        if selected:
            if self._on_folder_selected:
                self._on_folder_selected(selected)
            self.destroy()
