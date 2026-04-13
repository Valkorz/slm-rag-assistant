import tkinter as tk
import customtkinter as ctk
from PIL import Image
from tkinter import filedialog
import threading

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

files = []
model = None
response = ""

# Update original select_pdf function
def select_pdf() -> None:
    selected = filedialog.askopenfilename(
        title="Select a PDF file",
        filetypes=[("PDF files", "*.pdf")],
    )
    if selected:
        name = selected.split('/')[-1]
        files.append({
            'name': name,
            'path': selected
        })
        update_files_list()
            
def update_files_list():
    if len(files) == 0:
        pass
    
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

def _finish_run(answer: str = "", error: str = "") -> None:
    loading_bar.stop()
    loading_bar.grid_remove()
    loading_status.configure(text="")
    button_prompt.configure(state="normal", text="Run")
    if error:
        response_content.configure(text=f"Run failed: {error}")
        print(f"Run failed: {error}")
        return
    print(answer)
    response_content.configure(text=answer)


def run_prompt() -> None:
    user_question = question.get().strip()
    if not user_question:
        response_content.configure(text="Please type a question before running.")
        return

    button_prompt.configure(state="disabled", text="Running...")
    loading_status.configure(text="Loading model...")
    loading_bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20, pady=(8, 0))
    loading_bar.start()

    def worker() -> None:
        global model
        try:
            if model is None:
                from src.model import Model
                model = Model(query_count=5, 
                              lang=language_selector.get(), 
                              query_model=model_selector_query.get(),
                              reason_model=model_selector_reasoning.get())

            if files:
                model.addPdfs(files)

            root_window.after(0, lambda: loading_status.configure(text="Generating response..."))
            answer = model.prompt(user_question=user_question)
            root_window.after(0, lambda: _finish_run(answer=answer))
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
question.grid(row=1, column=0, sticky="ew", padx=20, pady=5)

label_question_header = ctk.CTkLabel(
	message_block,
	text="YOUR QUESTION",
	font=("Segoe UI Semibold", 18),
	text_color="#bbc3d2",
)
label_question_header.grid(row=0, column=0, sticky="ew", padx=20, pady=5)

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
actions_block.grid_columnconfigure(0, weight=1)
actions_block.grid_columnconfigure(1, weight=1)

language_selector = ctk.CTkOptionMenu(
	actions_block,
	values=["EN","PTBR"],
	fg_color="#18202a",
	button_color="#1f2937",
	button_hover_color="#273549",
	dropdown_fg_color="#11151c",
	corner_radius=10,
	height=38
)
language_selector.grid(row=0, column=0, sticky="ew", padx=20, pady=5)

model_selector_query = ctk.CTkOptionMenu(
	actions_block,
	values=["deepseek-r1-distill-qwen-1.5b", "google/gemma-4-e2b", "local_model"],
	fg_color="#18202a",
	button_color="#1f2937",
	button_hover_color="#273549",
	dropdown_fg_color="#11151c",
	corner_radius=10,
	height=38
)
model_selector_query.grid(row=0, column=1, sticky="ew", padx=20, pady=5)

model_selector_reasoning = ctk.CTkOptionMenu(
	actions_block,
	values=["meta-llama-3.1-8b-instruct", "google/gemma-4-e4b", "local_model"],
	fg_color="#18202a",
	button_color="#1f2937",
	button_hover_color="#273549",
	dropdown_fg_color="#11151c",
	corner_radius=10,
	height=38
)
model_selector_reasoning.grid(row=0, column=2, sticky="ew", padx=20, pady=5)

button_prompt = ctk.CTkButton(
	actions_block,
	text="Run",
    command=run_prompt,
	corner_radius=10,
	height=36,
	fg_color="#2563eb",
	hover_color="#1d4ed8",
)
button_prompt.grid(row=0, column=3, sticky="ew", pady=5)

loading_status = ctk.CTkLabel(
    actions_block,
    text="",
    text_color="#9ca3af",
    anchor="w",
)
loading_status.grid(row=2, column=0, columnspan=2, sticky="ew", padx=20, pady=(6, 0))

loading_bar = ctk.CTkProgressBar(
    actions_block,
    mode="indeterminate",
    progress_color="#1d4ed8",
)
loading_bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20, pady=(8, 0))
loading_bar.grid_remove()

# Response

response_block = ctk.CTkFrame(
    message_block,
    corner_radius=10,
    fg_color="#0f141b",
    border_color="#263242",
    border_width=1
)
response_block.grid(row=1, column=1, sticky="ew", padx=20, pady=5)
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
label_response_header.grid(row=0, column=1, sticky="ew", padx=20, pady=5)

root_window.mainloop()

