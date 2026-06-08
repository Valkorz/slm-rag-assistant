import tkinter as tk
import customtkinter as ctk
import asyncio 
from PIL import Image
from tkinter import filedialog
from pathlib import Path
# from src.model.model_manager import ModelManager
from src.config_loader import get_config, save_config
from src.assistant_request_socket import AssistantRequestSocket
import threading
import json
from src.dialog.model_class_initialize import ModelInitializeDialog
from src.dialog.models_warning import ModelsWarningDialog

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

files = []
downloaded_models = ["None"]
model = None
initialize_dialog = None
response = ""
selected_models_folder = ""

config_json = get_config()

#start TCP socket for receiving requests oustide the UI
_event_loop = asyncio.new_event_loop()
def _start_asyncio_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

_asyncio_thread = threading.Thread(target=_start_asyncio_loop, args=(_event_loop,), daemon=True)
_asyncio_thread.start()
tcp_socket = AssistantRequestSocket(port=8008)
tcp_socket.set_event_loop(_event_loop)

def on_language_changed(choice: str) -> None:
    if model is not None:
        threading.Thread(target=lambda: model.set_language(choice), daemon=True).start()

def on_host_toggled():
    hosting_port.delete(0,"end")
    hosting_address.delete(0,"end")
    if switch_tcp_toggle.get() == 1:
        hosting_port.insert(0, tcp_socket.port)
        hosting_address.insert(0, tcp_socket.host)

    tcp_socket.toggle_sync(state=switch_tcp_toggle.get(), tcp_callback=_tcp_request_handler)

def _tcp_request_handler(message: str) -> str:
    global model
    try:
        if model is None:
            from src.model import Model
            model = Model(query_count=5,
                            lang=language_selector.get(),
                            query_model=model_selector_query.get(),
                            reason_model=model_selector_reasoning.get(),
                            mode=mode_selector.get().lower())
        else:
            model.set_query_model(model_selector_query.get())
            model.set_resoning_model(model_selector_reasoning.get())
            model.set_language(language_selector.get())
            model.set_mode(mode_selector.get().lower())

        data = tcp_socket.parse_response(message)
        user_question = data.get("question", "").strip()
        if not user_question:
            return '{"error": "Missing required field: question"}'

        root_window.after(0, lambda: question.delete(0, "end"))
        root_window.after(0, lambda: question.insert(0, user_question))

        model.model_manager.set_models_root_path(entry_models_folder.get())

        ingest_files = _get_pdf_ingest_files()
        if ingest_files:
            model.addPdfs(ingest_files)

        answer = model.prompt(user_question=user_question)
        root_window.after(0, lambda: _finish_run(answer=answer))
        return answer if isinstance(answer, str) else json.dumps(answer)
    except ValueError as exc:
        return f'{{"error": "{str(exc)}"}}'
    except Exception as exc:
        return f'{{"error": "{str(exc)}"}}'

# Lazy initialization for model to avoid long loading times for window
def initializeModel():
    from src.model import Model
    global model, downloaded_models
    try:
        model = Model(query_count=5)
        model.model_manager.set_models_root_path(root_path=selected_models_folder)
        downloaded_models = get_downloaded_models()
        root_window.after(0, _on_model_ready)
    except Exception as exc:
        root_window.after(0, lambda error_message=str(exc): _on_model_error(error_message))

def _on_model_ready() -> None:
    button_prompt.configure(state="normal")
    model_selector_query.configure(values=downloaded_models)
    model_selector_reasoning.configure(values=downloaded_models)
    if initialize_dialog is not None:
        initialize_dialog.close("Model loaded")

def _on_model_error(error_message: str) -> None:
    button_prompt.configure(state="disabled")
    if initialize_dialog is not None:
        initialize_dialog.fail(f"Model load failed: {error_message}")

# Model selection
def model_select_callback(choice, option_menu : ctk.CTkOptionMenu):
    if not choice:
        pass

    downloaded_models = get_downloaded_models()
    if downloaded_models.__contains__(str(choice)):
        option_menu.configure(fg_color="#9da7c7", hover_color="#9da7c7")
    else: 
        option_menu.configure(fg_color="#2563eb", hover_color="#1d4ed8")
    pass

def model_download(model_name : str):
    from src.dialog.model_download import ModelDownloadDialog
    dialog = ModelDownloadDialog(root_window, model.model_manager, model_name)
    dialog.pack()
    pass

