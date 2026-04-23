import configparser
import os
from typing import Any

import logging

logger = logging.getLogger("OllamaChat")


class Config:
    """Configuration manager for the Ollama GUI client."""

    DEFAULT_CONFIG = {
        "base_url": "http://localhost:11434",
        "model": "llama3.2",
        "system_prompt": "",
        "theme": "dark",
        "temperature": 0.7,
        "top_p": 0.9,
        "top_k": 40,
        "num_ctx": 2048,
        "max_tokens": 2000,
    }

    def __init__(self, config_file: str = "config.ini"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self._load()

    def _load(self) -> None:
        """Load configuration from file."""
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)

        if "Ollama" not in self.config:
            self.config["Ollama"] = {}
        if "Parameters" not in self.config:
            self.config["Parameters"] = {}
        if "UI" not in self.config:
            self.config["UI"] = {}

        for key, value in self.DEFAULT_CONFIG.items():
            section = "Parameters" if key in ("temperature", "top_p", "top_k", "num_ctx", "max_tokens") else "Ollama"
            if key not in self.config[section]:
                self.config[section][key] = str(value)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        section = "Parameters" if key in ("temperature", "top_p", "top_k", "num_ctx", "max_tokens") else "Ollama"
        if key in self.config[section]:
            value = self.config[section][key]
            if key in ("temperature", "top_p", "top_k", "num_ctx", "max_tokens"):
                return float(value)
            return value
        return default or self.DEFAULT_CONFIG.get(key)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        section = "Parameters" if key in ("temperature", "top_p", "top_k", "num_ctx", "max_tokens") else "Ollama"
        self.config[section][key] = str(value)

    def get_params(self) -> dict[str, float]:
        """Get all parameters as a dictionary."""
        return {
            "temperature": self.get("temperature", 0.7),
            "top_p": self.get("top_p", 0.9),
            "top_k": self.get("top_k", 40),
            "num_ctx": self.get("num_ctx", 2048),
            "max_tokens": self.get("max_tokens", 2000),
        }

    def save(self) -> None:
        """Save configuration to file."""
        with open(self.config_file, "w") as f:
            self.config.write(f)
        logger.info("Configuration saved")

    def get_base_url(self) -> str:
        return self.get("base_url", "http://localhost:11434")

    def set_base_url(self, url: str) -> None:
        self.set("base_url", url)

    def get_model(self) -> str:
        return self.get("model", "llama3.2")

    def set_model(self, model: str) -> None:
        self.set("model", model)

    def get_system_prompt(self) -> str:
        return self.get("system_prompt", "")

    def set_system_prompt(self, prompt: str) -> None:
        self.set("system_prompt", prompt)

    def get_theme(self) -> str:
        return self.get("theme", "dark")

    def set_theme(self, theme: str) -> None:
        self.set("theme", theme)