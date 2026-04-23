import os
import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext
from typing import Optional, Callable


class FileBrowser(ttk.Frame):
    """File browser sidebar panel."""

    def __init__(self, parent, on_file_select: Optional[Callable[[str], None]] = None):
        super().__init__(parent)
        self.on_file_select = on_file_select
        self.current_path = os.getcwd()
        self._create_widgets()
        self._load_directory(self.current_path)

    def _create_widgets(self) -> None:
        self.path_label = ttk.Label(self, text="File Browser", font=("Segoe UI", 10, "bold"))
        self.path_label.pack(pady=(0, 5))

        self.path_entry = ttk.Entry(self)
        self.path_entry.pack(fill=tk.X, padx=5, pady=(0, 5))
        self.path_entry.insert(0, self.current_path)
        self.path_entry.bind("<Return>", lambda e: self._ navigate_to(self.path_entry.get()))

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        ttk.Button(btn_frame, text="..", width=3, command=self._go_up).pack(side=tk.LEFT, padx=1)
        ttk.Button(btn_frame, text="Home", command=self._go_home).pack(side=tk.LEFT, padx=1)

        self.tree = ttk.Treeview(self, show="tree")
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", self._on_double_click)

    def _load_directory(self, path: str) -> None:
        if not os.path.isdir(path):
            return

        self.current_path = path
        self.path_entry.delete(0, tk.END)
        self.path_entry.insert(0, path)

        for item in self.tree.get_children():
            self.tree.delete(item)

        try:
            items = sorted(os.listdir(path), key=lambda x: (not os.path.isdir(os.path.join(path, x)), x.lower()))
            for item in items:
                if item.startswith("."):
                    continue
                full_path = os.path.join(path, item)
                is_dir = os.path.isdir(full_path)
                icon = "[D]" if is_dir else "[F]"
                self.tree.insert("", tk.END, text=f"{icon} {item}", values=(full_path, is_dir))
        except PermissionError:
            pass

    def _on_select(self, event) -> None:
        pass

    def _on_double_click(self, event) -> None:
        item = self.tree.identify("item", event.x, event.y)
        if item:
            path = self.tree.item(item, "values")[0]
            is_dir = self.tree.item(item, "values")[1]
            if is_dir == "True":
                self._load_directory(path)
            elif self.on_file_select:
                self.on_file_select(path)

    def _go_up(self) -> None:
        parent = os.path.dirname(self.current_path)
        if parent and parent != self.current_path:
            self._load_directory(parent)

    def _go_home(self) -> None:
        self._load_directory(os.path.expanduser("~"))

    def _navigate_to(self, path: str) -> None:
        path = os.path.abspath(path)
        if os.path.isdir(path):
            self._load_directory(path)

    def set_root(self, path: str) -> None:
        self._load_directory(path)


class TerminalPanel(ttk.Frame):
    """Terminal panel for running commands."""

    def __init__(self, parent, on_command: Optional[Callable[[str], None]] = None):
        super().__init__(parent)
        self.on_command = on_command
        self.command_history = []
        self.history_index = -1
        self._create_widgets()
        self._write_welcome()

    def _create_widgets(self) -> None:
        header = ttk.Label(self, text="Terminal", font=("Segoe UI", 10, "bold"))
        header.pack(pady=(0, 5))

        output_frame = ttk.Frame(self)
        output_frame.pack(fill=tk.BOTH, expand=True)

        self.output = scrolledtext.ScrolledText(
            output_frame,
            wrap=tk.WORD,
            font=("Consolas", 9),
            background="#1e1e1e",
            foreground="#cccccc",
            insertbackground="white",
        )
        self.output.pack(fill=tk.BOTH, expand=True)
        self.output.config(state=tk.DISABLED)

        input_frame = ttk.Frame(self)
        input_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Label(input_frame, text="$", font=("Consolas", 10)).pack(side=tk.LEFT, padx=(5, 0))

        self.input = ttk.Entry(input_frame, font=("Consolas", 10))
        self.input.pack(fill=tk.X, expand=True, side=tk.LEFT, padx=5)
        self.input.bind("<Return>", self._execute)
        self.input.bind("<Up>", self._history_up)
        self.input.bind("<Down>", self._history_down)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(btn_frame, text="Clear", command=self._clear).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Kill Process", command=self._kill).pack(side=tk.LEFT, padx=2)

    def _write_welcome(self) -> None:
        self._write("Welcome to Terminal Panel\n")
        self._write("Type commands and press Enter to run\n")
        self._write("Use Up/Down for command history\n")
        self._write("-" * 40 + "\n")

    def _write(self, text: str) -> None:
        self.output.config(state=tk.NORMAL)
        self.output.insert(tk.END, text)
        self.output.see(tk.END)
        self.output.config(state=tk.DISABLED)

    def _execute(self, event=None) -> str:
        cmd = self.input.get().strip()
        if not cmd:
            return "break"

        self.command_history.append(cmd)
        self.history_index = len(self.command_history)

        self._write(f"$ {cmd}\n")
        self.input.delete(0, tk.END)

        if self.on_command:
            self.on_command(cmd, self._write)

        return "break"

    def _history_up(self, event=None) -> str:
        if self.command_history and self.history_index > 0:
            self.history_index -= 1
            self.input.delete(0, tk.END)
            self.input.insert(0, self.command_history[self.history_index])
        return "break"

    def _history_down(self, event=None) -> str:
        if self.history_index < len(self.command_history) - 1:
            self.history_index += 1
            self.input.delete(0, tk.END)
            self.input.insert(0, self.command_history[self.history_index])
        else:
            self.history_index = len(self.command_history)
            self.input.delete(0, tk.END)
        return "break"

    def _clear(self) -> None:
        self.output.config(state=tk.NORMAL)
        self.output.delete(1.0, tk.END)
        self.output.config(state=tk.DISABLED)
        self._write_welcome()

    def _kill(self) -> None:
        self._write("\n[Process killed]\n")

    def run_command(self, cmd: str, output_callback: Callable[[str], None]) -> None:
        """Run a command programmatically."""
        self.command_history.append(cmd)
        self.history_index = len(self.command_history)
        self._write(f"$ {cmd}\n")
        if self.on_command:
            self.on_command(cmd, output_callback)