def _apply_models_folder(path: str) -> None:
    entry_models_folder.delete(0, "end")
    entry_models_folder.insert(0, path)
    model.model_manager.set_models_root_path(path)
    new_models = model.model_manager.list_downloaded()
    if not new_models:
        new_models = [" "]
    model_selector_query.configure(values=new_models)
    model_selector_reasoning.configure(values=new_models)
    model_selector_query.set(new_models[0])
    model_selector_reasoning.set(new_models[0])

def select_models_folder() -> None:
    selected = filedialog.askdirectory(
        title="Select models root folder"
    )

    if not selected:
        return

    gguf_files = list(Path(selected).glob("*.gguf"))
    if not gguf_files:
        ModelsWarningDialog(root_window, on_folder_selected=_apply_models_folder)
        return

    _apply_models_folder(selected)

def get_downloaded_models() -> list[str]:
    print(f"models folder: {selected_models_folder}")
    model_list = model.model_manager.list_downloaded()
    if not model_list or len(model_list) == 0:
        model_list = [" "]
        root_window.after(0, lambda: ModelsWarningDialog(root_window, on_folder_selected=_apply_models_folder))

    return model_list

def select_pdf() -> None:
    selected = filedialog.askopenfilename(
        title="Select a PDF file",
        filetypes=[("PDF files", "*.pdf")],
    )
    if selected:
        name = selected.split('/')[-1]
        files.append({
            'name': name,
            'path': selected,
            'metadata': ""
        })
        update_files_list()

def _normalize_pdf_file(file_entry: dict) -> dict:
    if isinstance(file_entry, str):
        return {
            'name': file_entry.split('/')[-1],
            'path': file_entry,
            'metadata': ''
        }

    return {
        'name': file_entry.get('name', ''),
        'path': file_entry.get('path', ''),
        'metadata': file_entry.get('metadata', '') or ''
    }

def _sync_pdf_metadata(file_entry: dict, entry_widget: ctk.CTkEntry) -> None:
    metadata = entry_widget.get().strip()
    if len(metadata) > 15:
        metadata = metadata[:15]
        entry_widget.delete(0, "end")
        entry_widget.insert(0, metadata)

    file_entry['metadata'] = metadata

def _get_pdf_ingest_files() -> list[dict]:
    ingest_files = []
    invalid_files = []

    for file_entry in files:
        normalized = _normalize_pdf_file(file_entry)
        metadata = normalized['metadata'].strip()

        if metadata and not 5 <= len(metadata) <= 15:
            invalid_files.append(normalized['name'])
            continue

        if metadata:
            normalized['metadata'] = metadata
        else:
            normalized.pop('metadata', None)

        ingest_files.append(normalized)

    if invalid_files:
        raise ValueError(
            "Metadata must be 5-15 characters for: " + ", ".join(invalid_files)
        )

    return ingest_files
            
def update_files_list():
    for widget in files_list.winfo_children():
        widget.destroy()

    raw_img = Image.open("images/pdf.png") 
    pdf_image = ctk.CTkImage(light_image=raw_img, size=(20, 20))
    
    for f in files:
        file_frame = ctk.CTkFrame(files_list, fg_color="transparent")
        file_frame.pack(fill="x", padx=10, pady=5)
        
        icon_label = ctk.CTkLabel(file_frame, image=pdf_image, text="")
        icon_label.pack(side="left", padx=(0, 10))
        
        name_label = ctk.CTkLabel(file_frame, text=f['name'], text_color="#e5e7eb")
        name_label.pack(side="left")

        metadata_entry = ctk.CTkEntry(
            file_frame,
            width=120,
            height=30,
            placeholder_text="metadata",
            fg_color="#0f141b",
            border_color="#263242",
            text_color="#e5e7eb",
        )
        metadata_entry.insert(0, f.get('metadata', ''))
        metadata_entry.bind(
            "<KeyRelease>",
            lambda event, file_entry=f, entry_widget=metadata_entry: _sync_pdf_metadata(file_entry, entry_widget)
        )
        metadata_entry.pack(side="right", padx=(8, 0))

        remove_btn = ctk.CTkButton(file_frame, text="X", 
                       text_color="#e5e7eb", 
                       fg_color="#990c32", 
                       width=32,
                       height=32,
                       command=lambda file=f: _remove_and_reload(file))
        remove_btn.pack(side="right")

def _remove_and_reload(file):
    files.remove(file)
    update_files_list()

