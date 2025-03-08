#!/usr/bin/env python
import os
import sys
import subprocess

def run_app():
    """Run the Ollama GUI application with the virtual environment"""
    # Get the absolute path to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Define paths
    if sys.platform.startswith('win'):
        python_path = os.path.join(script_dir, '.venv', 'Scripts', 'python.exe')
    else:
        python_path = os.path.join(script_dir, '.venv', 'bin', 'python')
    
    app_path = os.path.join(script_dir, 'Simple Ollama GUI Client.py')
    
    # Check if virtual environment exists
    if not os.path.exists(python_path):
        print("Virtual environment not found. Please set up the environment first.")
        return
    
    # Run the application
    subprocess.run([python_path, app_path])

if __name__ == "__main__":
    run_app() 