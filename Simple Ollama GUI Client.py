import requests
import json
import os
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog, Menu
from tkinter.colorchooser import askcolor
import threading
import logging
import configparser
import re
from datetime import datetime
from PIL import Image, ImageTk
import io
import base64

# Add sv_ttk for modern theming
try:
    import sv_ttk
except ImportError:
    print("Installing sv_ttk for modern theme...")
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "sv-ttk"])
    import sv_ttk

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='ollama_chat.log',
    filemode='a'
)
logger = logging.getLogger('OllamaChat')

class OllamaChat:
    def __init__(self, base_url="http://localhost:11434", model="llama3.2"):
        """Initialize the Ollama chat interface."""
        self.base_url = base_url
        self.model = model
        self.api_generate = f"{base_url}/api/generate"
        self.api_chat = f"{base_url}/api/chat"
        self.api_models = f"{base_url}/api/tags"
        self.conversation = []
        self.save_dir = "chat_history"
        self.system_prompt = ""
        self.chat_name = ""
        self.parameters = {
            "temperature": 0.7,
            "top_p": 0.9,
            "top_k": 40,
            "max_tokens": 2000
        }
        
        # Create save directory if it doesn't exist
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)
            
        # Load configuration if exists
        self.config = configparser.ConfigParser()
        if os.path.exists('config.ini'):
            self.config.read('config.ini')
            if 'Ollama' in self.config:
                if 'base_url' in self.config['Ollama']:
                    self.base_url = self.config['Ollama']['base_url']
                if 'model' in self.config['Ollama']:
                    self.model = self.config['Ollama']['model']
                if 'system_prompt' in self.config['Ollama']:
                    self.system_prompt = self.config['Ollama']['system_prompt']
            if 'Parameters' in self.config:
                for key in self.parameters:
                    if key in self.config['Parameters']:
                        self.parameters[key] = float(self.config['Parameters'][key])
    
    def save_config(self):
        """Save current configuration to file."""
        if 'Ollama' not in self.config:
            self.config['Ollama'] = {}
        self.config['Ollama']['base_url'] = self.base_url
        self.config['Ollama']['model'] = self.model
        self.config['Ollama']['system_prompt'] = self.system_prompt
        
        if 'Parameters' not in self.config:
            self.config['Parameters'] = {}
        for key, value in self.parameters.items():
            self.config['Parameters'][key] = str(value)
            
        with open('config.ini', 'w') as configfile:
            self.config.write(configfile)
        logger.info('Configuration saved')
    
    def chat(self, prompt, stream_callback=None):
        """Send a message to the Ollama API and get a response."""
        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": stream_callback is not None,
            "system": self.system_prompt if self.system_prompt else None,
            "options": self.parameters
        }
        
        # Remove None values
        data = {k: v for k, v in data.items() if v is not None}
        
        try:
            if stream_callback:
                response_text = ""
                response = requests.post(self.api_generate, json=data, stream=True)
                response.raise_for_status()
                
                for line in response.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        if 'response' in chunk:
                            response_text += chunk['response']
                            stream_callback(chunk['response'])
                
                # Add the interaction to the conversation
                self.conversation.append({"user": prompt, "assistant": response_text})
                return response_text
            else:
                response = requests.post(self.api_generate, json=data)
                response.raise_for_status()
                result = response.json()
                
                # Add the interaction to the conversation
                self.conversation.append({"user": prompt, "assistant": result["response"]})
                return result["response"]
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error communicating with Ollama: {str(e)}")
            return f"Error communicating with Ollama: {str(e)}"
    
    def get_models(self):
        """Get list of available models from Ollama."""
        try:
            response = requests.get(self.api_models)
            response.raise_for_status()
            result = response.json()
            return [model['name'] for model in result['models']]
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting models: {str(e)}")
            return []
    
    def check_connection(self):
        """Check if Ollama server is available."""
        try:
            response = requests.get(f"{self.base_url}/api/version")
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException:
            return False
    
    def save_conversation(self, custom_name=None):
        """Save the current conversation to a text file."""
        if not self.conversation:
            return "No conversation to save"
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Use custom name if provided, otherwise use timestamp
        filename_base = custom_name if custom_name else f"chat_{timestamp}"
        self.chat_name = filename_base  # Save the current chat name
        
        filename = f"{self.save_dir}/{filename_base}.json"
        
        # Save as JSON with metadata
        data = {
            "model": self.model,
            "timestamp": datetime.now().isoformat(),
            "system_prompt": self.system_prompt,
            "parameters": self.parameters,
            "chat_name": filename_base,  # Include chat name in metadata
            "conversation": self.conversation
        }
        
        with open(filename, "w") as file:
            json.dump(data, file, indent=2)
        
        # Also save as text for readability
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
    
    def load_conversation(self, filename):
        """Load a conversation from a JSON file."""
        try:
            with open(filename, "r") as file:
                data = json.load(file)
            
            self.model = data.get("model", self.model)
            self.system_prompt = data.get("system_prompt", "")
            if "parameters" in data:
                self.parameters.update(data["parameters"])
            self.conversation = data.get("conversation", [])
            self.chat_name = data.get("chat_name", os.path.basename(filename).split('.')[0])
            return True
        except Exception as e:
            logger.error(f"Error loading conversation: {str(e)}")
            return False
    
    def rename_chat_file(self, old_path, new_name):
        """Rename an existing chat file."""
        try:
            dir_path = os.path.dirname(old_path)
            new_json_path = os.path.join(dir_path, f"{new_name}.json")
            
            # Check if the new filename already exists
            if os.path.exists(new_json_path):
                return False, "A file with this name already exists"
            
            # Rename the JSON file
            os.rename(old_path, new_json_path)
            
            # Also rename the corresponding text file if it exists
            old_txt_path = old_path.replace(".json", ".txt")
            if os.path.exists(old_txt_path):
                new_txt_path = os.path.join(dir_path, f"{new_name}.txt")
                os.rename(old_txt_path, new_txt_path)
            
            # Update the chat name in the JSON file
            with open(new_json_path, "r") as file:
                data = json.load(file)
            
            data["chat_name"] = new_name
            
            with open(new_json_path, "w") as file:
                json.dump(data, file, indent=2)
            
            return True, new_json_path
        except Exception as e:
            logger.error(f"Error renaming chat file: {str(e)}")
            return False, str(e)
    
    def set_model(self, model):
        """Change the model being used."""
        self.model = model
        self.save_config()
        return f"Model changed to {model}"
    
    def set_system_prompt(self, prompt):
        """Set the system prompt."""
        self.system_prompt = prompt
        self.save_config()
        return f"System prompt updated"
    
    def set_parameter(self, param, value):
        """Set a parameter value."""
        if param in self.parameters:
            try:
                self.parameters[param] = float(value)
                self.save_config()
                return f"Parameter {param} set to {value}"
            except ValueError:
                return f"Invalid value for {param}"
        else:
            return f"Unknown parameter: {param}"
    
    def clear_conversation(self):
        """Clear the current conversation."""
        self.conversation = []
        return "Conversation cleared"

class OllamaChatGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Simple Ollama GUI Client")
        self.root.geometry("900x700")
        self.root.minsize(700, 500)
        
        # Initialize theme and colors - change default to dark
        self.theme = "dark"  # Changed from "light" to "dark"
        self.colors = {
            "light": {
                "bg": "#f8f9fa",
                "text": "#212529",
                "input_bg": "#ffffff",
                "user_msg": "#e7f5ff",
                "assistant_msg": "#f8f9fa",
                "system_msg": "#fff9db",
                "highlight": "#339af0"
            },
            "dark": {
                "bg": "#212529",
                "text": "#f8f9fa",
                "input_bg": "#343a40",
                "user_msg": "#1864ab",
                "assistant_msg": "#343a40",
                "system_msg": "#5c3e08",
                "highlight": "#339af0"
            }
        }
        
        # Apply modern theme - change to dark
        sv_ttk.set_theme("dark")  # Changed from "light" to "dark"
        
        # Initialize the chat interface
        self.ollama = OllamaChat()
        
        # Add current file path tracking
        self.current_file_path = None
        
        # Create the GUI elements
        self.create_menu()
        self.create_widgets()
        
        # Set default theme
        self.apply_theme()
        
        # Setup context menu for copying messages
        self.setup_context_menu()
        
        # Check server connection
        self.check_connection()
        
        # Display initial system message
        self.display_system_message("Welcome to Simple Ollama GUI Client!")
        self.display_system_message(f"Current model: {self.ollama.model}")
        
        # Load models in background
        threading.Thread(target=self.load_models, daemon=True).start()
    
    def create_menu(self):
        """Create application menu."""
        self.menubar = Menu(self.root)
        
        # File menu
        file_menu = Menu(self.menubar, tearoff=0)
        file_menu.add_command(label="New Chat", command=self.clear_chat)
        file_menu.add_command(label="Open Chat", command=self.load_chat)
        file_menu.add_command(label="Save Chat", command=self.save_chat)
        file_menu.add_command(label="Save Chat As...", command=lambda: self.save_chat(save_as=True))
        file_menu.add_command(label="Rename Current Chat", command=self.rename_current_chat)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        self.menubar.add_cascade(label="File", menu=file_menu)
        
        # Edit menu
        edit_menu = Menu(self.menubar, tearoff=0)
        edit_menu.add_command(label="Copy Selected", command=self.copy_selected)
        edit_menu.add_command(label="Clear Chat", command=self.clear_chat)
        self.menubar.add_cascade(label="Edit", menu=edit_menu)
        
        # Settings menu
        settings_menu = Menu(self.menubar, tearoff=0)
        settings_menu.add_command(label="Toggle Theme", command=self.toggle_theme)
        settings_menu.add_command(label="Connection Settings", command=self.show_connection_settings)
        settings_menu.add_command(label="Model Parameters", command=self.show_parameters)
        settings_menu.add_command(label="System Prompt", command=self.show_system_prompt)
        self.menubar.add_cascade(label="Settings", menu=settings_menu)
        
        # Help menu
        help_menu = Menu(self.menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
        self.menubar.add_cascade(label="Help", menu=help_menu)
        
        self.root.config(menu=self.menubar)
    
    def setup_context_menu(self):
        """Setup context menu for conversation display."""
        self.context_menu = Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Copy", command=self.copy_selected)
        
        def show_context_menu(event):
            if self.conversation_display.tag_ranges(tk.SEL):
                self.context_menu.post(event.x_root, event.y_root)
        
        self.conversation_display.bind("<Button-3>", show_context_menu)
    
    def copy_selected(self):
        """Copy selected text to clipboard."""
        try:
            selected_text = self.conversation_display.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.root.clipboard_clear()
            self.root.clipboard_append(selected_text)
        except tk.TclError:
            pass  # No selection
    
    def create_widgets(self):
        # Apply consistent padding
        padding = {'padx': 12, 'pady': 12}
        small_padding = {'padx': 6, 'pady': 6}
        
        # Create main paned window for resizable sections
        self.main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_paned.pack(fill=tk.BOTH, expand=True, **padding)
        
        # Left frame for conversation
        self.left_frame = ttk.Frame(self.main_paned)
        self.main_paned.add(self.left_frame, weight=3)
        
        # Create a frame for the conversation display
        self.conversation_frame = ttk.Frame(self.left_frame)
        self.conversation_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create a scrolled text widget for displaying conversation with visible selection
        self.conversation_display = scrolledtext.ScrolledText(
            self.conversation_frame, 
            wrap=tk.WORD, 
            font=("Segoe UI", 10),  # Modern font
            selectbackground="#0078d7",
            selectforeground="white"
        )
        self.conversation_display.pack(fill=tk.BOTH, expand=True)
        self.conversation_display.config(state=tk.DISABLED)
        
        # Create a frame for the status bar with modern styling
        self.status_frame = ttk.Frame(self.left_frame)
        self.status_frame.pack(fill=tk.X, **small_padding)
        
        # Create status indicator with improved styling
        self.status_var = tk.StringVar(value="Disconnected")
        self.status_label = ttk.Label(self.status_frame, text="Status:", font=("Segoe UI", 9))
        self.status_label.pack(side=tk.LEFT, padx=(0, 5))
        self.status_indicator = ttk.Label(self.status_frame, textvariable=self.status_var, font=("Segoe UI", 9, "bold"))
        self.status_indicator.pack(side=tk.LEFT)
        
        # Create model status with improved styling
        self.model_status = ttk.Label(self.status_frame, text=f"Model: {self.ollama.model}", font=("Segoe UI", 9, "bold"))
        self.model_status.pack(side=tk.RIGHT)
        
        # Create a frame for the input area with improved spacing
        self.input_frame = ttk.Frame(self.left_frame)
        self.input_frame.pack(fill=tk.X, **padding)
        
        # Create a scrolled text widget for user input with better styling
        self.user_input = scrolledtext.ScrolledText(
            self.input_frame, 
            wrap=tk.WORD, 
            height=4, 
            font=("Segoe UI", 10)
        )
        self.user_input.pack(fill=tk.X, side=tk.LEFT, expand=True, padx=(0, 8))
        self.user_input.bind("<Shift-Return>", lambda e: None)
        self.user_input.bind("<Return>", self.send_message)
        
        # Create a send button with modern styling
        self.send_button = ttk.Button(
            self.input_frame, 
            text="Send", 
            command=self.send_message,
            style="Accent.TButton"  # Use the accent style from sv_ttk
        )
        self.send_button.pack(side=tk.RIGHT)
        
        # Right frame for settings and controls
        self.right_frame = ttk.Frame(self.main_paned)
        self.main_paned.add(self.right_frame, weight=1)
        
        # Model selection frame with improved styling
        self.model_frame = ttk.LabelFrame(self.right_frame, text="Model Selection")
        self.model_frame.pack(fill=tk.X, **small_padding)
        
        # Model dropdown with better styling
        self.model_var = tk.StringVar(value=self.ollama.model)
        self.model_dropdown = ttk.Combobox(
            self.model_frame, 
            textvariable=self.model_var,
            font=("Segoe UI", 9)
        )
        self.model_dropdown.pack(fill=tk.X, **small_padding)
        self.model_dropdown['values'] = [self.ollama.model]
        self.model_dropdown.bind("<<ComboboxSelected>>", self.change_model)
        
        # Refresh models button with accent styling
        ttk.Button(
            self.model_frame, 
            text="Refresh Models", 
            command=self.load_models,
            style="Accent.TButton"
        ).pack(fill=tk.X, **small_padding)
        
        # Parameters frame with improved spacing
        self.params_frame = ttk.LabelFrame(self.right_frame, text="Parameters")
        self.params_frame.pack(fill=tk.X, **small_padding)
        
        # Temperature scale with better styling
        ttk.Label(self.params_frame, text="Temperature:", font=("Segoe UI", 9)).pack(anchor=tk.W, padx=8, pady=(8, 0))
        self.temp_var = tk.DoubleVar(value=self.ollama.parameters["temperature"])
        self.temp_scale = ttk.Scale(
            self.params_frame, 
            from_=0.0, 
            to=2.0, 
            variable=self.temp_var, 
            orient=tk.HORIZONTAL, 
            command=lambda v: self.update_parameter("temperature")
        )
        self.temp_scale.pack(fill=tk.X, **small_padding)
        self.temp_label = ttk.Label(self.params_frame, text=f"{self.temp_var.get():.2f}", font=("Segoe UI", 9))
        self.temp_label.pack(anchor=tk.W, padx=8)
        
        # Top-p scale with better styling
        ttk.Label(self.params_frame, text="Top-p:", font=("Segoe UI", 9)).pack(anchor=tk.W, padx=8, pady=(8, 0))
        self.top_p_var = tk.DoubleVar(value=self.ollama.parameters["top_p"])
        self.top_p_scale = ttk.Scale(
            self.params_frame, 
            from_=0.0, 
            to=1.0, 
            variable=self.top_p_var, 
            orient=tk.HORIZONTAL, 
            command=lambda v: self.update_parameter("top_p")
        )
        self.top_p_scale.pack(fill=tk.X, **small_padding)
        self.top_p_label = ttk.Label(self.params_frame, text=f"{self.top_p_var.get():.2f}", font=("Segoe UI", 9))
        self.top_p_label.pack(anchor=tk.W, padx=8)
        
        # System Prompt frame with improved styling
        self.system_frame = ttk.LabelFrame(self.right_frame, text="System Prompt")
        self.system_frame.pack(fill=tk.X, **small_padding)
        
        # System prompt entry with better styling
        self.system_prompt_var = tk.StringVar(value=self.ollama.system_prompt)
        self.system_prompt_entry = scrolledtext.ScrolledText(
            self.system_frame, 
            wrap=tk.WORD, 
            height=3, 
            font=("Segoe UI", 9)
        )
        self.system_prompt_entry.pack(fill=tk.X, **small_padding)
        self.system_prompt_entry.insert("1.0", self.ollama.system_prompt)
        
        # Apply system prompt button with accent styling
        ttk.Button(
            self.system_frame, 
            text="Apply System Prompt", 
            command=self.apply_system_prompt,
            style="Accent.TButton"
        ).pack(fill=tk.X, **small_padding)
        
        # Commands frame
        self.commands_frame = ttk.LabelFrame(self.right_frame, text="Commands")
        self.commands_frame.pack(fill=tk.X, **small_padding)
        
        # Command buttons with consistent styling
        ttk.Button(
            self.commands_frame, 
            text="Save Chat", 
            command=self.save_chat,
            style="Accent.TButton"
        ).pack(fill=tk.X, **small_padding)
        
        ttk.Button(
            self.commands_frame, 
            text="Load Chat", 
            command=self.load_chat
        ).pack(fill=tk.X, **small_padding)
        
        ttk.Button(
            self.commands_frame, 
            text="Clear Chat", 
            command=self.clear_chat
        ).pack(fill=tk.X, **small_padding)
        
        ttk.Button(
            self.commands_frame, 
            text="Toggle Theme", 
            command=self.toggle_theme
        ).pack(fill=tk.X, **small_padding)
    
    def apply_theme(self):
        """Apply current theme to all widgets with improved styling."""
        colors = self.colors[self.theme]
        
        # Configure text display
        self.conversation_display.config(
            background=colors["bg"],
            foreground=colors["text"],
            selectbackground="#0078d7" if self.theme == "light" else "#265f99",
            selectforeground="white"
        )
        
        # Configure input area
        self.user_input.config(
            background=colors["input_bg"],
            foreground=colors["text"],
            selectbackground="#0078d7" if self.theme == "light" else "#265f99",
            selectforeground="white"
        )
        
        # Configure system prompt area
        self.system_prompt_entry.config(
            background=colors["input_bg"],
            foreground=colors["text"],
            selectbackground="#0078d7" if self.theme == "light" else "#265f99",
            selectforeground="white"
        )
        
        # Configure tag colors with improved styling
        self.conversation_display.tag_configure("user_message", 
            background=colors["user_msg"],
            lmargin1=20, lmargin2=20, rmargin=20)
        
        self.conversation_display.tag_configure("assistant_message", 
            background=colors["assistant_msg"],
            lmargin1=20, lmargin2=20, rmargin=20)
        
        self.conversation_display.tag_configure("system_message", 
            background=colors["system_msg"],
            lmargin1=20, lmargin2=20, rmargin=20)
        
        # Status colors with improved visibility
        if self.status_var.get() == "Connected":
            self.status_indicator.config(foreground="#28a745")  # Green
        else:
            self.status_indicator.config(foreground="#dc3545")  # Red
    
    def toggle_theme(self):
        """Toggle between light and dark themes."""
        self.theme = "dark" if self.theme == "light" else "light"
        # Apply sv_ttk theme
        sv_ttk.set_theme(self.theme)
        self.apply_theme()
    
    def update_parameter(self, param):
        """Update parameter value."""
        if param == "temperature":
            value = self.temp_var.get()
            self.temp_label.config(text=f"{value:.2f}")
        elif param == "top_p":
            value = self.top_p_var.get()
            self.top_p_label.config(text=f"{value:.2f}")
        
        # Update in backend
        self.ollama.set_parameter(param, value)
    
    def apply_system_prompt(self):
        """Apply the system prompt."""
        system_prompt = self.system_prompt_entry.get("1.0", tk.END).strip()
        result = self.ollama.set_system_prompt(system_prompt)
        self.display_system_message(result)
    
    def load_models(self):
        """Load available models from Ollama."""
        models = self.ollama.get_models()
        if models:
            self.model_dropdown['values'] = models
            self.display_system_message(f"Loaded {len(models)} models")
    
    def check_connection(self):
        """Check connection to Ollama server."""
        def do_check():
            connected = self.ollama.check_connection()
            self.status_var.set("Connected" if connected else "Disconnected")
            if connected:
                self.status_indicator.config(foreground="green")
            else:
                self.status_indicator.config(foreground="red")
        
        # Run check in thread to avoid blocking UI
        threading.Thread(target=do_check, daemon=True).start()
    
    def show_connection_settings(self):
        """Show connection settings dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Connection Settings")
        dialog.geometry("400x150")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Ollama API URL:").grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
        
        url_var = tk.StringVar(value=self.ollama.base_url)
        url_entry = ttk.Entry(dialog, textvariable=url_var, width=30)
        url_entry.grid(row=0, column=1, padx=10, pady=10)
        
        def save_settings():
            new_url = url_var.get().strip()
            if new_url:
                self.ollama.base_url = new_url
                self.ollama.api_generate = f"{new_url}/api/generate"
                self.ollama.api_chat = f"{new_url}/api/chat"
                self.ollama.api_models = f"{new_url}/api/tags"
                self.ollama.save_config()
                self.check_connection()
                self.display_system_message(f"API URL changed to {new_url}")
            dialog.destroy()
        
        ttk.Button(dialog, text="Test Connection", 
                 command=lambda: messagebox.showinfo("Connection Test", 
                                                   "Connected" if self.ollama.check_connection() else "Failed to connect")
                ).grid(row=1, column=0, padx=10, pady=10)
        
        ttk.Button(dialog, text="Save", command=save_settings).grid(row=1, column=1, padx=10, pady=10)
    
    def show_parameters(self):
        """Show advanced parameters dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Model Parameters")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Add parameter entries
        row = 0
        param_vars = {}
        
        for param, value in self.ollama.parameters.items():
            ttk.Label(dialog, text=f"{param}:").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
            param_vars[param] = tk.StringVar(value=str(value))
            ttk.Entry(dialog, textvariable=param_vars[param], width=10).grid(row=row, column=1, padx=10, pady=5)
            row += 1
        
        def save_params():
            for param, var in param_vars.items():
                try:
                    value = float(var.get())
                    self.ollama.set_parameter(param, value)
                except ValueError:
                    messagebox.showerror("Invalid Value", f"Invalid value for {param}: {var.get()}")
                    return
            
            # Update displayed values in main window
            self.temp_var.set(self.ollama.parameters["temperature"])
            self.top_p_var.set(self.ollama.parameters["top_p"])
            self.temp_label.config(text=f"{self.temp_var.get():.2f}")
            self.top_p_label.config(text=f"{self.top_p_var.get():.2f}")
            
            self.display_system_message("Parameters updated")
            dialog.destroy()
        
        ttk.Button(dialog, text="Save", command=save_params).grid(row=row, column=0, columnspan=2, padx=10, pady=10)
    
    def show_system_prompt(self):
        """Show system prompt dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("System Prompt")
        dialog.geometry("600x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        prompt_text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD, font=("Segoe UI", 10))
        prompt_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        prompt_text.insert("1.0", self.ollama.system_prompt)
        
        def save_prompt():
            prompt = prompt_text.get("1.0", tk.END).strip()
            self.ollama.set_system_prompt(prompt)
            self.system_prompt_entry.delete("1.0", tk.END)
            self.system_prompt_entry.insert("1.0", prompt)
            self.display_system_message("System prompt updated")
            dialog.destroy()
        
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Save", command=save_prompt).pack(side=tk.RIGHT, padx=5)
    
    def display_message(self, sender, message, tag=None):
        """Display a message in the conversation display with modern styling."""
        self.conversation_display.config(state=tk.NORMAL)
        
        # Add a timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Format the message with chat bubbles based on sender
        if sender == "User":
            # Add timestamp and header
            self.conversation_display.insert(tk.END, f"\n[{timestamp}] ", "timestamp")
            self.conversation_display.insert(tk.END, "You", "user_header")
            self.conversation_display.insert(tk.END, "\n", "normal")
            
            # Add message with padding for bubble effect
            self.conversation_display.insert(tk.END, f"{message}\n", tag)
        elif sender == "Assistant":
            # Add timestamp and header
            self.conversation_display.insert(tk.END, f"\n[{timestamp}] ", "timestamp")
            self.conversation_display.insert(tk.END, "Assistant", "assistant_header")
            self.conversation_display.insert(tk.END, "\n", "normal")
            
            # Add message with padding for bubble effect
            self.conversation_display.insert(tk.END, f"{message}\n", tag)
        else:  # System message
            self.conversation_display.insert(tk.END, f"\n[{timestamp}] ", "timestamp")
            self.conversation_display.insert(tk.END, "System", "system_header")
            self.conversation_display.insert(tk.END, f": {message}\n", tag)
        
        # Configure visual styles for message elements
        self.conversation_display.tag_config("timestamp", foreground="#6c757d", font=("Segoe UI", 8))
        self.conversation_display.tag_config("user_header", foreground="#0366d6", font=("Segoe UI", 10, "bold"))
        self.conversation_display.tag_config("assistant_header", foreground="#28a745", font=("Segoe UI", 10, "bold"))
        self.conversation_display.tag_config("system_header", foreground="#5f4b8b", font=("Segoe UI", 10, "bold"))
        
        # Scroll to the bottom
        self.conversation_display.see(tk.END)
        self.conversation_display.config(state=tk.DISABLED)
    
    def display_system_message(self, message):
        """Display a system message in the conversation display."""
        self.display_message("System", message, "system_message")
    
    def send_message(self, event=None):
        """Send the user's message to the Ollama API."""
        # Get the user's message
        user_message = self.user_input.get("1.0", tk.END).strip()
        
        if not user_message:
            return "break"
        
        # Display the user's message
        self.display_message("User", user_message, "user_message")
        
        # Clear the input field
        self.user_input.delete("1.0", tk.END)
        
        # Get the response from Ollama
        self.root.config(cursor="watch")
        self.send_button.config(state=tk.DISABLED)
        self.root.update()
        
        # Display assistant typing indicator
        self.conversation_display.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.typing_mark = f"\n[{timestamp}] Assistant:\n"
        self.conversation_display.insert(tk.END, self.typing_mark, "assistant_header")
        self.conversation_display.insert(tk.END, "Thinking...", "typing_indicator")
        self.conversation_display.see(tk.END)
        self.conversation_display.config(state=tk.DISABLED)
        
        # Function to handle streaming responses
        def stream_handler(text_chunk):
            self.conversation_display.config(state=tk.NORMAL)
            # Remove typing indicator on first chunk
            if "Thinking..." in self.conversation_display.get("1.0", tk.END):
                typing_pos = self.conversation_display.search("Thinking...", "1.0", tk.END)
                if typing_pos:
                    self.conversation_display.delete(typing_pos, f"{typing_pos}+10c")
            
            # Add the chunk
            self.conversation_display.insert(tk.END, text_chunk, "assistant_message")
            self.conversation_display.see(tk.END)
            self.conversation_display.config(state=tk.DISABLED)
            self.root.update()
        
        def process_message():
            try:
                # Use threading to prevent freezing the UI
                response = self.ollama.chat(user_message, stream_handler)
                
                # Update model status in case it was changed
                self.model_status.config(text=f"Model: {self.ollama.model}")
                
            except Exception as e:
                logger.error(f"Error sending message: {str(e)}")
                
                # Remove typing indicator
                self.conversation_display.config(state=tk.NORMAL)
                typing_pos = self.conversation_display.search("Thinking...", "1.0", tk.END)
                if typing_pos:
                    self.conversation_display.delete(typing_pos, f"{typing_pos}+10c")
                self.conversation_display.config(state=tk.DISABLED)
                
                self.display_system_message(f"Error: {str(e)}")
            
            self.root.config(cursor="")
            self.send_button.config(state=tk.NORMAL)
        
        # Start processing in a separate thread
        threading.Thread(target=process_message, daemon=True).start()
        
        return "break"  # Prevent default behavior of Return key
    
    def change_model(self, event=None):
        """Change the model used by Ollama."""
        new_model = self.model_var.get().strip()
        if new_model:
            result = self.ollama.set_model(new_model)
            self.model_status.config(text=f"Model: {new_model}")
            self.display_system_message(result)
    
    def save_chat(self, save_as=False):
        """Save the current conversation."""
        if not self.ollama.conversation:
            messagebox.showinfo("Save Chat", "No conversation to save")
            return
        
        if save_as or not self.ollama.chat_name:
            # Use file dialog to get custom location and name
            default_name = self.ollama.chat_name or f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            filename = filedialog.asksaveasfilename(
                initialdir=self.ollama.save_dir,
                initialfile=f"{default_name}.json",
                title="Save Chat As",
                filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
            )
            
            if not filename:
                return  # User cancelled
            
            # Extract directory and base name
            dir_path = os.path.dirname(filename)
            base_name = os.path.basename(filename)
            # Remove extension if it's .json
            if base_name.lower().endswith('.json'):
                base_name = os.path.splitext(base_name)[0]
            
            # Update save directory if different
            if dir_path != self.ollama.save_dir:
                # Create the directory if it doesn't exist
                if not os.path.exists(dir_path):
                    os.makedirs(dir_path)
            
            # Save the conversation
            data = {
                "model": self.ollama.model,
                "timestamp": datetime.now().isoformat(),
                "system_prompt": self.ollama.system_prompt,
                "parameters": self.ollama.parameters,
                "chat_name": base_name,
                "conversation": self.ollama.conversation
            }
            
            with open(filename, "w") as file:
                json.dump(data, file, indent=2)
            
            # Also save as text for readability
            text_filename = os.path.splitext(filename)[0] + ".txt"
            with open(text_filename, "w") as file:
                file.write(f"Chat with Ollama ({self.ollama.model}) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                if self.ollama.system_prompt:
                    file.write(f"System prompt: {self.ollama.system_prompt}\n\n")
                
                for i, exchange in enumerate(self.ollama.conversation, 1):
                    file.write(f"[{i}] User: {exchange['user']}\n\n")
                    file.write(f"[{i}] Assistant: {exchange['assistant']}\n\n")
                    file.write("-" * 80 + "\n\n")
            
            # Update current file path and chat name
            self.current_file_path = filename
            self.ollama.chat_name = base_name
            
            self.display_system_message(f"Conversation saved to {filename}")
        else:
            # Use existing name in the default save directory
            filename = f"{self.ollama.save_dir}/{self.ollama.chat_name}.json"
            
            # Save as JSON with metadata
            data = {
                "model": self.ollama.model,
                "timestamp": datetime.now().isoformat(),
                "system_prompt": self.ollama.system_prompt,
                "parameters": self.ollama.parameters,
                "chat_name": self.ollama.chat_name,
                "conversation": self.ollama.conversation
            }
            
            with open(filename, "w") as file:
                json.dump(data, file, indent=2)
            
            # Also save as text for readability
            text_filename = f"{self.ollama.save_dir}/{self.ollama.chat_name}.txt"
            with open(text_filename, "w") as file:
                file.write(f"Chat with Ollama ({self.ollama.model}) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                if self.ollama.system_prompt:
                    file.write(f"System prompt: {self.ollama.system_prompt}\n\n")
                
                for i, exchange in enumerate(self.ollama.conversation, 1):
                    file.write(f"[{i}] User: {exchange['user']}\n\n")
                    file.write(f"[{i}] Assistant: {exchange['assistant']}\n\n")
                    file.write("-" * 80 + "\n\n")
            
            # Update current file path
            self.current_file_path = filename
            
            self.display_system_message(f"Conversation saved to {filename}")
    
    def rename_current_chat(self):
        """Rename the current chat file."""
        if not self.current_file_path or not os.path.exists(self.current_file_path):
            messagebox.showinfo("Rename Chat", "Please save the chat first before renaming.")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Rename Chat")
        dialog.geometry("400x150")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Enter a new name for this chat:").grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
        
        current_name = self.ollama.chat_name or os.path.basename(self.current_file_path).split('.')[0]
        name_var = tk.StringVar(value=current_name)
        name_entry = ttk.Entry(dialog, textvariable=name_var, width=30)
        name_entry.grid(row=0, column=1, padx=10, pady=10)
        name_entry.select_range(0, tk.END)
        name_entry.focus()
        
        def do_rename():
            new_name = name_var.get().strip()
            if new_name and new_name != current_name:
                success, result = self.ollama.rename_chat_file(self.current_file_path, new_name)
                if success:
                    self.current_file_path = result
                    self.ollama.chat_name = new_name
                    self.display_system_message(f"Chat renamed to: {new_name}")
                else:
                    messagebox.showerror("Rename Error", f"Failed to rename chat: {result}")
            dialog.destroy()
        
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).grid(row=1, column=0, padx=10, pady=10)
        ttk.Button(dialog, text="Rename", command=do_rename).grid(row=1, column=1, padx=10, pady=10)
        
        # Bind Enter key to rename
        dialog.bind("<Return>", lambda event: do_rename())
    
    def load_chat(self):
        """Load a saved conversation."""
        filename = filedialog.askopenfilename(
            initialdir=self.ollama.save_dir,
            title="Load Chat",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        
        if filename:
            if self.ollama.load_conversation(filename):
                # Track the current file path
                self.current_file_path = filename
                
                # Clear the display
                self.conversation_display.config(state=tk.NORMAL)
                self.conversation_display.delete("1.0", tk.END)
                self.conversation_display.config(state=tk.DISABLED)
                
                # Update model info
                self.model_var.set(self.ollama.model)
                self.model_status.config(text=f"Model: {self.ollama.model}")
                
                # Update system prompt
                self.system_prompt_entry.delete("1.0", tk.END)
                self.system_prompt_entry.insert("1.0", self.ollama.system_prompt)
                
                # Update parameters
                self.temp_var.set(self.ollama.parameters["temperature"])
                self.top_p_var.set(self.ollama.parameters["top_p"])
                self.temp_label.config(text=f"{self.temp_var.get():.2f}")
                self.top_p_label.config(text=f"{self.top_p_var.get():.2f}")
                
                # Display conversation
                chat_name = self.ollama.chat_name or os.path.basename(filename)
                self.display_system_message(f"Loaded conversation: {chat_name}")
                
                for exchange in self.ollama.conversation:
                    self.display_message("User", exchange["user"], "user_message")
                    self.display_message("Assistant", exchange["assistant"], "assistant_message")
            else:
                messagebox.showerror("Error", f"Failed to load conversation from {filename}")
    
    def clear_chat(self):
        """Clear the current conversation."""
        if messagebox.askyesno("Clear Chat", "Are you sure you want to clear the current conversation?"):
            result = self.ollama.clear_conversation()
            
            # Clear the display
            self.conversation_display.config(state=tk.NORMAL)
            self.conversation_display.delete("1.0", tk.END)
            self.conversation_display.config(state=tk.DISABLED)
            
            # Reset current file path
            self.current_file_path = None
            self.ollama.chat_name = ""
            
            self.display_system_message(result)
    
    def show_about(self):
        """Show enhanced about dialog with creation information."""
        about_window = tk.Toplevel(self.root)
        about_window.title("About Simple Ollama GUI Client")
        about_window.geometry("500x400")
        about_window.resizable(True, True)
        about_window.transient(self.root)
        about_window.grab_set()
        
        # Use a notebook for tabbed information
        notebook = ttk.Notebook(about_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Main tab
        main_frame = ttk.Frame(notebook)
        notebook.add(main_frame, text="About")
        
        # Title and version
        title_label = ttk.Label(main_frame, text="Simple Ollama GUI Client", 
                               font=("Segoe UI", 16, "bold"))
        title_label.pack(pady=(15, 5))
        
        version_label = ttk.Label(main_frame, text="Version 1.0")
        version_label.pack(pady=(0, 15))
        
        # Description
        desc_text = ("A user-friendly GUI client for interacting with Ollama's AI models.\n"
                    "Features include chat history management, model parameter controls,\n"
                    "theming, and system prompt configuration.")
        desc_label = ttk.Label(main_frame, text=desc_text, justify=tk.CENTER)
        desc_label.pack(pady=(0, 15))
        
        # Credits frame
        credits_frame = ttk.LabelFrame(main_frame, text="Credits")
        credits_frame.pack(fill=tk.X, padx=20, pady=5)
        
        credits_text = (
            "AI Project Manager: TheAmericanMaker\n"
            "AI Coding Assistant: Claude 3.7 Sonnet (Anthropic)\n"
            "Development Environment: Cursor AI IDE\n"
            "Built with: Python and Tkinter\n"
            "Uses: Ollama API for model inference"
        )
        
        credits_label = ttk.Label(credits_frame, text=credits_text, justify=tk.LEFT)
        credits_label.pack(padx=10, pady=10)
        
        # Created date
        date_label = ttk.Label(main_frame, text=f"Created: {datetime.now().strftime('%B %Y')}")
        date_label.pack(pady=(15, 5))
        
        # Credits tab with more details
        details_frame = ttk.Frame(notebook)
        notebook.add(details_frame, text="Development")
        
        # Scrollable text area for detailed information
        details_text = scrolledtext.ScrolledText(details_frame, wrap=tk.WORD)
        details_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        development_details = """
        Development Process:
        
        This application was created through an AI-assisted development process. TheAmericanMaker directed the development by specifying features and requirements, while Claude 3.7 Sonnet generated the Python code within the Cursor AI IDE.
        
        The development followed an iterative approach:
        
        1. Initial creation of a simple CLI interface to Ollama
        2. Conversion to a basic Tkinter GUI application
        3. Progressive enhancement with features like:
           - Streaming responses
           - Theme switching
           - Parameter controls
           - Chat management
           - Improved styling and usability features
        
        Technology Stack:
        
        - Python 3: Core programming language
        - Tkinter: GUI framework for the interface
        - Requests: HTTP library for API communication
        - JSON: For data serialization and chat storage
        - Ollama API: For accessing local AI models
        - Threading: For non-blocking user interface
        
        This project demonstrates the potential of human-AI collaboration in software development, combining human direction and oversight with AI-assisted coding and implementation.
        """
        
        details_text.insert(tk.END, development_details)
        details_text.config(state=tk.DISABLED)
        
        # License tab
        license_frame = ttk.Frame(notebook)
        notebook.add(license_frame, text="License")
        
        license_text = scrolledtext.ScrolledText(license_frame, wrap=tk.WORD)
        license_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        mit_license = """
        MIT License 2025 TheAmericanMaker
        
        Permission is hereby granted, free of charge, to any person obtaining a copy
        of this software and associated documentation files (the "Software"), to deal
        in the Software without restriction, including without limitation the rights
        to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
        copies of the Software, and to permit persons to whom the Software is
        furnished to do so, subject to the following conditions:
        
        The above copyright notice and this permission notice shall be included in all
        copies or substantial portions of the Software.
        
        THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
        IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
        FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
        AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
        LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
        OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
        SOFTWARE.
        """
        
        license_text.insert(tk.END, mit_license)
        license_text.config(state=tk.DISABLED)
        
        # Close button
        close_button = ttk.Button(about_window, text="Close", command=about_window.destroy)
        close_button.pack(pady=10)

def install_dependencies():
    """Install required dependencies if missing."""
    try:
        import sv_ttk
    except ImportError:
        print("Installing sv_ttk for modern theme...")
        import subprocess
        import sys
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "sv-ttk"])
            import sv_ttk
            print("Successfully installed sv_ttk!")
        except Exception as e:
            print(f"Failed to install sv_ttk: {e}")
            print("Continuing with default theme...")

def main():
    # Try to install dependencies before starting
    install_dependencies()
    
    root = tk.Tk()
    app = OllamaChatGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()