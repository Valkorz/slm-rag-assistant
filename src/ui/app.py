import tkinter as tk
import customtkinter as ctk
import asyncio
import json
import sys
import threading
from pathlib import Path
from tkinter import filedialog
from PIL import Image

from src import theme
from src.config_loader import get_config, save_config
from src.assistant_request_socket import AssistantRequestSocket
from src.pdf_files import normalize_pdf_file, collect_ingest_files, load_pdfs_from_folder
from src.dialog.model_class_initialize import ModelInitializeDialog
from src.dialog.models_warning import ModelsWarningDialog
from src.ui.slide_panel import SlidePanel

from src.utils.logger import logger

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

DATA_FOLDER = "./data/"
PDF_ICON_PATH = "images/pdf.png"
TCP_PORT = 8008
QUESTION_PLACEHOLDER = "Write your question here..."

# Generation / retrieval defaults 
DEFAULT_TEMPERATURE = 0.1          # reasoning model answer temperature
DEFAULT_QUERY_COUNT = 5            # number of search queries generated per question
DEFAULT_QUERY_TEMPERATURE = 0.1    # temperature for the query-generation step
DEFAULT_SCORE_MINIMUM = 0.6        # minimum retrieval score to keep a chunk
DEFAULT_CHUNK_DENSITY = 0.55       # is_valid_chunk: min information density
DEFAULT_CHUNK_DIVERSITY = 0.40     # is_valid_chunk: min lexical diversity
DEFAULT_CHUNK_AVG_SENT = 5.0       # is_valid_chunk: min average sentence length

IS_FROZEN = getattr(sys, "frozen", False)         # True in a PyInstaller release build
LOG_LEVELS = ["DEBUG", "INFO", "WARN", "ERROR"]   # order of the log-filter buttons


class AssistantApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Runtime state
        self.files: list[dict] = []
        self.downloaded_models = ["None"]
        self.model = None
        self.initialize_dialog = None
        self._init_dialog_shown = False  # init dialog is shown only on the first Send
        self.selected_models_folder = ""
        self._inner_scrollables = []      # regions that handle their own mouse wheel
        self._log_selected_index = -1     # highlighted log message (-1 = none)
        self._selected_log_panel = None

        self._build_window()
        self._start_tcp_socket()
        self._build_layout()

        self._load_initial_files()
        self._apply_saved_config()

        logger.debug("Application initialized.")

        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    # ------------------------------------------------------------------ #
    # Window + scrollable container
    # ------------------------------------------------------------------ #
    def _build_window(self) -> None:
        self.geometry("980x700")
        self.minsize(860, 620)
        self.title("Assistant")
        self.configure(fg_color=theme.BG_PAGE)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def _build_layout(self) -> None:
        self._build_scroll_container()
        self._build_slide_panel()
        self._build_header()
        self._build_files_section()
        self._build_message_section()
        self._build_logging_section()
        self._build_actions_section()
        self._build_floating_toggle()

        # Append each new log entry on the main thread (logs may come from worker threads).
        logger.subscribe(lambda entry: self.after(0, lambda e=entry: self._append_log(e)))

    def _build_scroll_container(self) -> None:
        page_canvas = tk.Canvas(self, highlightthickness=0, bg=theme.BG_PAGE)
        page_canvas.grid(row=0, column=0, sticky="nsew")

        page_scrollbar = ctk.CTkScrollbar(self, orientation="vertical", command=page_canvas.yview)
        page_scrollbar.grid(row=0, column=1, sticky="ns")
        page_canvas.configure(yscrollcommand=page_scrollbar.set)

        self.main_container = ctk.CTkFrame(page_canvas, fg_color="transparent")
        main_container_window = page_canvas.create_window((24, 24), window=self.main_container, anchor="nw")

        def _update_scroll_region(_event=None):
            page_canvas.configure(scrollregion=page_canvas.bbox("all"))

        def _fit_content_width(event):
            width = max(event.width - 48, 1)
            page_canvas.itemconfigure(main_container_window, width=width)

        def _on_mousewheel(event):
            #Don't scroll the page if the pointer is focused on inner-scrollables like the Logs panel.
            if self._pointer_over_inner_scroll(event):
                return
            page_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.main_container.bind("<Configure>", _update_scroll_region)
        page_canvas.bind("<Configure>", _fit_content_width)
        page_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(1, weight=1)
        self.main_container.grid_rowconfigure(2, weight=0)

    def _pointer_over_inner_scroll(self, event) -> bool:
        widget = self.winfo_containing(event.x_root, event.y_root)
        if widget is None:
            return False
        path = str(widget)
        for region in self._inner_scrollables:
            base = str(region)
            if path == base or path.startswith(base + "."):
                return True
        return False

    def _build_slide_panel(self) -> None:
        self.slide_panel = SlidePanel(
            self,
            side="right",
            width=0.30,
            title="Settings",
            fg_color=theme.BG_CARD,
            border_width=1,
            border_color=theme.BG_CARD_BORDER,
            corner_radius=0,
        )

        #Ensure that configs are saved when the panel is closed.
        self.slide_panel.panelClosingFallback(func=self._save_all_config)

        # The drawer (and its scrollable settings) handle their own wheel scrolling.
        self._inner_scrollables.append(self.slide_panel)

    def _build_header(self) -> None:
        header_card = ctk.CTkFrame(
            self.main_container,
            corner_radius=18,
            fg_color=theme.BG_CARD,
            border_width=1,
            border_color=theme.BG_CARD_BORDER,
        )
        header_card.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))

        label_title = ctk.CTkLabel(
            header_card,
            text="SLM RAG Assistant",
            font=theme.FONT_TITLE,
            text_color=theme.TEXT_PRIMARY,
        )
        label_title.pack(anchor="w", padx=20, pady=(16, 4))

    def _build_floating_toggle(self) -> None:
        """Drawer toggle pinned to the window so it stays put while content scrolls.

        Placed on the root window (not inside the scrollable canvas), so it keeps
        its top-right screen position regardless of how far the page is scrolled.
        """
        self.panel_toggle_button = ctk.CTkButton(
            self,
            text="⚙️",
            width=44,
            height=44,
            corner_radius=10,
            font=("Segoe UI", 20),
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER,
            command=self.slide_panel.toggle,
        )
        # relx=1.0 keeps it glued to the right edge; the x offset clears the scrollbar.
        self.panel_toggle_button.place(relx=1.0, x=-36, y=16, anchor="ne")
        self.panel_toggle_button.lift()

    def _build_files_section(self) -> None:
        files_block = ctk.CTkFrame(
            self.main_container,
            corner_radius=18,
            fg_color=theme.BG_CARD,
            border_width=1,
            border_color=theme.BG_CARD_BORDER,
        )
        files_block.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 14))

        label_fselect_description = ctk.CTkLabel(
            files_block,
            text="REFERENCE MATERIAL",
            font=theme.FONT_SECTION,
            text_color=theme.TEXT_MUTED,
        )
        label_fselect_description.pack(anchor="w", padx=20, pady=(16, 4))

        self.files_list = ctk.CTkFrame(
            files_block,
            corner_radius=18,
            fg_color=theme.BG_INSET,
            border_width=1,
            border_color=theme.BG_INSET_BORDER,
        )
        self.files_list.pack(fill="x", pady=5, padx=20)

        button_select_pdf = ctk.CTkButton(
            files_block,
            text="Select file",
            command=self.select_pdf,
            corner_radius=10,
            height=36,
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER,
        )
        button_select_pdf.pack(anchor="w", pady=5, padx=20)

    def _build_message_section(self) -> None:
        """Question entry and response box (share one card)."""
        self.message_block = ctk.CTkFrame(
            self.main_container,
            corner_radius=18,
            fg_color=theme.BG_CARD,
            border_width=1,
            border_color=theme.BG_CARD_BORDER,
        )
        self.message_block.grid_columnconfigure(0, weight=1)
        self.message_block.grid_columnconfigure(1, weight=1)
        self.message_block.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 14))

        label_question_header = ctk.CTkLabel(
            self.message_block,
            text="YOUR QUESTION",
            font=theme.FONT_SECTION,
            text_color=theme.TEXT_MUTED,
        )
        label_question_header.grid(row=0, columnspan=2, sticky="ew", padx=20, pady=5)

        # Multi-line textbox so long questions wrap instead of bleeding sideways.
        self.question = ctk.CTkTextbox(
            self.message_block,
            wrap="word",
            corner_radius=10,
            height=100,
            fg_color=theme.BG_FIELD,
            border_color=theme.FIELD_BORDER,
            border_width=1,
            text_color=theme.TEXT_PRIMARY,
        )
        self.question.grid(row=1, columnspan=2, sticky="ew", padx=20, pady=5)
        self._init_question_placeholder()

        #models folder selection
        path_models_block = ctk.CTkFrame(
            self.message_block,
            fg_color=theme.BG_FIELD
        )
        path_models_block.columnconfigure((0,1,3),weight=1)
        path_models_block.rowconfigure((0,1),weight=1)
        path_models_block.grid(row=2, columnspan=2, sticky="ew", padx=20, pady=5)

        self.entry_models_folder = ctk.CTkEntry(
            path_models_block,
            placeholder_text="C:/Path/To/Models/Folder/*GGUF",
            corner_radius=10,
            height=36,
            fg_color=theme.BG_FIELD,
            border_color=theme.FIELD_BORDER,
            text_color=theme.TEXT_PRIMARY,
        )
        self.entry_models_folder.grid(row=0, column=0, columnspan=2, sticky="ew", pady=5, padx=5)

        button_select_models_folder = ctk.CTkButton(
            path_models_block,
            text="Select models root folder",
            command=self.select_models_folder,
            corner_radius=10,
            height=36,
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER,
        )
        button_select_models_folder.grid(row=0, column=3, sticky="ew", pady=5, padx=5)

        self.button_prompt = ctk.CTkButton(
            path_models_block,
            text="Send",
            command=self.run_prompt,
            corner_radius=10,
            height=36,
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER,
        )
        self.button_prompt.grid(row=2, column=3, sticky="ew", pady=5, padx=5)

        # Always visible right under the Send button: gray while idle,
        # accent-colored and animated while a prompt is running.
        self.loading_bar = ctk.CTkProgressBar(path_models_block, mode="determinate")
        self.loading_bar.grid(row=3, column=3, sticky="ew", padx=5, pady=(0, 5))
        self._loading_bar_idle()

        #Response stuff
        label_response_header = ctk.CTkLabel(
            self.message_block,
            text="RESPONSE",
            font=theme.FONT_SECTION,
            text_color=theme.TEXT_MUTED,
        )
        label_response_header.grid(row=4, columnspan=2, sticky="ew", padx=20, pady=5)

        # Read-only textbox: wraps long answers and scrolls when they overflow.
        self.response_content = ctk.CTkTextbox(
            self.message_block,
            wrap="word",
            corner_radius=10,
            height=200,
            fg_color=theme.BG_FIELD,
            border_color=theme.FIELD_BORDER,
            border_width=1,
            text_color=theme.TEXT_PRIMARY,
            font=theme.FONT_RESPONSE,
        )
        self.response_content.grid(row=5, columnspan=2, sticky="ew", padx=20, pady=5)
        self.response_content.configure(state="disabled")

    # ------------------------------------------------------------------ #
    # Logging
    # ------------------------------------------------------------------ #

    def _build_logging_section(self) -> None:
        # Filter state: every level visible by default (DEBUG is dropped in release builds).
        self._log_rows: list[tuple[str, ctk.CTkFrame]] = []
        self._visible_levels = {lvl for lvl in LOG_LEVELS if not (IS_FROZEN and lvl == "DEBUG")}
        self._log_filter_buttons: dict[str, ctk.CTkButton] = {}

        logging_block = ctk.CTkFrame(
            self.main_container,
            corner_radius=18,
            fg_color=theme.BG_CARD,
            border_width=1,
            border_color=theme.BG_CARD_BORDER,
        )
        logging_block.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 14))

        label_logging_header = ctk.CTkLabel(
            logging_block,
            text="LOGS",
            font=theme.FONT_SECTION,
            text_color=theme.TEXT_MUTED,
        )
        label_logging_header.pack(anchor="w", padx=20, pady=(16, 4))

        # Buttons to show/hide log levels
        filter_bar = ctk.CTkFrame(logging_block, fg_color="transparent")
        filter_bar.pack(fill="x", padx=20, pady=(0, 6))
        for level in LOG_LEVELS:
            if IS_FROZEN and level == "DEBUG":
                continue  # debug logs are not shown in release builds
            icon_path = logger.icon_for_level(level)
            icon = ctk.CTkImage(light_image=Image.open(icon_path), size=(16, 16)) if icon_path else None
            button = ctk.CTkButton(
                filter_bar,
                text=level.capitalize(),
                image=icon,
                compound="left",
                width=88,
                height=30,
                corner_radius=8,
                fg_color=theme.ACCENT,
                hover_color=theme.ACCENT_HOVER,
                command=lambda lvl=level: self._toggle_log_level(lvl),
            )
            button.pack(side="left", padx=(0, 8))
            self._log_filter_buttons[level] = button

        ctk.CTkButton(
            filter_bar,
            text="Clear",
            width=70,
            height=30,
            corner_radius=8,
            fg_color=theme.DANGER,
            hover_color=theme.DANGER,
            command=self._clear_logs,
        ).pack(side="right")

        content_row = ctk.CTkFrame(logging_block, fg_color="transparent")
        content_row.pack(fill="x", padx=20, pady=(0, 16))
        content_row.grid_columnconfigure(0, weight=1)

        self.logging_content = ctk.CTkScrollableFrame(
            content_row,
            corner_radius=10,
            height=500,
            fg_color=theme.BG_FIELD,
            border_color=theme.FIELD_BORDER,
            border_width=1,
        )
        self.logging_content.grid(row=0, column=0, sticky="nsew")
        self._inner_scrollables.append(self.logging_content)

        # Arrow buttons above/below the scrollbar to step between messages.
        nav_col = ctk.CTkFrame(content_row, fg_color="transparent")
        nav_col.grid(row=0, column=1, sticky="ns", padx=(6, 0))
        ctk.CTkButton(nav_col, text="▲", width=28, height=28, corner_radius=8,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      command=lambda: self._log_nav(-1)).pack(side="top")
        ctk.CTkButton(nav_col, text="▼", width=28, height=28, corner_radius=8,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      command=lambda: self._log_nav(1)).pack(side="bottom")

        # Stepping also works with arrow keys.
        log_canvas = self.logging_content._parent_canvas
        log_canvas.configure(takefocus=True)
        log_canvas.bind("<Up>", lambda e: self._log_key_nav(-1))
        log_canvas.bind("<Down>", lambda e: self._log_key_nav(1))
        self.logging_content.bind("<Button-1>", lambda e: log_canvas.focus_set())

        # Render anything already logged before this view existed.
        for row in logger.get_messages(count=100):
            self._append_log(row["message"])

    def _append_log(self, entry: str) -> None:
        """Append a single log row. Incremental — existing rows are never rebuilt."""
        level = logger.level_of(entry)
        if IS_FROZEN and level == "DEBUG":
            return  # debug logs are suppressed in release builds

        parts = entry.split("\t", 2)
        header = " ".join(p.strip() for p in parts[:2])
        message = parts[2] if len(parts) > 2 else ""

        panel = ctk.CTkFrame(
            self.logging_content,
            fg_color=theme.MENU_FG,
            border_color=theme.FIELD_BORDER,
            border_width=1,
            corner_radius=8,
        )
        panel.grid_columnconfigure(1, weight=1)

        icon_path = logger.icon_for(entry)
        if icon_path:
            log_icon = ctk.CTkImage(light_image=Image.open(icon_path), size=(20, 20))
            ctk.CTkLabel(panel, image=log_icon, text="").grid(row=0, column=0, padx=12, pady=8)

        text_col = ctk.CTkFrame(panel, fg_color="transparent")
        text_col.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=8)

        header_label = ctk.CTkLabel(text_col, text=header, text_color=theme.TEXT_FAINT,
                                    anchor="w", justify="left")
        header_label.pack(fill="x", anchor="w")

        wrap_labels = [header_label]
        if message:
            message_label = ctk.CTkLabel(text_col, text=message, text_color=theme.TEXT_PRIMARY,
                                         anchor="w", justify="left")
            message_label.pack(fill="x", anchor="w")
            wrap_labels.append(message_label)

        def _sync_wrap(event, labels=wrap_labels):
            wrap = max(event.width - 8, 80)
            for label in labels:
                label.configure(wraplength=wrap)
        text_col.bind("<Configure>", _sync_wrap)

        self._log_rows.append((level, panel))
        if self._is_level_visible(level):
            panel.pack(fill="x", padx=10, pady=4)

    def _is_level_visible(self, level: str) -> bool:
        return level not in LOG_LEVELS or level in self._visible_levels

    def _toggle_log_level(self, level: str) -> None:
        if level in self._visible_levels:
            self._visible_levels.discard(level)
        else:
            self._visible_levels.add(level)

        button = self._log_filter_buttons.get(level)
        if button is not None:
            on = level in self._visible_levels
            button.configure(fg_color=theme.ACCENT if on else theme.MENU_FG)

        self._apply_log_filter()

    def _apply_log_filter(self) -> None:
        # Hidden rows invalidate the current selection.
        if self._selected_log_panel is not None and self._selected_log_panel.winfo_exists():
            self._selected_log_panel.configure(border_color=theme.FIELD_BORDER)
        self._selected_log_panel = None
        self._log_selected_index = -1

        for _level, frame in self._log_rows:
            frame.pack_forget()
        for level, frame in self._log_rows:
            if self._is_level_visible(level):
                frame.pack(fill="x", padx=10, pady=4)

    def _log_key_nav(self, delta: int) -> str:
        self._log_nav(delta)
        return "break"

    def _log_nav(self, delta: int) -> None:
        """Highlight and scroll to the previous/next visible log message."""
        visible = [panel for (lvl, panel) in self._log_rows if self._is_level_visible(lvl)]
        if not visible:
            return

        self._log_selected_index = max(0, min(len(visible) - 1, self._log_selected_index + delta))
        panel = visible[self._log_selected_index]

        if self._selected_log_panel is not None and self._selected_log_panel.winfo_exists():
            self._selected_log_panel.configure(border_color=theme.FIELD_BORDER)
        panel.configure(border_color=theme.ACCENT)
        self._selected_log_panel = panel

        canvas = self.logging_content._parent_canvas
        canvas.update_idletasks()
        bbox = canvas.bbox("all")
        if bbox and bbox[3] - bbox[1] > 0:
            canvas.yview_moveto(max(0.0, min(1.0, panel.winfo_y() / (bbox[3] - bbox[1]))))
        canvas.focus_set()  # keep focus on the logs so the arrow keys keep working

    def _clear_logs(self) -> None:
        for _level, panel in self._log_rows:
            panel.destroy()
        self._log_rows.clear()
        self._selected_log_panel = None
        self._log_selected_index = -1

    # ------------------------------------------------------------------ #
    # Loading bar states
    # ------------------------------------------------------------------ #
    def _loading_bar_idle(self) -> None:
        """Full gray bar: nothing is running."""
        self.loading_bar.stop()
        self.loading_bar.configure(mode="determinate", progress_color=theme.LOADING_IDLE)
        self.loading_bar.set(1.0)

    def _loading_bar_active(self) -> None:
        """Accent-colored indeterminate animation while a prompt runs."""
        self.loading_bar.configure(mode="indeterminate", progress_color=theme.ACCENT_HOVER)
        self.loading_bar.start()

    # ------------------------------------------------------------------ #
    # Question / response text helpers
    # ------------------------------------------------------------------ #
    def _init_question_placeholder(self) -> None:
        self._question_showing_placeholder = True
        self.question.insert("0.0", QUESTION_PLACEHOLDER)
        self.question.configure(text_color=theme.TEXT_FAINT)
        self.question.bind("<FocusIn>", self._on_question_focus_in)
        self.question.bind("<FocusOut>", self._on_question_focus_out)

    def _on_question_focus_in(self, _event=None) -> None:
        if self._question_showing_placeholder:
            self.question.delete("0.0", "end")
            self.question.configure(text_color=theme.TEXT_PRIMARY)
            self._question_showing_placeholder = False

    def _on_question_focus_out(self, _event=None) -> None:
        if not self.question.get("0.0", "end").strip():
            self._show_question_placeholder()

    def _show_question_placeholder(self) -> None:
        self.question.delete("0.0", "end")
        self.question.insert("0.0", QUESTION_PLACEHOLDER)
        self.question.configure(text_color=theme.TEXT_FAINT)
        self._question_showing_placeholder = True

    def _get_question(self) -> str:
        if self._question_showing_placeholder:
            return ""
        return self.question.get("0.0", "end").strip()

    def _set_question(self, text: str) -> None:
        self._question_showing_placeholder = False
        self.question.delete("0.0", "end")
        self.question.insert("0.0", text)
        self.question.configure(text_color=theme.TEXT_PRIMARY)

    def _set_response(self, text: str) -> None:
        self.response_content.configure(state="normal")
        self.response_content.delete("0.0", "end")
        self.response_content.insert("0.0", text)
        self.response_content.configure(state="disabled")

    def _build_actions_section(self) -> None:
        actions_block = ctk.CTkScrollableFrame(
            self.slide_panel.body,
            corner_radius=18,
            fg_color=theme.BG_CARD,
            border_width=1,
            border_color=theme.BG_CARD_BORDER,
        )
        actions_block.pack(fill="both", expand=True, padx=4, pady=4)
        actions_block.grid_columnconfigure(0, weight=1)
        self._inner_scrollables.append(actions_block)

        label_language = ctk.CTkLabel(actions_block, text="Language", font=theme.FONT_LABEL, text_color=theme.TEXT_MUTED)
        label_language.grid(row=0, sticky="ew", padx=20, pady=5)

        self.language_selector = ctk.CTkOptionMenu(
            actions_block,
            values=["EN", "PTBR"],
            command=self.on_language_changed,
            fg_color=theme.MENU_FG,
            button_color=theme.MENU_BUTTON,
            button_hover_color=theme.MENU_BUTTON_HOVER,
            dropdown_fg_color=theme.MENU_DROPDOWN,
            corner_radius=10,
            height=38,
        )
        self.language_selector.grid(row=1, sticky="ew", padx=20, pady=5)

        label_query_model = ctk.CTkLabel(actions_block, text="Query Model", font=theme.FONT_LABEL, text_color=theme.TEXT_MUTED)
        label_query_model.grid(row=2, sticky="ew", padx=20, pady=5)

        self.model_selector_query = ctk.CTkOptionMenu(
            actions_block,
            values=self.downloaded_models,
            fg_color=theme.MENU_FG,
            button_color=theme.MENU_BUTTON,
            button_hover_color=theme.MENU_BUTTON_HOVER,
            dropdown_fg_color=theme.MENU_DROPDOWN,
            corner_radius=10,
            height=38,
        )
        self.model_selector_query.grid(row=3, sticky="ew", padx=20, pady=5)

        label_reasoning_model = ctk.CTkLabel(actions_block, text="Reasoning Model", font=theme.FONT_LABEL, text_color=theme.TEXT_MUTED)
        label_reasoning_model.grid(row=4, sticky="ew", padx=20, pady=5)

        self.model_selector_reasoning = ctk.CTkOptionMenu(
            actions_block,
            values=self.downloaded_models,
            fg_color=theme.MENU_FG,
            button_color=theme.MENU_BUTTON,
            button_hover_color=theme.MENU_BUTTON_HOVER,
            dropdown_fg_color=theme.MENU_DROPDOWN,
            corner_radius=10,
            height=38,
        )
        self.model_selector_reasoning.grid(row=5, sticky="ew", padx=20, pady=5)

        label_mode = ctk.CTkLabel(actions_block, text="Mode", font=theme.FONT_LABEL, text_color=theme.TEXT_MUTED)
        label_mode.grid(row=6, sticky="ew", padx=20, pady=5)

        self.mode_selector = ctk.CTkOptionMenu(
            actions_block,
            values=["Adaptive", "Exact"],
            fg_color=theme.MENU_FG,
            button_color=theme.MENU_BUTTON,
            button_hover_color=theme.MENU_BUTTON_HOVER,
            dropdown_fg_color=theme.MENU_DROPDOWN,
            corner_radius=10,
            height=38,
        )
        self.mode_selector.grid(row=7, sticky="ew", padx=20, pady=5)

        # Tunable generation / retrieval settings
        self.temperature_slider = self._make_slider(
            actions_block, 8, "Temperature", from_=0.0, to=1.0, steps=20, default=DEFAULT_TEMPERATURE)
        self.query_count_slider = self._make_slider(
            actions_block, 10, "Query count", from_=1, to=10, steps=9, default=DEFAULT_QUERY_COUNT, fmt="{:.0f}")
        self.query_temperature_slider = self._make_slider(
            actions_block, 12, "Query gen. temperature", from_=0.0, to=1.0, steps=20, default=DEFAULT_QUERY_TEMPERATURE)
        self.score_minimum_slider = self._make_slider(
            actions_block, 14, "Min. query score", from_=0.0, to=1.0, steps=20, default=DEFAULT_SCORE_MINIMUM)
        self.chunk_density_slider = self._make_slider(
            actions_block, 16, "Chunk min. density", from_=0.0, to=1.0, steps=20, default=DEFAULT_CHUNK_DENSITY)
        self.chunk_diversity_slider = self._make_slider(
            actions_block, 18, "Chunk min. diversity", from_=0.0, to=1.0, steps=20, default=DEFAULT_CHUNK_DIVERSITY)
        self.chunk_avg_sent_slider = self._make_slider(
            actions_block, 20, "Chunk min. avg. sentence", from_=0.0, to=20.0, steps=40, default=DEFAULT_CHUNK_AVG_SENT, fmt="{:.1f}")

        self.loading_status = ctk.CTkLabel(actions_block, text="", text_color=theme.TEXT_FAINT, anchor="w")

        self.hosting_address = ctk.CTkEntry(
            actions_block,
            placeholder_text="0.0.0.0",
            corner_radius=10,
            height=36,
            fg_color=theme.BG_FIELD,
            border_color=theme.FIELD_BORDER,
            text_color=theme.TEXT_PRIMARY,
        )
        self.hosting_address.grid(row=22, sticky="ew", pady=5, padx=5)

        self.hosting_port = ctk.CTkEntry(
            actions_block,
            placeholder_text="0000",
            corner_radius=10,
            height=36,
            fg_color=theme.BG_FIELD,
            border_color=theme.FIELD_BORDER,
            text_color=theme.TEXT_PRIMARY,
        )
        self.hosting_port.grid(row=23, sticky="ew", pady=5, padx=5)

        self.switch_tcp_toggle = ctk.CTkSwitch(actions_block, text="TCP", command=self.on_host_toggled)
        self.switch_tcp_toggle.grid(row=24, sticky="ew", pady=5, padx=5)

    def _make_slider(self, parent, row: int, label_text: str, *, from_: float, to: float,
                     steps: int, default: float, fmt: str = "{:.2f}") -> ctk.CTkSlider:
        """Add a labelled slider (label on ``row``, slider on ``row + 1``).

        The label shows the live value; returns the slider so callers can read it.
        """
        label = ctk.CTkLabel(parent, text=f"{label_text}: {fmt.format(default)}",
                             font=theme.FONT_LABEL, text_color=theme.TEXT_MUTED)
        label.grid(row=row, sticky="ew", padx=20, pady=(8, 0))

        def update_label(value) -> None:
            label.configure(text=f"{label_text}: {fmt.format(float(value))}")

        slider = ctk.CTkSlider(
            parent,
            from_=from_,
            to=to,
            number_of_steps=steps,
            button_color=theme.ACCENT,
            button_hover_color=theme.ACCENT_HOVER,
            progress_color=theme.ACCENT,
            command=update_label,
        )
        slider.set(default)
        slider.grid(row=row + 1, sticky="ew", padx=20, pady=(0, 6))
        slider._update_label = update_label  # let _set_slider refresh the text on config restore
        return slider

    # ------------------------------------------------------------------ #
    # Settings accessors (read current widget values for the model)
    # ------------------------------------------------------------------ #
    def _get_temperature(self) -> float:
        return float(self.temperature_slider.get())

    def _get_query_count(self) -> int:
        return int(round(self.query_count_slider.get()))

    def _get_query_temperature(self) -> float:
        return float(self.query_temperature_slider.get())

    def _get_score_minimum(self) -> float:
        return float(self.score_minimum_slider.get())

    def _get_chunk_density(self) -> float:
        return float(self.chunk_density_slider.get())

    def _get_chunk_diversity(self) -> float:
        return float(self.chunk_diversity_slider.get())

    def _get_chunk_avg_sentence(self) -> float:
        return float(self.chunk_avg_sent_slider.get())

    # ------------------------------------------------------------------ #
    # TCP socket (serve requests from outside the UI)
    # ------------------------------------------------------------------ #
    def _start_tcp_socket(self) -> None:
        self._event_loop = asyncio.new_event_loop()
        self._asyncio_thread = threading.Thread(
            target=self._run_asyncio_loop, args=(self._event_loop,), daemon=True
        )
        self._asyncio_thread.start()
        self.tcp_socket = AssistantRequestSocket(port=TCP_PORT)
        self.tcp_socket.set_event_loop(self._event_loop)

    @staticmethod
    def _run_asyncio_loop(loop) -> None:
        asyncio.set_event_loop(loop)
        loop.run_forever()

    def on_host_toggled(self) -> None:
        self.hosting_port.delete(0, "end")
        self.hosting_address.delete(0, "end")
        if self.switch_tcp_toggle.get() == 1:
            self.hosting_port.insert(0, self.tcp_socket.port)
            self.hosting_address.insert(0, self.tcp_socket.host)

        self.tcp_socket.toggle_sync(state=self.switch_tcp_toggle.get(), tcp_callback=self._tcp_request_handler)

    def _tcp_request_handler(self, message: str) -> str:
        try:
            if self.model is None:
                from src.model import Model
                self.model = Model(query_count=self._get_query_count(),
                                   lang=self.language_selector.get(),
                                   query_model=self.model_selector_query.get(),
                                   reason_model=self.model_selector_reasoning.get(),
                                   mode=self.mode_selector.get().lower(),
                                   temperature=self._get_temperature(),
                                   query_temperature=self._get_query_temperature(),
                                   score_minimum=self._get_score_minimum(),
                                   chunk_min_density=self._get_chunk_density(),
                                   chunk_min_diversity=self._get_chunk_diversity(),
                                   chunk_min_avg_sentence=self._get_chunk_avg_sentence())
            else:
                self.model.set_query_model(self.model_selector_query.get())
                self.model.set_resoning_model(self.model_selector_reasoning.get())
                self.model.set_language(self.language_selector.get())
                self.model.set_mode(self.mode_selector.get().lower())
                self.model.set_temperature(self._get_temperature())
                self.model.set_query_count(self._get_query_count())
                self.model.set_query_temperature(self._get_query_temperature())
                self.model.set_score_minimum(self._get_score_minimum())
                self.model.set_chunk_validation(self._get_chunk_density(), self._get_chunk_diversity(), self._get_chunk_avg_sentence())

            data = self.tcp_socket.parse_response(message)
            user_question = data.get("question", "").strip()
            if not user_question:
                return '{"error": "Missing required field: question"}'

            self.after(0, lambda: self._set_question(user_question))

            self.model.model_manager.set_models_root_path(self.entry_models_folder.get())

            ingest_files = collect_ingest_files(self.files)
            if ingest_files:
                self.model.addPdfs(ingest_files)

            answer = self.model.prompt(user_question=user_question)
            self.after(0, lambda: self._finish_run(answer=answer))
            return answer if isinstance(answer, str) else json.dumps(answer)
        except ValueError as exc:
            return f'{{"error": "{str(exc)}"}}'
        except Exception as exc:
            return f'{{"error": "{str(exc)}"}}'

    # ------------------------------------------------------------------ #
    # Model lifecycle
    # ------------------------------------------------------------------ #
    def _on_model_ready(self) -> None:
        """Close the one-time initialization dialog once the model has loaded."""
        if self.initialize_dialog is not None:
            self.initialize_dialog.close("Model loaded")
            self.initialize_dialog = None

    def on_language_changed(self, choice: str) -> None:
        if self.model is not None:
            threading.Thread(target=lambda: self.model.set_language(choice), daemon=True).start()

    def model_select_callback(self, choice, option_menu: ctk.CTkOptionMenu) -> None:
        if not choice:
            pass

        downloaded_models = self.get_downloaded_models()
        if downloaded_models.__contains__(str(choice)):
            option_menu.configure(fg_color=theme.MODEL_PRESENT, hover_color=theme.MODEL_PRESENT)
        else:
            option_menu.configure(fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER)

    def model_download(self, model_name: str) -> None:
        from src.dialog.model_download import ModelDownloadDialog
        dialog = ModelDownloadDialog(self, self.model.model_manager, model_name)
        dialog.pack()

    def get_downloaded_models(self) -> list[str]:
        print(f"models folder: {self.selected_models_folder}")
        model_list = self.model.model_manager.list_downloaded()
        if not model_list or len(model_list) == 0:
            model_list = [" "]
            self.after(600, lambda: ModelsWarningDialog(self, on_folder_selected=self._apply_models_folder))

        return model_list

    # ------------------------------------------------------------------ #
    # Models folder selection
    # ------------------------------------------------------------------ #
    def _apply_models_folder(self, path: str) -> None:
        self.selected_models_folder = path
        self.entry_models_folder.delete(0, "end")
        self.entry_models_folder.insert(0, path)

        if self.model is not None:
            self.model.model_manager.set_models_root_path(path)
            new_models = self.model.model_manager.list_downloaded()
        else:
            new_models = [f.name for f in Path(path).rglob("*.gguf")]

        if not new_models:
            new_models = [" "]
        self.model_selector_query.configure(values=new_models)
        self.model_selector_reasoning.configure(values=new_models)
        # self.model_selector_query.set(new_models[0])
        # self.model_selector_reasoning.set(new_models[0])

    def select_models_folder(self) -> None:
        selected = filedialog.askdirectory(title="Select models root folder")
        if not selected:
            return

        self.entry_models_folder.delete(0, "end")
        self.entry_models_folder.insert(0, selected)

        gguf_files = list(Path(selected).rglob("*.gguf"))
        if not gguf_files:
            ModelsWarningDialog(self, on_folder_selected=self._apply_models_folder)
            return

        self._apply_models_folder(selected)

    # ------------------------------------------------------------------ #
    # PDF reference files
    # ------------------------------------------------------------------ #
    def _load_initial_files(self) -> None:
        self.files.extend(load_pdfs_from_folder(DATA_FOLDER))
        self.update_files_list()

    def select_pdf(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select a PDF file",
            filetypes=[("PDF files", "*.pdf")],
        )
        if selected:
            name = selected.split('/')[-1]
            self.files.append({
                'name': name,
                'path': selected,
                'metadata': ""
            })
            self.update_files_list()

    def _sync_pdf_metadata(self, file_entry: dict, entry_widget: ctk.CTkEntry) -> None:
        metadata = entry_widget.get().strip()
        if len(metadata) > 15:
            metadata = metadata[:15]
            entry_widget.delete(0, "end")
            entry_widget.insert(0, metadata)

        file_entry['metadata'] = metadata

    def update_files_list(self) -> None:
        for widget in self.files_list.winfo_children():
            widget.destroy()

        raw_img = Image.open(PDF_ICON_PATH)
        pdf_image = ctk.CTkImage(light_image=raw_img, size=(20, 20))

        for f in self.files:
            file_frame = ctk.CTkFrame(self.files_list, fg_color="transparent")
            file_frame.pack(fill="x", padx=10, pady=5)

            icon_label = ctk.CTkLabel(file_frame, image=pdf_image, text="")
            icon_label.pack(side="left", padx=(0, 10))

            name_label = ctk.CTkLabel(file_frame, text=f['name'], text_color=theme.TEXT_PRIMARY)
            name_label.pack(side="left")

            metadata_entry = ctk.CTkEntry(
                file_frame,
                width=120,
                height=30,
                placeholder_text="metadata",
                fg_color=theme.BG_FIELD,
                border_color=theme.FIELD_BORDER,
                text_color=theme.TEXT_PRIMARY,
            )
            metadata_entry.insert(0, f.get('metadata', ''))
            metadata_entry.bind(
                "<KeyRelease>",
                lambda event, file_entry=f, entry_widget=metadata_entry: self._sync_pdf_metadata(file_entry, entry_widget)
            )
            metadata_entry.pack(side="right", padx=(8, 0))

            remove_btn = ctk.CTkButton(
                file_frame,
                text="X",
                text_color=theme.TEXT_PRIMARY,
                fg_color=theme.DANGER,
                width=32,
                height=32,
                command=lambda file=f: self._remove_and_reload(file),
            )
            remove_btn.pack(side="right")

    def _remove_and_reload(self, file) -> None:
        self.files.remove(file)
        self.update_files_list()

    # ------------------------------------------------------------------ #
    # Running a prompt
    # ------------------------------------------------------------------ #
    def run_prompt(self) -> None:
        logger.info("Initializing model...")
        user_question = self._get_question()
        if not user_question:
            self._set_response("Please type a question before running.")
            return

        self.button_prompt.configure(state="disabled", text="Running...")
        self.loading_status.configure(text="Loading model...")
        self._loading_bar_active()

        if self.model is None and not self._init_dialog_shown:
            self.initialize_dialog = ModelInitializeDialog(self)
            self._init_dialog_shown = True

        logger.info("Initializing model class...")
        def worker() -> None:
            try:
                if self.model is None:
                    from src.model import Model
                    self.model = Model(query_count=self._get_query_count(),
                                       lang=self.language_selector.get(),
                                       query_model=self.model_selector_query.get(),
                                       reason_model=self.model_selector_reasoning.get(),
                                       mode=self.mode_selector.get().lower(),
                                       temperature=self._get_temperature(),
                                       query_temperature=self._get_query_temperature(),
                                       score_minimum=self._get_score_minimum(),
                                       chunk_min_density=self._get_chunk_density(),
                                       chunk_min_diversity=self._get_chunk_diversity(),
                                       chunk_min_avg_sentence=self._get_chunk_avg_sentence())
                    self.model.model_manager.set_models_root_path(self.entry_models_folder.get())
                    self.after(0, self._on_model_ready)
                else:
                    self.model.model_manager.set_models_root_path(self.entry_models_folder.get())
                    self.model.set_query_model(self.model_selector_query.get())
                    self.model.set_resoning_model(self.model_selector_reasoning.get())
                    self.model.set_language(self.language_selector.get())
                    self.model.set_mode(self.mode_selector.get().lower())
                    self.model.set_temperature(self._get_temperature())
                    self.model.set_query_count(self._get_query_count())
                    self.model.set_query_temperature(self._get_query_temperature())
                    self.model.set_score_minimum(self._get_score_minimum())
                    self.model.set_chunk_validation(self._get_chunk_density(), self._get_chunk_diversity(), self._get_chunk_avg_sentence())

                ingest_files = collect_ingest_files(self.files)
                if ingest_files:
                    self.model.addPdfs(ingest_files)

                self.after(0, lambda: self.loading_status.configure(text="Generating response..."))
                answer = self.model.prompt(user_question=user_question)
                self.after(0, lambda: self._finish_run(answer=answer))
            except ValueError as exc:
                error_message = str(exc)
                self.after(0, lambda error_message=error_message: self._finish_run(error=error_message))
            except Exception as exc:
                error_message = str(exc)
                self.after(0, lambda error_message=error_message: self._finish_run(error=error_message))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_run(self, answer="", error: str = "") -> None:
        self._loading_bar_idle()
        self.loading_status.configure(text="")
        self.button_prompt.configure(state="normal", text="Send")
        if error:
            if self.initialize_dialog is not None:
                self.initialize_dialog.fail(f"Model load failed: {error}")
                self.initialize_dialog = None
            self._set_response(f"Run failed: {error}")
            print(f"Run failed: {error}")
            logger.error(f"Run failed: {error}")
            return

        if isinstance(answer, dict):
            ansjson = answer
        else:
            try:
                ansjson = json.loads(answer)
            except json.JSONDecodeError:
                self._set_response(str(answer))
                return

        response_value = f"""
    RESPONSE:
    {ansjson.get('answer', '')}

    SOURCES:
    {ansjson.get('sources', '')}
    """

        self._set_response(response_value)
        logger.debug("Generation finished.")

    # ------------------------------------------------------------------ #
    # Config persistence
    # ------------------------------------------------------------------ #
    def _set_slider(self, slider: ctk.CTkSlider, value: float) -> None:
        """Set a slider's value and refresh its label (``set`` skips the command)."""
        slider.set(value)
        slider._update_label(value)

    def _apply_saved_config(self) -> None:
        config_json = get_config()
        if not config_json:
            return

        self.selected_models_folder = config_json['root_model_path']
        self.entry_models_folder.delete(0, "end")
        self.entry_models_folder.insert(0, config_json['root_model_path'])
        self.files = [normalize_pdf_file(file_entry) for file_entry in config_json['documents']]
        self.language_selector.set(config_json['language'])
        self.model_selector_query.set(config_json['model_query'])
        self.model_selector_reasoning.set(config_json['model_reason'])
        self.update_files_list()
        self._apply_models_folder(config_json['root_model_path'])

        # Tunable generation / retrieval settings 
        settings = config_json.get('settings', {})
        self._set_slider(self.temperature_slider, settings.get('temperature', DEFAULT_TEMPERATURE))
        self._set_slider(self.query_count_slider, settings.get('query_count', DEFAULT_QUERY_COUNT))
        self._set_slider(self.query_temperature_slider, settings.get('query_temperature', DEFAULT_QUERY_TEMPERATURE))
        self._set_slider(self.score_minimum_slider, settings.get('score_minimum', DEFAULT_SCORE_MINIMUM))
        self._set_slider(self.chunk_density_slider, settings.get('chunk_density', DEFAULT_CHUNK_DENSITY))
        self._set_slider(self.chunk_diversity_slider, settings.get('chunk_diversity', DEFAULT_CHUNK_DIVERSITY))
        self._set_slider(self.chunk_avg_sent_slider, settings.get('chunk_avg_sentence', DEFAULT_CHUNK_AVG_SENT))

    def _save_all_config(self):
        save_config(
            root_model_path=self.entry_models_folder.get(),
            previous_question=self._get_question(),
            documents=self.files,
            language=self.language_selector.get(),
            model_query=self.model_selector_query.get(),
            model_reason=self.model_selector_reasoning.get(),
            settings={
                "temperature": self._get_temperature(),
                "query_count": self._get_query_count(),
                "query_temperature": self._get_query_temperature(),
                "score_minimum": self._get_score_minimum(),
                "chunk_density": self._get_chunk_density(),
                "chunk_diversity": self._get_chunk_diversity(),
                "chunk_avg_sentence": self._get_chunk_avg_sentence(),
            })
    
    def _on_closing(self) -> None:
        print("Encerrando aplicativo...")
        self._save_all_config()
        self.destroy()
