import os
import threading
import json
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import requests
from datetime import datetime


class AgentMode:
    """AI Agent for file editing via Ollama."""

    def __init__(self, ollama_client):
        self.ollama = ollama_client
        self.project_root = os.getcwd()
        self.agent_history = []

    def execute_task(self, task: str, file_context: str = "") -> str:
        """Execute a file editing task."""
        system_prompt = f"""You are a coding assistant. The user wants to: {task}

Project root: {self.project_root}

Instructions:
1. First, understand what files need to be modified
2. Read those files to understand the current state
3. Make the necessary changes
4. Report what you did

You have access to these tools:
- read_file(path): Read a file's contents
- write_file(path, content): Write content to a file (overwrites)
- edit_file(path, old_string, new_string): Edit specific portions
- list_dir(path): List directory contents
- run_command(cmd): Run shell commands

Use these tools to complete the task. Be precise and don't make unnecessary changes."""

        messages = [{"role": "system", "content": system_prompt}]
        if file_context:
            messages.append({"role": "user", "content": file_context})
        messages.append({"role": "user", "content": task})

        return self._stream_response(messages)

    def _stream_response(self, messages: list) -> str:
        data = {
            "model": self.ollama.model,
            "messages": messages,
            "stream": True,
        }

        try:
            response = requests.post(self.ollama.api_chat, json=data, stream=True, timeout=120)
            response.raise_for_status()

            full_response = ""
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line)
                    if "content" in chunk.get("message", {}):
                        content = chunk["message"]["content"]
                        full_response += content
                    if chunk.get("done", False):
                        break
            return full_response
        except requests.exceptions.RequestException as e:
            return f"Error: {str(e)}"

    def describe_change(self, diff: str) -> str:
        """Ask AI to describe what changed in a diff."""
        prompt = f"Explain what changed in this diff in plain English:\n\n{diff}"
        messages = [{"role": "user", "content": prompt}]
        return self._stream_response(messages)


class AgentPanel(ttk.Frame):
    """Agent mode panel for AI-powered file editing."""

    def __init__(self, parent, ollama_client, on_agent_complete=None):
        super().__init__(parent)
        self.ollama = ollama_client
        self.agent = AgentMode(ollama_client)
        self.on_agent_complete = on_agent_complete
        self.is_running = False
        self._create_widgets()

    def _create_widgets(self) -> None:
        header = ttk.Label(self, text="Agent Mode", font=("Segoe UI", 10, "bold"))
        header.pack(pady=(0, 5))

        prompt_frame = ttk.Frame(self)
        prompt_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.prompt_text = scrolledtext.ScrolledText(
            prompt_frame,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            height=3,
        )
        self.prompt_text.pack(fill=tk.X, pady=(0, 5))
        self.prompt_text.insert(
            "1.0",
            "Describe what you want done... (e.g., 'Add a function to calculate fibonacci')",
        )

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Button(
            btn_frame,
            text="Execute",
            command=self._execute_task,
            style="Accent.TButton",
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Stop", command=self._stop).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Clear", command=self._clear).pack(side=tk.LEFT, padx=2)

        output_frame = ttk.Frame(self)
        output_frame.pack(fill=tk.BOTH, expand=True)

        self.output = scrolledtext.ScrolledText(
            output_frame,
            wrap=tk.WORD,
            font=("Consolas", 9),
            background="#1e1e1e",
            foreground="#cccccc",
        )
        self.output.pack(fill=tk.BOTH, expand=True)
        self.output.config(state=tk.DISABLED)

    def _execute_task(self) -> None:
        task = self.prompt_text.get("1.0", tk.END).strip()
        if not task or self.is_running:
            return

        self.is_running = True
        self.prompt_text.config(state=tk.NORMAL)
        self.prompt_text.delete("1.0", tk.END)
        self.prompt_text.config(state=tk.DISABLED)

        self._write(f"[Executing] {task}\n")
        self._write("-" * 40 + "\n")

        def run():
            try:
                result = self.agent.execute_task(task)
                self._write(result)
            except Exception as e:
                self._write(f"[Error] {str(e)}\n")
            finally:
                self.is_running = False

        threading.Thread(target=run, daemon=True).start()

    def _stop(self) -> None:
        self.is_running = False
        self._write("\n[Stopped]\n")

    def _clear(self) -> None:
        self.output.config(state=tk.NORMAL)
        self.output.delete("1.0", tk.END)
        self.output.config(state=tk.DISABLED)
        self._write("[Agent cleared]\n")

    def _write(self, text: str) -> None:
        def do_write():
            self.output.config(state=tk.NORMAL)
            self.output.insert(tk.END, text)
            self.output.see(tk.END)
            self.output.config(state=tk.DISABLED)

        self.after(0, do_write)