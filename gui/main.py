import tkinter as tk
from tkinter import ttk, scrolledtext, Menu, messagebox, filedialog
import threading
from datetime import datetime
from typing import Optional

import sv_ttk

from core.ollama_client import OllamaClient
from utils.config import Config


class OllamaGUI:
    """Main GUI application for Ollama chat client."""

    COLORS = {
        "light": {
            "bg": "#f8f9fa",
            "text": "#212529",
            "input_bg": "#ffffff",
            "user_msg": "#e7f5ff",
            "assistant_msg": "#f8f9fa",
            "system_msg": "#fff9db",
        },
        "dark": {
            "bg": "#212529",
            "text": "#f8f9fa",
            "input_bg": "#343a40",
            "user_msg": "#1864ab",
            "assistant_msg": "#343a40",
            "system_msg": "#5c3e08",
        },
    }

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Simple Ollama GUI Client")
        self.root.geometry("900x700")
        self.root.minsize(700, 500)

        self.config = Config()
        self.client = OllamaClient(
            base_url=self.config.get_base_url(),
            model=self.config.get_model(),
        )
        self.client.system_prompt = self.config.get_system_prompt()
        self.client.parameters = self.config.get_params()
        self.client.save_dir = "chat_history"

        self.theme = self.config.get_theme()
        self.current_file_path: Optional[str] = None

        self._setup_menu()
        self._create_widgets()
        self._apply_theme()
        self._setup_context_menu()
        self._check_connection()

        self.display_system_message("Welcome to Simple Ollama GUI Client!")
        self.display_system_message(f"Current model: {self.client.model}")

        threading.Thread(target=self._load_models, daemon=True).start()

    def _setup_menu(self) -> None:
        self.menubar = Menu(self.root)

        file_menu = Menu(self.menubar, tearoff=0)
        file_menu.add_command(label="New Chat", command=self._clear_chat)
        file_menu.add_command(label="Open Chat", command=self._load_chat)
        file_menu.add_command(label="Save Chat", command=self._save_chat)
        file_menu.add_command(label="Save Chat As...", command=lambda: self._save_chat(save_as=True))
        file_menu.add_command(label="Rename Current Chat", command=self._rename_chat)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        self.menubar.add_cascade(label="File", menu=file_menu)

        edit_menu = Menu(self.menubar, tearoff=0)
        edit_menu.add_command(label="Copy Selected", command=self._copy_selected)
        edit_menu.add_command(label="Clear Chat", command=self._clear_chat)
        self.menubar.add_cascade(label="Edit", menu=edit_menu)

        settings_menu = Menu(self.menubar, tearoff=0)
        settings_menu.add_command(label="Toggle Theme", command=self._toggle_theme)
        settings_menu.add_command(label="Connection Settings", command=self._show_connection_settings)
        settings_menu.add_command(label="Model Parameters", command=self._show_parameters)
        settings_menu.add_command(label="System Prompt", command=self._show_system_prompt)
        self.menubar.add_cascade(label="Settings", menu=settings_menu)

        help_menu = Menu(self.menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        self.menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=self.menubar)

    def _create_widgets(self) -> None:
        padding = {"padx": 12, "pady": 12}
        small_padding = {"padx": 6, "pady": 6}

        self.main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_paned.pack(fill=tk.BOTH, expand=True, **padding)

        self.left_frame = ttk.Frame(self.main_paned)
        self.main_paned.add(self.left_frame, weight=3)

        self.conversation_frame = ttk.Frame(self.left_frame)
        self.conversation_frame.pack(fill=tk.BOTH, expand=True)

        self.conversation_display = scrolledtext.ScrolledText(
            self.conversation_frame,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            selectbackground="#0078d7",
            selectforeground="white",
        )
        self.conversation_display.pack(fill=tk.BOTH, expand=True)
        self.conversation_display.config(state=tk.DISABLED)

        self.status_frame = ttk.Frame(self.left_frame)
        self.status_frame.pack(fill=tk.X, **small_padding)

        self.status_var = tk.StringVar(value="Disconnected")
        ttk.Label(self.status_frame, text="Status:", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(0, 5))
        self.status_indicator = ttk.Label(
            self.status_frame, textvariable=self.status_var, font=("Segoe UI", 9, "bold")
        )
        self.status_indicator.pack(side=tk.LEFT)

        self.model_status = ttk.Label(
            self.status_frame, text=f"Model: {self.client.model}", font=("Segoe UI", 9, "bold")
        )
        self.model_status.pack(side=tk.RIGHT)

        self.input_frame = ttk.Frame(self.left_frame)
        self.input_frame.pack(fill=tk.X, **padding)

        self.user_input = scrolledtext.ScrolledText(
            self.input_frame, wrap=tk.WORD, height=4, font=("Segoe UI", 10)
        )
        self.user_input.pack(fill=tk.X, side=tk.LEFT, expand=True, padx=(0, 8))
        self.user_input.bind("<Return>", self._send_message)

        self.send_button = ttk.Button(
            self.input_frame,
            text="Send",
            command=self._send_message,
            style="Accent.TButton",
        )
        self.send_button.pack(side=tk.RIGHT)

        self.right_frame = ttk.Frame(self.main_paned)
        self.main_paned.add(self.right_frame, weight=1)

        self.model_frame = ttk.LabelFrame(self.right_frame, text="Model Selection")
        self.model_frame.pack(fill=tk.X, **small_padding)

        self.model_var = tk.StringVar(value=self.client.model)
        self.model_dropdown = ttk.Combobox(
            self.model_frame, textvariable=self.model_var, font=("Segoe UI", 9)
        )
        self.model_dropdown.pack(fill=tk.X, **small_padding)
        self.model_dropdown["values"] = [self.client.model]
        self.model_dropdown.bind("<<ComboboxSelected>>", self._change_model)

        ttk.Button(
            self.model_frame,
            text="Refresh Models",
            command=self._load_models,
            style="Accent.TButton",
        ).pack(fill=tk.X, **small_padding)

        self.params_frame = ttk.LabelFrame(self.right_frame, text="Parameters")
        self.params_frame.pack(fill=tk.X, **small_padding)

        ttk.Label(self.params_frame, text="Temperature:", font=("Segoe UI", 9)).pack(anchor=tk.W, padx=8, pady=(8, 0))
        self.temp_var = tk.DoubleVar(value=self.client.parameters.get("temperature", 0.7))
        self.temp_scale = ttk.Scale(
            self.params_frame,
            from_=0.0,
            to=2.0,
            variable=self.temp_var,
            orient=tk.HORIZONTAL,
            command=lambda v: self._update_parameter("temperature"),
        )
        self.temp_scale.pack(fill=tk.X, **small_padding)
        self.temp_label = ttk.Label(
            self.params_frame, text=f"{self.temp_var.get():.2f}", font=("Segoe UI", 9)
        )
        self.temp_label.pack(anchor=tk.W, padx=8)

        ttk.Label(self.params_frame, text="Top-p:", font=("Segoe UI", 9)).pack(anchor=tk.W, padx=8, pady=(8, 0))
        self.top_p_var = tk.DoubleVar(value=self.client.parameters.get("top_p", 0.9))
        self.top_p_scale = ttk.Scale(
            self.params_frame,
            from_=0.0,
            to=1.0,
            variable=self.top_p_var,
            orient=tk.HORIZONTAL,
            command=lambda v: self._update_parameter("top_p"),
        )
        self.top_p_scale.pack(fill=tk.X, **small_padding)
        self.top_p_label = ttk.Label(
            self.params_frame, text=f"{self.top_p_var.get():.2f}", font=("Segoe UI", 9)
        )
        self.top_p_label.pack(anchor=tk.W, padx=8)

        self.system_frame = ttk.LabelFrame(self.right_frame, text="System Prompt")
        self.system_frame.pack(fill=tk.X, **small_padding)

        self.system_prompt_entry = scrolledtext.ScrolledText(
            self.system_frame, wrap=tk.WORD, height=3, font=("Segoe UI", 9)
        )
        self.system_prompt_entry.pack(fill=tk.X, **small_padding)
        self.system_prompt_entry.insert("1.0", self.client.system_prompt)

        ttk.Button(
            self.system_frame,
            text="Apply System Prompt",
            command=self._apply_system_prompt,
            style="Accent.TButton",
        ).pack(fill=tk.X, **small_padding)

        self.commands_frame = ttk.LabelFrame(self.right_frame, text="Commands")
        self.commands_frame.pack(fill=tk.X, **small_padding)

        for text, cmd in [
            ("Save Chat", self._save_chat),
            ("Load Chat", self._load_chat),
            ("Clear Chat", self._clear_chat),
            ("Toggle Theme", self._toggle_theme),
        ]:
            ttk.Button(
                self.commands_frame,
                text=text,
                command=cmd,
                style="Accent.TButton",
            ).pack(fill=tk.X, **small_padding)

    def _apply_theme(self) -> None:
        sv_ttk.set_theme(self.theme)
        colors = self.COLORS[self.theme]

        self.conversation_display.config(
            background=colors["bg"],
            foreground=colors["text"],
            selectbackground="#0078d7" if self.theme == "light" else "#265f99",
            selectforeground="white",
        )
        self.user_input.config(
            background=colors["input_bg"],
            foreground=colors["text"],
            selectbackground="#0078d7" if self.theme == "light" else "#265f99",
            selectforeground="white",
        )
        self.system_prompt_entry.config(
            background=colors["input_bg"],
            foreground=colors["text"],
            selectbackground="#0078d7" if self.theme == "light" else "#265f99",
            selectforeground="white",
        )

        self.conversation_display.tag_configure(
            "user_message",
            background=colors["user_msg"],
            lmargin1=20,
            lmargin2=20,
            rmargin=20,
        )
        self.conversation_display.tag_configure(
            "assistant_message",
            background=colors["assistant_msg"],
            lmargin1=20,
            lmargin2=20,
            rmargin=20,
        )
        self.conversation_display.tag_configure(
            "system_message",
            background=colors["system_msg"],
            lmargin1=20,
            lmargin2=20,
            rmargin=20,
        )

        fg = "#28a745" if self.status_var.get() == "Connected" else "#dc3545"
        self.status_indicator.config(foreground=fg)

    def _toggle_theme(self) -> None:
        self.theme = "dark" if self.theme == "light" else "light"
        self.config.set_theme(self.theme)
        self.config.save()
        self._apply_theme()

    def _update_parameter(self, param: str) -> None:
        if param == "temperature":
            value = self.temp_var.get()
            self.temp_label.config(text=f"{value:.2f}")
            self.client.set_parameter(param, value)
        elif param == "top_p":
            value = self.top_p_var.get()
            self.top_p_label.config(text=f"{value:.2f}")
            self.client.set_parameter(param, value)

    def _apply_system_prompt(self) -> None:
        prompt = self.system_prompt_entry.get("1.0", tk.END).strip()
        self.client.set_system_prompt(prompt)
        self.display_system_message("System prompt updated")
        self.config.set_system_prompt(prompt)
        self.config.save()

    def _load_models(self) -> None:
        models = self.client.get_models()
        if models:
            self.model_dropdown["values"] = models
            self.display_system_message(f"Loaded {len(models)} models")

    def _check_connection(self) -> None:
        def do_check():
            connected = self.client.check_connection()
            self.status_var.set("Connected" if connected else "Disconnected")
            fg = "green" if connected else "red"
            self.status_indicator.config(foreground=fg)

        threading.Thread(target=do_check, daemon=True).start()

    def _show_connection_settings(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Connection Settings")
        dialog.geometry("400x150")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Ollama API URL:").grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)

        url_var = tk.StringVar(value=self.client.base_url)
        url_entry = ttk.Entry(dialog, textvariable=url_var, width=30)
        url_entry.grid(row=0, column=1, padx=10, pady=10)

        def save_settings():
            new_url = url_var.get().strip()
            if new_url:
                self.client.base_url = new_url
                self.config.set_base_url(new_url)
                self.config.save()
                self._check_connection()
                self.display_system_message(f"API URL changed to {new_url}")
            dialog.destroy()

        ttk.Button(
            dialog,
            text="Test Connection",
            command=lambda: messagebox.showinfo(
                "Connection Test",
                "Connected" if self.client.check_connection() else "Failed to connect",
            ),
        ).grid(row=1, column=0, padx=10, pady=10)

        ttk.Button(dialog, text="Save", command=save_settings).grid(row=1, column=1, padx=10, pady=10)

    def _show_parameters(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Model Parameters")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()

        row = 0
        param_vars = {}

        for param, value in self.client.parameters.items():
            ttk.Label(dialog, text=f"{param}:").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
            param_vars[param] = tk.StringVar(value=str(value))
            ttk.Entry(dialog, textvariable=param_vars[param], width=10).grid(row=row, column=1, padx=10, pady=5)
            row += 1

        def save_params():
            try:
                for param, var in param_vars.items():
                    value = float(var.get())
                    self.client.set_parameter(param, value)
                self.temp_var.set(self.client.parameters.get("temperature", 0.7))
                self.top_p_var.set(self.client.parameters.get("top_p", 0.9))
                self.temp_label.config(text=f"{self.temp_var.get():.2f}")
                self.top_p_label.config(text=f"{self.top_p_var.get():.2f}")
                self.display_system_message("Parameters updated")
                self.config.save()
                dialog.destroy()
            except ValueError as e:
                messagebox.showerror("Invalid Value", f"Invalid value: {e}")

        ttk.Button(dialog, text="Save", command=save_params).grid(row=row, column=0, columnspan=2, padx=10, pady=10)

    def _show_system_prompt(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("System Prompt")
        dialog.geometry("600x400")
        dialog.transient(self.root)
        dialog.grab_set()

        prompt_text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD, font=("Segoe UI", 10))
        prompt_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        prompt_text.insert("1.0", self.client.system_prompt)

        def save_prompt() -> None:
            prompt = prompt_text.get("1.0", tk.END).strip()
            self.client.set_system_prompt(prompt)
            self.system_prompt_entry.delete("1.0", tk.END)
            self.system_prompt_entry.insert("1.0", prompt)
            self.config.set_system_prompt(prompt)
            self.config.save()
            self.display_system_message("System prompt updated")
            dialog.destroy()

        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Save", command=save_prompt).pack(side=tk.RIGHT, padx=5)

    def display_system_message(self, message: str) -> None:
        self.display_message("System", message, "system_message")

    def display_message(self, sender: str, message: str, tag: Optional[str] = None) -> None:
        self.conversation_display.config(state=tk.NORMAL)

        timestamp = datetime.now().strftime("%H:%M:%S")

        if sender == "User":
            self.conversation_display.insert(tk.END, f"\n[{timestamp}] ", "timestamp")
            self.conversation_display.insert(tk.END, "You", "user_header")
            self.conversation_display.insert(tk.END, "\n", "normal")
            self.conversation_display.insert(tk.END, f"{message}\n", tag)
        elif sender == "Assistant":
            self.conversation_display.insert(tk.END, f"\n[{timestamp}] ", "timestamp")
            self.conversation_display.insert(tk.END, "Assistant", "assistant_header")
            self.conversation_display.insert(tk.END, "\n", "normal")
            self.conversation_display.insert(tk.END, f"{message}\n", tag)
        else:
            self.conversation_display.insert(tk.END, f"\n[{timestamp}] ", "timestamp")
            self.conversation_display.insert(tk.END, "System", "system_header")
            self.conversation_display.insert(tk.END, f": {message}\n", tag)

        self.conversation_display.tag_config("timestamp", foreground="#6c757d", font=("Segoe UI", 8))
        self.conversation_display.tag_config("user_header", foreground="#0366d6", font=("Segoe UI", 10, "bold"))
        self.conversation_display.tag_config("assistant_header", foreground="#28a745", font=("Segoe UI", 10, "bold"))
        self.conversation_display.tag_config("system_header", foreground="#5f4b8b", font=("Segoe UI", 10, "bold"))

        self.conversation_display.see(tk.END)
        self.conversation_display.config(state=tk.DISABLED)

    def _send_message(self, event=None) -> str:
        user_message = self.user_input.get("1.0", tk.END).strip()
        if not user_message:
            return "break"

        self.display_message("User", user_message, "user_message")
        self.user_input.delete("1.0", tk.END)

        self.root.config(cursor="watch")
        self.send_button.config(state=tk.DISABLED)
        self.root.update()

        timestamp = datetime.now().strftime("%H:%M:%S")
        self.conversation_display.config(state=tk.NORMAL)
        self.conversation_display.insert(tk.END, f"\n[{timestamp}] Assistant:\n", "assistant_header")
        self.conversation_display.insert(tk.END, "Thinking...", "typing_indicator")
        self.conversation_display.see(tk.END)
        self.conversation_display.config(state=tk.DISABLED)

        def stream_handler(text_chunk: str) -> None:
            self.conversation_display.config(state=tk.NORMAL)
            if "Thinking..." in self.conversation_display.get("1.0", tk.END):
                typing_pos = self.conversation_display.search("Thinking...", "1.0", tk.END)
                if typing_pos:
                    self.conversation_display.delete(typing_pos, f"{typing_pos}+10c")
            self.conversation_display.insert(tk.END, text_chunk, "assistant_message")
            self.conversation_display.see(tk.END)
            self.conversation_display.config(state=tk.DISABLED)
            self.root.update()

        def process_message() -> None:
            try:
                self.client.chat(user_message, stream_handler)
                self.model_status.config(text=f"Model: {self.client.model}")
            except Exception as e:
                self.conversation_display.config(state=tk.NORMAL)
                typing_pos = self.conversation_display.search("Thinking...", "1.0", tk.END)
                if typing_pos:
                    self.conversation_display.delete(typing_pos, f"{typing_pos}+10c")
                self.conversation_display.config(state=tk.DISABLED)
                self.display_system_message(f"Error: {str(e)}")
            finally:
                self.root.config(cursor="")
                self.send_button.config(state=tk.NORMAL)

        threading.Thread(target=process_message, daemon=True).start()
        return "break"

    def _change_model(self, event=None) -> None:
        new_model = self.model_var.get().strip()
        if new_model:
            self.client.set_model(new_model)
            self.model_status.config(text=f"Model: {new_model}")
            self.config.set_model(new_model)
            self.config.save()
            self.display_system_message(f"Model changed to {new_model}")

    def _save_chat(self, save_as: bool = False) -> None:
        if not self.client.conversation:
            messagebox.showinfo("Save Chat", "No conversation to save")
            return

        if save_as or not self.client.chat_name:
            default_name = self.client.chat_name or f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            filename = filedialog.asksaveasfilename(
                initialdir=self.client.save_dir,
                initialfile=f"{default_name}.json",
                title="Save Chat As",
                filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            )
            if not filename:
                return

            import os

            dir_path = os.path.dirname(filename)
            base_name = os.path.basename(filename)
            if base_name.lower().endswith(".json"):
                base_name = os.path.splitext(base_name)[0]

            if dir_path != self.client.save_dir and dir_path:
                if not os.path.exists(dir_path):
                    os.makedirs(dir_path)

            self.client.save_conversation(base_name)
            self.current_file_path = filename
            self.client.chat_name = base_name
            self.display_system_message(f"Conversation saved to {filename}")
        else:
            filename = f"{self.client.save_dir}/{self.client.chat_name}.json"
            self.client.save_conversation(self.client.chat_name)
            self.current_file_path = filename
            self.display_system_message(f"Conversation saved to {filename}")

    def _rename_chat(self) -> None:
        if not self.current_file_path:
            messagebox.showinfo("Rename Chat", "Please save the chat first before renaming.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Rename Chat")
        dialog.geometry("400x150")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Enter a new name for this chat:").grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)

        import os

        current_name = self.client.chat_name or os.path.basename(self.current_file_path).split(".")[0]
        name_var = tk.StringVar(value=current_name)
        name_entry = ttk.Entry(dialog, textvariable=name_var, width=30)
        name_entry.grid(row=0, column=1, padx=10, pady=10)
        name_entry.select_range(0, tk.END)
        name_entry.focus()

        def do_rename() -> None:
            new_name = name_var.get().strip()
            if new_name and new_name != current_name:
                success, result = self.client.rename_chat_file(self.current_file_path, new_name)
                if success:
                    self.current_file_path = result
                    self.client.chat_name = new_name
                    self.display_system_message(f"Chat renamed to: {new_name}")
                else:
                    messagebox.showerror("Rename Error", f"Failed to rename chat: {result}")
            dialog.destroy()

        ttk.Button(dialog, text="Cancel", command=dialog.destroy).grid(row=1, column=0, padx=10, pady=10)
        ttk.Button(dialog, text="Rename", command=do_rename).grid(row=1, column=1, padx=10, pady=10)
        dialog.bind("<Return>", lambda event: do_rename())

    def _load_chat(self) -> None:
        filename = filedialog.askopenfilename(
            initialdir=self.client.save_dir,
            title="Load Chat",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
        )
        if not filename:
            return

        if self.client.load_conversation(filename):
            self.current_file_path = filename

            self.conversation_display.config(state=tk.NORMAL)
            self.conversation_display.delete("1.0", tk.END)
            self.conversation_display.config(state=tk.DISABLED)

            self.model_var.set(self.client.model)
            self.model_status.config(text=f"Model: {self.client.model}")

            self.system_prompt_entry.delete("1.0", tk.END)
            self.system_prompt_entry.insert("1.0", self.client.system_prompt)

            self.temp_var.set(self.client.parameters.get("temperature", 0.7))
            self.top_p_var.set(self.client.parameters.get("top_p", 0.9))
            self.temp_label.config(text=f"{self.temp_var.get():.2f}")
            self.top_p_label.config(text=f"{self.top_p_var.get():.2f}")

            chat_name = self.client.chat_name or os.path.basename(filename)
            self.display_system_message(f"Loaded conversation: {chat_name}")

            for exchange in self.client.conversation:
                self.display_message("User", exchange["user"], "user_message")
                self.display_message("Assistant", exchange["assistant"], "assistant_message")
        else:
            messagebox.showerror("Error", f"Failed to load conversation from {filename}")

    def _clear_chat(self) -> None:
        if messagebox.askyesno("Clear Chat", "Are you sure you want to clear the current conversation?"):
            self.client.clear_conversation()
            self.conversation_display.config(state=tk.NORMAL)
            self.conversation_display.delete("1.0", tk.END)
            self.conversation_display.config(state=tk.DISABLED)
            self.current_file_path = None
            self.client.chat_name = ""
            self.display_system_message("Conversation cleared")

    def _show_about(self) -> None:
        about_window = tk.Toplevel(self.root)
        about_window.title("About Simple Ollama GUI Client")
        about_window.geometry("500x400")
        about_window.resizable(True, True)
        about_window.transient(self.root)
        about_window.grab_set()

        notebook = ttk.Notebook(about_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        main_frame = ttk.Frame(notebook)
        notebook.add(main_frame, text="About")

        ttk.Label(
            main_frame, text="Simple Ollama GUI Client", font=("Segoe UI", 16, "bold")
        ).pack(pady=(15, 5))
        ttk.Label(main_frame, text="Version 1.0").pack(pady=(0, 15))

        desc = (
            "A user-friendly GUI client for interacting with Ollama's AI models.\n"
            "Features include chat history management, parameter controls,\n"
            "theming, and system prompt configuration."
        )
        ttk.Label(main_frame, text=desc, justify=tk.CENTER).pack(pady=(0, 15))

        credits_frame = ttk.LabelFrame(main_frame, text="Credits")
        credits_frame.pack(fill=tk.X, padx=20, pady=5)

        credits_text = (
            "Project Manager: TheAmericanMaker\n"
            "AI Coding Assistant: Claude (Anthropic)\n"
            "Built with: Python and Tkinter\n"
            "Uses: Ollama API for model inference"
        )
        ttk.Label(credits_frame, text=credits_text, justify=tk.LEFT).pack(padx=10, pady=10)

        ttk.Label(main_frame, text=f"Created: {datetime.now().strftime('%B %Y')}").pack(pady=(15, 5))

        details_frame = ttk.Frame(notebook)
        notebook.add(details_frame, text="Development")

        details_text = scrolledtext.ScrolledText(details_frame, wrap=tk.WORD)
        details_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        details_text.insert(
            tk.END,
            "Development Process:\n\n"
            "This application was created through an AI-assisted development process.\n\n"
            "Technology Stack:\n"
            "- Python 3\n"
            "- Tkinter\n"
            "- Requests\n"
            "- Ollama API",
        )
        details_text.config(state=tk.DISABLED)

        license_frame = ttk.Frame(notebook)
        notebook.add(license_frame, text="License")

        license_text = scrolledtext.ScrolledText(license_frame, wrap=tk.WORD)
        license_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        license_text.insert(
            tk.END,
            "MIT License 2025 TheAmericanMaker\n\n"
            "Permission is hereby granted, free of charge, to any person obtaining a copy "
            "of this software... (see LICENSE file for full text)",
        )
        license_text.config(state=tk.DISABLED)

        ttk.Button(about_window, text="Close", command=about_window.destroy).pack(pady=10)

    def _setup_context_menu(self) -> None:
        self.context_menu = Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Copy", command=self._copy_selected)

        def show_context_menu(event) -> None:
            if self.conversation_display.tag_ranges(tk.SEL):
                self.context_menu.post(event.x_root, event.y_root)

        self.conversation_display.bind("<Button-3>", show_context_menu)

    def _copy_selected(self) -> None:
        try:
            selected_text = self.conversation_display.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.root.clipboard_clear()
            self.root.clipboard_append(selected_text)
        except tk.TclError:
            pass