def _finish_run(answer = "", error: str = "") -> None:
    loading_bar.stop()
    loading_bar.grid_remove()
    loading_status.configure(text="")
    button_prompt.configure(state="normal", text="Run")
    if error:
        response_content.configure(text=f"Run failed: {error}")
        print(f"Run failed: {error}")
        return

    if isinstance(answer, dict):
        ansjson = answer
    else:
        try:
            ansjson = json.loads(answer)
        except json.JSONDecodeError:
            response_content.configure(text=str(answer))
            return

    response_value = f"""
    RESPONSE:
    {ansjson.get('answer', '')}
    
    SOURCES:
    {ansjson.get('sources', '')}
    """

    response_content.configure(text=response_value)


def run_prompt() -> None:
    user_question = question.get().strip()
    if not user_question:
        response_content.configure(text="Please type a question before running.")
        return

    button_prompt.configure(state="disabled", text="Running...")
    loading_status.configure(text="Loading model...")
    loading_bar.grid(row=2, column=0, columnspan=3, sticky="ew", padx=20, pady=(8, 0))
    loading_bar.start()


    model.model_manager.set_models_root_path(entry_models_folder.get())
    def worker() -> None:
        global model
        try:
            if model is None:
                from src.model import Model
                model = Model(query_count=5,
                              lang=language_selector.get(),
                              query_model=model_selector_query.get(),
                              reason_model=model_selector_reasoning.get(),
                              mode=mode_selector.get().lower())
            else:
                model.set_query_model(model_selector_query.get())
                model.set_resoning_model(model_selector_reasoning.get())
                model.set_language(language_selector.get())
                model.set_mode(mode_selector.get().lower())

            ingest_files = _get_pdf_ingest_files()
            if ingest_files:
                model.addPdfs(ingest_files)

            root_window.after(0, lambda: loading_status.configure(text="Generating response..."))
            answer = model.prompt(user_question=user_question)
            root_window.after(0, lambda: _finish_run(answer=answer))
        except ValueError as exc:
            error_message = str(exc)
            root_window.after(0, lambda error_message=error_message: _finish_run(error=error_message))
        except Exception as exc:
            error_message = str(exc)
            root_window.after(0, lambda error_message=error_message: _finish_run(error=error_message))

    threading.Thread(target=worker, daemon=True).start()

root_window = ctk.CTk()
root_window.geometry("980x700")
root_window.minsize(860, 620)
root_window.title("Assistant")
root_window.configure(fg_color="#0b0d11")

root_window.grid_rowconfigure(0, weight=1)
root_window.grid_columnconfigure(0, weight=1)

def on_closing():
    print("Encerrando aplicativo...")
    save_config(
    root_model_path=entry_models_folder.get(),
    previous_question=question.get(),
    documents=files,
    language=language_selector.get(),
    model_query=model_selector_query.get(),
    model_reason=model_selector_reasoning.get())
    root_window.destroy()

page_canvas = tk.Canvas(
    root_window,
    highlightthickness=0,
    bg="#0b0d11",
)
page_canvas.grid(row=0, column=0, sticky="nsew")

page_scrollbar = ctk.CTkScrollbar(
    root_window,
    orientation="vertical",
    command=page_canvas.yview,
)
page_scrollbar.grid(row=0, column=1, sticky="ns")
page_canvas.configure(yscrollcommand=page_scrollbar.set)

main_container = ctk.CTkFrame(page_canvas, fg_color="transparent")
main_container_window = page_canvas.create_window((24, 24), window=main_container, anchor="nw")

def _update_scroll_region(_event=None):
    page_canvas.configure(scrollregion=page_canvas.bbox("all"))

def _fit_content_width(event):
    width = max(event.width - 48, 1)
    page_canvas.itemconfigure(main_container_window, width=width)

def _on_mousewheel(event):
    page_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

main_container.bind("<Configure>", _update_scroll_region)
page_canvas.bind("<Configure>", _fit_content_width)
page_canvas.bind_all("<MouseWheel>", _on_mousewheel)

main_container.grid_columnconfigure(0, weight=1)
main_container.grid_columnconfigure(1, weight=1)
main_container.grid_rowconfigure(2, weight=0)

#Heading
header_card = ctk.CTkFrame(
	main_container,
	corner_radius=18,
	fg_color="#11151c",
	border_width=1,
	border_color="#1f2937",
)
header_card.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))

label_title = ctk.CTkLabel(
	header_card,
	text="SLM RAG Assistant",
	font=("Segoe UI Semibold", 30),
	text_color="#e5e7eb",
)
label_title.pack(anchor="w", padx=20, pady=(16, 4))

#File selection
files_block = ctk.CTkFrame(
	main_container,
	corner_radius=18,
	fg_color="#11151c",
	border_width=1,
	border_color="#1f2937",
)
files_block.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 14))

