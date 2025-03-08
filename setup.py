#!/usr/bin/env python
import subprocess
import sys

def setup():
    """Set up the Ollama GUI Client environment"""
    # Upgrade pip first
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
    
    # Install core requirements
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    
    # Ensure sv-ttk is properly installed
    subprocess.check_call([sys.executable, "-m", "pip", "install", "sv-ttk"])
    
    print("Setup complete! You can now run the application with 'python run.py'")

if __name__ == "__main__":
    setup() 