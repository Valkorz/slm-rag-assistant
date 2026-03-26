import tkinter as tk
import customtkinter as ctk

root_window = tk.Tk()
root_window.geometry("720x720")
root_window.title("Assistant")

label_title = ctk.CTkLabel(root_window, text="Assistente de Dedutíveis IRPF 2026", font=("arial bold", 30), text_color="black")
label_title.pack(pady=10)

label_data = ctk.CTkLabel(root_window, text="Dados:", font=("arial", 15), text_color="black")
label_data.pack(pady=5)

# DATA FIELDS

data_canvas = ctk.CTkCanvas(root_window)
data_canvas.pack(pady=5)

label_wage = ctk.CTkLabel(data_canvas, text="Salário", font=("arial", 12), text_color="black")
label_wage.pack(pady=2)

data_wage = ctk.CTkEntry(data_canvas, corner_radius=2, placeholder_text="R$ ---")
data_wage.pack(pady=2)


root_window.mainloop()