label_fselect_description = ctk.CTkLabel(
	files_block,
	text="REFERENCE MATERIAL",
	font=("Segoe UI Semibold", 18),
	text_color="#bbc3d2",
)
label_fselect_description.pack(anchor="w", padx=20, pady=(16, 4))

files_list = ctk.CTkFrame(
    files_block,
    corner_radius=18,
    fg_color="#0b0e14",
    border_width=1,
    border_color="#17202c",
)
files_list.pack(fill="x", pady=5, padx=20)

button_select_pdf = ctk.CTkButton(
	files_block,
	text="Select file",
	command=select_pdf,
	corner_radius=10,
	height=36,
	fg_color="#2563eb",
	hover_color="#1d4ed8",
)
button_select_pdf.pack(anchor="w", pady=5, padx=20)

# Prompt

message_block = ctk.CTkFrame(
    main_container,
    corner_radius=18,
    fg_color="#11151c",
    border_width=1,
    border_color="#1f2937",
)
message_block.grid_columnconfigure(0, weight=1)
message_block.grid_columnconfigure(1, weight=1)
message_block.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 14))

question = ctk.CTkEntry(
    message_block,
    placeholder_text="Write your question here...",
    corner_radius=10,
    height=100,
    fg_color="#0f141b",
    border_color="#263242",
    text_color="#e5e7eb",
)
question.grid(row=1,columnspan=2, sticky="ew", padx=20, pady=5)

label_question_header = ctk.CTkLabel(
	message_block,
	text="YOUR QUESTION",
	font=("Segoe UI Semibold", 18),
	text_color="#bbc3d2",
)
label_question_header.grid(row=0,columnspan=2, sticky="ew", padx=20, pady=5)

# Actions
actions_block = ctk.CTkFrame(
    main_container,
    corner_radius=18,
    fg_color="#11151c",
    height=50,
    border_width=1,
    border_color="#1f2937",
)
actions_block.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 14))
actions_block.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="group1")
actions_block.grid_rowconfigure(0, weight=1)
actions_block.grid_rowconfigure(1, weight=1)

label_language = ctk.CTkLabel(
    actions_block,
    text="Language",
    font=("Segoe UI Semibold", 12),
    text_color="#bbc3d2",
)
label_language.grid(row=0, column=0, sticky="ew", padx=20, pady=5)

language_selector = ctk.CTkOptionMenu(
	actions_block,
	values=["EN","PTBR"],
	command=on_language_changed,
	fg_color="#18202a",
	button_color="#1f2937",
	button_hover_color="#273549",
	dropdown_fg_color="#11151c",
	corner_radius=10,
	height=38
)
language_selector.grid(row=1, column=0, sticky="ew", padx=20, pady=5)

label_query_model = ctk.CTkLabel(
    actions_block,
    text="Query Model",
    font=("Segoe UI Semibold", 12),
    text_color="#bbc3d2",
)
label_query_model.grid(row=0, column=1, sticky="ew", padx=20, pady=5)

label_reasoning_model = ctk.CTkLabel(
    actions_block,
    text="Reasoning Model",
    font=("Segoe UI Semibold", 12),
    text_color="#bbc3d2",
)
label_reasoning_model.grid(row=0, column=2, sticky="ew", padx=20, pady=5)

label_mode = ctk.CTkLabel(
    actions_block,
    text="Mode",
    font=("Segoe UI Semibold", 12),
    text_color="#bbc3d2",
)
label_mode.grid(row=0, column=3, sticky="ew", padx=20, pady=5)

model_selector_query = ctk.CTkOptionMenu(
    actions_block,
    values=downloaded_models,
    fg_color="#18202a",
    button_color="#1f2937",
    button_hover_color="#273549",
    dropdown_fg_color="#11151c",
    corner_radius=10,
    height=38
)
model_selector_query.grid(row=1, column=1, sticky="ew", padx=20, pady=5)

model_selector_reasoning = ctk.CTkOptionMenu(
    actions_block,
    values=downloaded_models,
    fg_color="#18202a",
    button_color="#1f2937",
    button_hover_color="#273549",
    dropdown_fg_color="#11151c",
    corner_radius=10,
    height=38
)
model_selector_reasoning.grid(row=1, column=2, sticky="ew", padx=20, pady=5)

mode_selector = ctk.CTkOptionMenu(
    actions_block,
    values=["Document", "Financial"],
    fg_color="#18202a",
    button_color="#1f2937",
    button_hover_color="#273549",
    dropdown_fg_color="#11151c",
    corner_radius=10,
    height=38,
)
mode_selector.grid(row=1, column=3, sticky="ew", padx=20, pady=5)

