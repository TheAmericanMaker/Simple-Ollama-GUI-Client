import logging
import json
from datetime import datetime
from typing import Optional, Callable

import requests

logger = logging.getLogger("OllamaChat")


class OllamaClient:
    """Backend client for communicating with Ollama API."""

    DEFAULT_PARAMS = {
        "temperature": 0.7,
        "top_p": 0.9,
        "top_k": 40,
        "num_ctx": 2048,
    }

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2"):
        self.base_url = base_url
        self.model = model
        self.parameters = self.DEFAULT_PARAMS.copy()
        self.system_prompt: str = ""
        self.conversation: list[dict[str, str]] = []
        self.chat_name: str = ""
        self.save_dir = "chat_history"

    @property
    def api_chat(self) -> str:
        return f"{self.base_url}/api/chat"

    @property
    def api_generate(self) -> str:
        return f"{self.base_url}/api/generate"

    @property
    def api_models(self) -> str:
        return f"{self.base_url}/api/tags"

    def chat(
        self,
        prompt: str,
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Send a message to the Ollama API and get a response."""
        messages = [{"role": "user", "content": prompt}]
        if self.system_prompt:
            messages.insert(0, {"role": "system", "content": self.system_prompt})

        data = {
            "model": self.model,
            "messages": messages,
            "stream": stream_callback is not None,
            "options": self.parameters,
        }
        data = {k: v for k, v in data.items() if v is not None}

        try:
            if stream_callback:
                return self._chat_stream(data, stream_callback)
            else:
                return self._chat_nonstream(data)
        except requests.exceptions.RequestException as e:
            logger.error(f"Error communicating with Ollama: {e}")
            return f"Error communicating with Ollama: {e}"

    def _chat_stream(
        self, data: dict, stream_callback: Callable[[str], None]
    ) -> str:
        response_text = ""
        response = requests.post(self.api_chat, json=data, stream=True)
        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                chunk = json.loads(line)
                if "content" in chunk.get("message", {}):
                    text = chunk["message"]["content"]
                    response_text += text
                    stream_callback(text)
                if chunk.get("done", False):
                    break

        self.conversation.append({"user": data["messages"][-1]["content"], "assistant": response_text})
        return response_text

    def _chat_nonstream(self, data: dict) -> str:
        response = requests.post(self.api_chat, json=data)
        response.raise_for_status()
        result = response.json()
        content = result["message"]["content"]
        self.conversation.append({"user": data["messages"][-1]["content"], "assistant": content})
        return content

    def get_models(self) -> list[str]:
        """Get list of available models from Ollama."""
        try:
            response = requests.get(self.api_models)
            response.raise_for_status()
            result = response.json()
            return [model["name"] for model in result.get("models", [])]
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting models: {e}")
            return []

    def check_connection(self) -> bool:
        """Check if Ollama server is available."""
        try:
            response = requests.get(f"{self.base_url}/api/version")
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException:
            return False

    def save_conversation(self, custom_name: Optional[str] = None) -> str:
        """Save the current conversation to a JSON file."""
        if not self.conversation:
            return "No conversation to save"

        import os

        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename_base = custom_name or f"chat_{timestamp}"
        self.chat_name = filename_base

        filename = f"{self.save_dir}/{filename_base}.json"

        data = {
            "model": self.model,
            "timestamp": datetime.now().isoformat(),
            "system_prompt": self.system_prompt,
            "parameters": self.parameters,
            "chat_name": filename_base,
            "conversation": self.conversation,
        }

        with open(filename, "w") as file:
            json.dump(data, file, indent=2)

        text_filename = f"{self.save_dir}/{filename_base}.txt"
        with open(text_filename, "w") as file:
            file.write(f"Chat with Ollama ({self.model}) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            if self.system_prompt:
                file.write(f"System prompt: {self.system_prompt}\n\n")
            for i, exchange in enumerate(self.conversation, 1):
                file.write(f"[{i}] User: {exchange['user']}\n\n")
                file.write(f"[{i}] Assistant: {exchange['assistant']}\n\n")
                file.write("-" * 80 + "\n\n")

        return f"Conversation saved to {filename}"

    def load_conversation(self, filename: str) -> bool:
        """Load a conversation from a JSON file."""
        try:
            with open(filename, "r") as file:
                data = json.load(file)

            self.model = data.get("model", self.model)
            self.system_prompt = data.get("system_prompt", "")
            if "parameters" in data:
                self.parameters.update(data["parameters"])
            self.conversation = data.get("conversation", [])
            self.chat_name = data.get("chat_name", filename.split("/")[-1].split(".")[0])
            return True
        except Exception as e:
            logger.error(f"Error loading conversation: {e}")
            return False

    def rename_chat_file(self, old_path: str, new_name: str) -> tuple[bool, str]:
        """Rename an existing chat file."""
        import os

        try:
            dir_path = os.path.dirname(old_path)
            new_json_path = os.path.join(dir_path, f"{new_name}.json")

            if os.path.exists(new_json_path):
                return False, "A file with this name already exists"

            os.rename(old_path, new_json_path)

            old_txt_path = old_path.replace(".json", ".txt")
            if os.path.exists(old_txt_path):
                new_txt_path = os.path.join(dir_path, f"{new_name}.txt")
                os.rename(old_txt_path, new_txt_path)

            with open(new_json_path, "r") as file:
                data = json.load(file)
            data["chat_name"] = new_name
            with open(new_json_path, "w") as file:
                json.dump(data, file, indent=2)

            return True, new_json_path
        except Exception as e:
            logger.error(f"Error renaming chat file: {e}")
            return False, str(e)

    def set_model(self, model: str) -> str:
        """Change the model being used."""
        self.model = model
        return f"Model changed to {model}"

    def set_system_prompt(self, prompt: str) -> str:
        """Set the system prompt."""
        self.system_prompt = prompt
        return "System prompt updated"

    def set_parameter(self, param: str, value: float) -> str:
        """Set a parameter value."""
        if param in self.parameters:
            try:
                self.parameters[param] = float(value)
                return f"Parameter {param} set to {value}"
            except ValueError:
                return f"Invalid value for {param}"
        return f"Unknown parameter: {param}"

    def clear_conversation(self) -> str:
        """Clear the current conversation."""
        self.conversation = []
        return "Conversation cleared"