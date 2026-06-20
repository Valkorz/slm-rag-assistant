import tkinter as tk
import customtkinter as ctk
import asyncio
import json
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

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

DATA_FOLDER = "./data/"
PDF_ICON_PATH = "images/pdf.png"
TCP_PORT = 8008


class AssistantApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Runtime state
        self.files: list[dict] = []
        self.downloaded_models = ["None"]
        self.model = None
        self.initialize_dialog = None
        self.selected_models_folder = ""

        self._build_window()
        self._start_tcp_socket()
        self._build_layout()

        self._load_initial_files()
        self._start_model_initialization()
        self._apply_saved_config()

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
        self._build_header()
        self._build_files_section()
        self._build_message_section()
        self._build_actions_section()

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
            page_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.main_container.bind("<Configure>", _update_scroll_region)
        page_canvas.bind("<Configure>", _fit_content_width)
        page_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(1, weight=1)
        self.main_container.grid_rowconfigure(2, weight=0)

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
        message_block = ctk.CTkFrame(
            self.main_container,
            corner_radius=18,
            fg_color=theme.BG_CARD,
            border_width=1,
            border_color=theme.BG_CARD_BORDER,
        )
        message_block.grid_columnconfigure(0, weight=1)
        message_block.grid_columnconfigure(1, weight=1)
        message_block.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 14))

        label_question_header = ctk.CTkLabel(
            message_block,
            text="YOUR QUESTION",
            font=theme.FONT_SECTION,
            text_color=theme.TEXT_MUTED,
        )
        label_question_header.grid(row=0, columnspan=2, sticky="ew", padx=20, pady=5)

        self.question = ctk.CTkEntry(
            message_block,
            placeholder_text="Write your question here...",
            corner_radius=10,
            height=100,
            fg_color=theme.BG_FIELD,
            border_color=theme.FIELD_BORDER,
            text_color=theme.TEXT_PRIMARY,
        )
        self.question.grid(row=1, columnspan=2, sticky="ew", padx=20, pady=5)

        label_response_header = ctk.CTkLabel(
            message_block,
            text="RESPONSE",
            font=theme.FONT_SECTION,
            text_color=theme.TEXT_MUTED,
        )
        label_response_header.grid(row=2, columnspan=2, sticky="ew", padx=20, pady=5)

        response_block = ctk.CTkFrame(
            message_block,
            corner_radius=10,
            fg_color=theme.BG_FIELD,
            border_color=theme.FIELD_BORDER,
            border_width=1,
        )
        response_block.grid(row=3, columnspan=2, sticky="ew", padx=20, pady=5)
        response_block.grid_columnconfigure(0, weight=1)

        self.response_content = ctk.CTkLabel(
            response_block,
            text="",
            font=theme.FONT_RESPONSE,
            text_color=theme.TEXT_PRIMARY,
            justify="left",
            anchor="nw",
        )
        self.response_content.grid(row=0, column=0, sticky="ew", padx=12, pady=12)

        def _sync_response_wrap(event):
            wrap = max(event.width - 24, 120)
            self.response_content.configure(wraplength=wrap)

        response_block.bind("<Configure>", _sync_response_wrap)

    def _build_actions_section(self) -> None:
        """Selectors (language/models/mode), run button, models folder, TCP host."""
        actions_block = ctk.CTkFrame(
            self.main_container,
            corner_radius=18,
            fg_color=theme.BG_CARD,
            height=50,
            border_width=1,
            border_color=theme.BG_CARD_BORDER,
        )
        actions_block.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        actions_block.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="group1")
        actions_block.grid_rowconfigure(0, weight=1)
        actions_block.grid_rowconfigure(1, weight=1)

        label_language = ctk.CTkLabel(actions_block, text="Language", font=theme.FONT_LABEL, text_color=theme.TEXT_MUTED)
        label_language.grid(row=0, column=0, sticky="ew", padx=20, pady=5)

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
        self.language_selector.grid(row=1, column=0, sticky="ew", padx=20, pady=5)

        label_query_model = ctk.CTkLabel(actions_block, text="Query Model", font=theme.FONT_LABEL, text_color=theme.TEXT_MUTED)
        label_query_model.grid(row=0, column=1, sticky="ew", padx=20, pady=5)

        label_reasoning_model = ctk.CTkLabel(actions_block, text="Reasoning Model", font=theme.FONT_LABEL, text_color=theme.TEXT_MUTED)
        label_reasoning_model.grid(row=0, column=2, sticky="ew", padx=20, pady=5)

        label_mode = ctk.CTkLabel(actions_block, text="Mode", font=theme.FONT_LABEL, text_color=theme.TEXT_MUTED)
        label_mode.grid(row=0, column=3, sticky="ew", padx=20, pady=5)

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
        self.model_selector_query.grid(row=1, column=1, sticky="ew", padx=20, pady=5)

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
        self.model_selector_reasoning.grid(row=1, column=2, sticky="ew", padx=20, pady=5)

        self.mode_selector = ctk.CTkOptionMenu(
            actions_block,
            values=["Document", "Financial"],
            fg_color=theme.MENU_FG,
            button_color=theme.MENU_BUTTON,
            button_hover_color=theme.MENU_BUTTON_HOVER,
            dropdown_fg_color=theme.MENU_DROPDOWN,
            corner_radius=10,
            height=38,
        )
        self.mode_selector.grid(row=1, column=3, sticky="ew", padx=20, pady=5)

        self.button_prompt = ctk.CTkButton(
            actions_block,
            text="Run",
            command=self.run_prompt,
            corner_radius=10,
            height=36,
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER,
            state="disabled",
        )
        self.button_prompt.grid(row=2, column=3, sticky="ew", pady=5)

        self.entry_models_folder = ctk.CTkEntry(
            actions_block,
            placeholder_text="C:/Path/To/Models/Folder/*GGUF",
            corner_radius=10,
            height=36,
            fg_color=theme.BG_FIELD,
            border_color=theme.FIELD_BORDER,
            text_color=theme.TEXT_PRIMARY,
        )
        self.entry_models_folder.grid(row=3, column=0, columnspan=3, sticky="ew", pady=5, padx=5)

        button_select_models_folder = ctk.CTkButton(
            actions_block,
            text="Select models root folder",
            command=self.select_models_folder,
            corner_radius=10,
            height=36,
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER,
        )
        button_select_models_folder.grid(row=3, column=3, sticky="ew", pady=5, padx=5)

        # Created but only shown on demand (loading bar is gridded in run_prompt).
        self.loading_status = ctk.CTkLabel(actions_block, text="", text_color=theme.TEXT_FAINT, anchor="w")
        self.loading_bar = ctk.CTkProgressBar(actions_block, mode="indeterminate", progress_color=theme.ACCENT_HOVER)

        self.hosting_address = ctk.CTkEntry(
            actions_block,
            placeholder_text="0.0.0.0",
            corner_radius=10,
            height=36,
            fg_color=theme.BG_FIELD,
            border_color=theme.FIELD_BORDER,
            text_color=theme.TEXT_PRIMARY,
        )
        self.hosting_address.grid(row=4, column=0, columnspan=2, sticky="ew", pady=5, padx=5)

        self.hosting_port = ctk.CTkEntry(
            actions_block,
            placeholder_text="0000",
            corner_radius=10,
            height=36,
            fg_color=theme.BG_FIELD,
            border_color=theme.FIELD_BORDER,
            text_color=theme.TEXT_PRIMARY,
        )
        self.hosting_port.grid(row=4, column=2, sticky="ew", pady=5, padx=5)

        self.switch_tcp_toggle = ctk.CTkSwitch(actions_block, text="TCP", command=self.on_host_toggled)
        self.switch_tcp_toggle.grid(row=4, column=3, sticky="ew", pady=5, padx=5)

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
                self.model = Model(query_count=5,
                                   lang=self.language_selector.get(),
                                   query_model=self.model_selector_query.get(),
                                   reason_model=self.model_selector_reasoning.get(),
                                   mode=self.mode_selector.get().lower())
            else:
                self.model.set_query_model(self.model_selector_query.get())
                self.model.set_resoning_model(self.model_selector_reasoning.get())
                self.model.set_language(self.language_selector.get())
                self.model.set_mode(self.mode_selector.get().lower())

            data = self.tcp_socket.parse_response(message)
            user_question = data.get("question", "").strip()
            if not user_question:
                return '{"error": "Missing required field: question"}'

            self.after(0, lambda: self.question.delete(0, "end"))
            self.after(0, lambda: self.question.insert(0, user_question))

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
    def _start_model_initialization(self) -> None:
        self.initialize_dialog = ModelInitializeDialog(self)
        self.after(0, lambda: threading.Thread(target=self.initialize_model, daemon=True).start())

    # Lazy initialization for the model to avoid long loading times for the window.
    def initialize_model(self) -> None:
        from src.model import Model
        try:
            self.model = Model(query_count=5)
            self.model.model_manager.set_models_root_path(root_path=self.selected_models_folder)
            self.downloaded_models = self.get_downloaded_models()
            self.after(0, self._on_model_ready)
        except Exception as exc:
            self.after(0, lambda error_message=str(exc): self._on_model_error(error_message))

    def _on_model_ready(self) -> None:
        self.button_prompt.configure(state="normal")
        self.model_selector_query.configure(values=self.downloaded_models)
        self.model_selector_reasoning.configure(values=self.downloaded_models)
        if self.initialize_dialog is not None:
            self.initialize_dialog.close("Model loaded")

    def _on_model_error(self, error_message: str) -> None:
        self.button_prompt.configure(state="disabled")
        if self.initialize_dialog is not None:
            self.initialize_dialog.fail(f"Model load failed: {error_message}")

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
        self.model_selector_query.set(new_models[0])
        self.model_selector_reasoning.set(new_models[0])

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
        user_question = self.question.get().strip()
        if not user_question:
            self.response_content.configure(text="Please type a question before running.")
            return

        self.button_prompt.configure(state="disabled", text="Running...")
        self.loading_status.configure(text="Loading model...")
        self.loading_bar.grid(row=2, column=0, columnspan=3, sticky="ew", padx=20, pady=(8, 0))
        self.loading_bar.start()

        self.model.model_manager.set_models_root_path(self.entry_models_folder.get())

        def worker() -> None:
            try:
                if self.model is None:
                    from src.model import Model
                    self.model = Model(query_count=5,
                                       lang=self.language_selector.get(),
                                       query_model=self.model_selector_query.get(),
                                       reason_model=self.model_selector_reasoning.get(),
                                       mode=self.mode_selector.get().lower())
                else:
                    self.model.set_query_model(self.model_selector_query.get())
                    self.model.set_resoning_model(self.model_selector_reasoning.get())
                    self.model.set_language(self.language_selector.get())
                    self.model.set_mode(self.mode_selector.get().lower())

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
        self.loading_bar.stop()
        self.loading_bar.grid_remove()
        self.loading_status.configure(text="")
        self.button_prompt.configure(state="normal", text="Run")
        if error:
            self.response_content.configure(text=f"Run failed: {error}")
            print(f"Run failed: {error}")
            return

        if isinstance(answer, dict):
            ansjson = answer
        else:
            try:
                ansjson = json.loads(answer)
            except json.JSONDecodeError:
                self.response_content.configure(text=str(answer))
                return

        response_value = f"""
    RESPONSE:
    {ansjson.get('answer', '')}

    SOURCES:
    {ansjson.get('sources', '')}
    """

        self.response_content.configure(text=response_value)

    # ------------------------------------------------------------------ #
    # Config persistence
    # ------------------------------------------------------------------ #
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

    def _on_closing(self) -> None:
        print("Encerrando aplicativo...")
        save_config(
            root_model_path=self.entry_models_folder.get(),
            previous_question=self.question.get(),
            documents=self.files,
            language=self.language_selector.get(),
            model_query=self.model_selector_query.get(),
            model_reason=self.model_selector_reasoning.get())
        self.destroy()
