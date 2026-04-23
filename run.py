import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="ollama_chat.log",
    filemode="a",
)

logger = logging.getLogger("OllamaChat")


def install_dependencies():
    try:
        import sv_ttk
    except ImportError:
        print("Installing sv_ttk for modern theme...")
        try:
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "sv-ttk"])
            import sv_ttk
            print("Successfully installed sv_ttk!")
        except Exception as e:
            print(f"Failed to install sv_ttk: {e}")
            print("Continuing with default theme...")


def main():
    install_dependencies()

    import tkinter as tk
    from gui.main import OllamaGUI

    root = tk.Tk()
    app = OllamaGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()