# import os
# import subprocess
# import requests
# import json
# import time
# from datetime import datetime
# import argparse
# import threading
# import itertools
# import sys
# import re

# # Configuration
# OLLAMA_URL = "http://localhost:11434" # Base URL for Ollama API
# OLLAMA_GENERATE_URL = f"{OLLAMA_URL}/api/generate"
# OLLAMA_TAGS_URL = f"{OLLAMA_URL}/api/tags"
 
# OUTPUT_FILE = "refactoring.md"
# SYSTEM_DOCS_FILE = "system_documentation.md"

# # Spinner control variables
# spinner_running = False
# spinner_thread = None

# def run_command(command, cwd=None):
#     """
#     Run a shell command and return its stdout.
#     Prints an error message if the command fails.
#     """
#     try:
#         result = subprocess.run(command, capture_output=True, text=True, check=True, cwd=cwd)
#         return result.stdout.strip()
#         f.write(doc_entry)
#     print(f"[✅] Documentation for commit {commit_hash} successfully added to {file_path}.")


# def handle_generate_docs(args):
#     """Handles the documentation generation with all parameters from command line."""
#     if not check_ollama_status():
#         print("[🛑] Ollama server is not running. Please start it to proceed.")
#         return
#     # Use default model if none specified
# """
# This file has been split for maintainability.
# See:
#   - git_utils.py: git-related utilities
#   - ollama_utils.py: Ollama API/model utilities
#   - spinner.py: spinner animation
#   - docgen.py: documentation generation
#   - main.py: CLI entry point
# """

# # Example usage:
# #   python3 main.py [args]

# from .main import main

# if __name__ == "__main__":
#     main()