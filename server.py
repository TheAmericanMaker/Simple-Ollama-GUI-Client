"""
Server module for headless API access.
Allows the Ollama GUI to be used as an HTTP server for other tools.
"""

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional

from core.ollama_client import OllamaClient


class OllamaRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Ollama API."""

    def log_message(self, format, *args):
        pass

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _get_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        return json.loads(body) if body else {}

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/health":
            self._send_json({"status": "ok", "model": self.server.ollama.model})
        elif path == "/models":
            models = self.server.ollama.get_models()
            self._send_json({"models": models})
        elif path == "/conversation":
            self._send_json({"conversation": self.server.ollama.conversation})
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._get_body()

        if path == "/chat":
            prompt = body.get("prompt", "")
            stream = body.get("stream", False)

            if stream:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()

                def stream_callback(text):
                    self.wfile.write(f"data: {json.dumps({'content': text})}\n\n".encode())

                result = self.server.ollama.chat(prompt, stream_callback)
            else:
                result = self.server.ollama.chat(prompt)
                self._send_json({"response": result, "model": self.server.ollama.model})

        elif path == "/generate":
            prompt = body.get("prompt", "")
            result = self.server.ollama.chat(prompt)
            self._send_json({"response": result, "model": self.server.ollama.model})

        elif path == "/model":
            model = body.get("model")
            if model:
                self.server.ollama.set_model(model)
                self.server.config.set_model(model)
                self.server.config.save()
                self._send_json({"status": "ok", "model": model})
            else:
                self._send_json({"error": "model required"}, 400)

        elif path == "/system-prompt":
            prompt = body.get("prompt", "")
            self.server.ollama.set_system_prompt(prompt)
            self._send_json({"status": "ok"})

        elif path == "/parameters":
            for key, value in body.items():
                self.server.ollama.set_parameter(key, value)
            self._send_json({"status": "ok", "parameters": self.server.ollama.parameters})

        elif path == "/save":
            result = self.server.ollama.save_conversation()
            self._send_json({"status": result})

        elif path == "/clear":
            self.server.ollama.clear_conversation()
            self._send_json({"status": "ok"})

        else:
            self._send_json({"error": "Not found"}, 404)


class OllamaServer(HTTPServer):
    """HTTP server for Ollama GUI."""

    def __init__(self, port: int, ollama: OllamaClient, config):
        super().__init__(("", port), OllamaRequestHandler)
        self.ollama = ollama
        self.config = config

    def start(self):
        thread = threading.Thread(target=self.serve_forever, daemon=True)
        thread.start()
        return f"Server running on http://localhost:{self.server_address[1]}"

    def stop_server(self):
        self.shutdown()


def start_server(port: int = 8765, base_url: str = "http://localhost:11434", model: str = "llama3.2"):
    """Start the Ollama server."""
    from utils.config import Config

    config = Config()
    config.set_base_url(base_url)
    config.set_model(model)
    config.save()

    ollama = OllamaClient(base_url=base_url, model=model)
    ollama.system_prompt = config.get_system_prompt()
    ollama.parameters = config.get_params()

    server = OllamaServer(port, ollama, config)
    return server


if __name__ == "__main__":
    import sys

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = start_server(port)
    print(server.start())
    print("Press Ctrl+C to stop")
    try:
        input()
    except KeyboardInterrupt:
        print("\nStopping server...")
        server.stop_server()