button_prompt = ctk.CTkButton(
	actions_block,
	text="Run",
    command=run_prompt,
	corner_radius=10,
	height=36,
	fg_color="#2563eb",
	hover_color="#1d4ed8",
    state="disabled",
)
button_prompt.grid(row=2, column=3, sticky="ew", pady=5)

entry_models_folder = ctk.CTkEntry(
    actions_block,
    placeholder_text="C:/Path/To/Models/Folder/*UGGF",
    corner_radius=10,
    height=36,
    fg_color="#0f141b",
    border_color="#263242",
    text_color="#e5e7eb"
)
entry_models_folder.grid(row=3,column=0,columnspan=3,sticky="ew",pady=5,padx=5)

button_select_models_folder = ctk.CTkButton(
	actions_block,
	text="Select models root folder",
    command=select_models_folder,
	corner_radius=10,
	height=36,
	fg_color="#2563eb",
	hover_color="#1d4ed8",
)
button_select_models_folder.grid(row=3, column=3, sticky="ew", pady=5,padx=5)   

loading_status = ctk.CTkLabel(
    actions_block,
    text="",
    text_color="#9ca3af",
    anchor="w",
)
# loading_status.grid(row=2, column=0, columnspan=2, sticky="ew", padx=20, pady=(6, 0))
# loading_status.configure(text="Loading model...")

loading_bar = ctk.CTkProgressBar(
    actions_block,
    mode="indeterminate",
    progress_color="#1d4ed8",
)
# loading_bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20, pady=(8, 0))
# loading_bar.start()

hosting_address = ctk.CTkEntry(
    actions_block,
    placeholder_text="0.0.0.0",
    corner_radius=10,
    height=36,
    fg_color="#0f141b",
    border_color="#263242",
    text_color="#e5e7eb",
    # state="readonly"
)
hosting_address.grid(row=4, column=0, columnspan=2, sticky="ew", pady=5,padx=5)   

hosting_port = ctk.CTkEntry(
    actions_block,
    placeholder_text="0000",
    corner_radius=10,
    height=36,
    fg_color="#0f141b",
    border_color="#263242",
    text_color="#e5e7eb",
    # state="readonly"
)
hosting_port.grid(row=4, column=2, sticky="ew", pady=5,padx=5)   

switch_tcp_toggle = ctk.CTkSwitch(
    actions_block,
    text="TCP",
    command=on_host_toggled
)
switch_tcp_toggle.grid(row=4, column=3, sticky="ew", pady=5,padx=5)   

# Response

response_block = ctk.CTkFrame(
    message_block,
    corner_radius=10,
    fg_color="#0f141b",
    border_color="#263242",
    border_width=1
)
response_block.grid(row=3,columnspan=2, sticky="ew", padx=20, pady=5)
response_block.grid_columnconfigure(0, weight=1)

response_content = ctk.CTkLabel(
	response_block,
	text=response,
	font=("Segoe UI Semibold", 15),
	text_color="#e5e7eb",
    justify="left",
    anchor="nw",
)
response_content.grid(row=0, column=0, sticky="ew", padx=12, pady=12)

def _sync_response_wrap(event):
    wrap = max(event.width - 24, 120)
    response_content.configure(wraplength=wrap)

response_block.bind("<Configure>", _sync_response_wrap)

label_response_header = ctk.CTkLabel(
	message_block,
	text="RESPONSE",
	font=("Segoe UI Semibold", 18),
	text_color="#bbc3d2",
)
label_response_header.grid(row=2, columnspan=2, sticky="ew", padx=20, pady=5)

# Initialize files with data folder contents
for file in list(Path("./data/").glob("*.pdf")):
    fstr = str(file.as_posix())
    name = fstr.split('/')[-1]
    files.append({
        'name': name,
        'path': fstr,
        'metadata': ""
    })
    update_files_list()

initialize_dialog = ModelInitializeDialog(root_window)
root_window.after(0, lambda: threading.Thread(target=initializeModel, daemon=True).start())

# Load config
if config_json:
    selected_models_folder = config_json['root_model_path']
    entry_models_folder.delete(0,"end")
    entry_models_folder.insert(0, config_json['root_model_path'])
    files = [_normalize_pdf_file(file_entry) for file_entry in config_json['documents']]
    language_selector.set(config_json['language'])
    model_selector_query.set(config_json['model_query'])
    model_selector_reasoning.set(config_json['model_reason'])
    update_files_list()

# Initialize window
root_window.protocol("WM_DELETE_WINDOW", on_closing)
root_window.mainloop()


