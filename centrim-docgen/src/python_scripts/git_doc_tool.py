import os
import subprocess
import requests
import json
import time
from datetime import datetime
import argparse
import threading
import itertools
import sys

# Configuration
OLLAMA_URL = "http://localhost:11434" # Base URL for Ollama API
OLLAMA_GENERATE_URL = f"{OLLAMA_URL}/api/generate"
OLLAMA_TAGS_URL = f"{OLLAMA_URL}/api/tags"

OUTPUT_FILE = "refactoring.md"
DIFF_LIMIT = 5000  # Limit to avoid model overload (adjust as needed)

# Spinner control variables
spinner_running = False
spinner_thread = None

def run_command(command, cwd=None):
    """
    Run a shell command and return its stdout.
    Prints an error message if the command fails.
    """
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True, cwd=cwd)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"[❌] Command failed: {' '.join(command)}\n{e.stderr}")
        return None
    except FileNotFoundError:
        print(f"[❌] Command not found: {command[0]}. Make sure Git is installed and in your PATH.")
        return None
    except Exception as e:
        print(f"[❌] Error running command: {e}")
        return None

def get_recent_commit_info(num_commits):
    """
    Fetches info (hash, author, message) for the N most recent commits.
    Returns a list of tuples (hash, author, message, date).
    """
    print(f"[🔍] Fetching info for the last {num_commits} commits...")
    commit_info_raw = run_command(["git", "log", f"-{num_commits}", "--pretty=format:%H%n%an%n%s%n%ad", "--date=iso-strict", "--reverse"])
    
    commits = []
    if commit_info_raw:
        lines = commit_info_raw.split('\n')
        for i in range(0, len(lines), 4):
            if i + 3 < len(lines):
                commit_hash = lines[i]
                author = lines[i+1]
                message = lines[i+2]
                date = lines[i+3]
                commits.append((commit_hash, author, message, date))
                print(f"[✅] Fetched commit: {commit_hash} by {author}")
    else:
        print("[❌] Could not fetch recent commit info.")
    return commits

def get_git_diff(commit_hash):
    """
    Fetch the git diff for the specified commit relative to its parent.
    """
    print(f"[🔍] Fetching git diff for commit {commit_hash}...")
    diff = run_command(["git", "diff", f"{commit_hash}~1", commit_hash])
    if diff:
        print(f"[✅] Diff fetched ({len(diff)} characters).")
    else:
        print("[ℹ️] No diff found for this commit (e.g., initial commit or merge commit without changes).")
    return diff

def read_documented_hashes(file_path):
    """
    Reads the existing documentation file and extracts documented commit hashes.
    Assumes hashes are marked with 'Commit Hash: <hash>'.
    Returns a set of hashes.
    """
    documented_hashes = set()
    if os.path.exists(file_path):
        print(f"[🔍] Reading existing documentation from {file_path}...")
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith("**Commit Hash**: `"):
                    hash_val = line.replace("**Commit Hash**: `", "").replace("`", "").strip()
                    documented_hashes.add(hash_val)
        print(f"[✅] Found {len(documented_hashes)} existing documented hashes.")
    else:
        print(f"[ℹ️] Documentation file '{file_path}' not found. A new one will be created if needed.")
    return documented_hashes

def spinner_animation():
    """
    Displays a spinning cursor in the console.
    """
    spinner_chars = itertools.cycle(['-', '\\', '|', '/'])
    while spinner_running:
        sys.stdout.write(next(spinner_chars) + '\r')
        sys.stdout.flush()
        time.sleep(0.1)

def start_spinner():
    """Starts the spinner animation."""
    global spinner_running, spinner_thread
    spinner_running = True
    spinner_thread = threading.Thread(target=spinner_animation)
    spinner_thread.daemon = True # Allow main program to exit even if spinner is running
    spinner_thread.start()

def stop_spinner():
    """Stops the spinner animation."""
    global spinner_running, spinner_thread
    if spinner_running:
        spinner_running = False
        if spinner_thread and spinner_thread.is_alive():
            spinner_thread.join(timeout=0.2) # Give it a moment to finish

def check_ollama_status():
    """Checks if the Ollama server is running."""
    print(f"[⚙️] Checking Ollama server status at {OLLAMA_URL}...")
    try:
        response = requests.get(OLLAMA_URL, timeout=5)
        if response.status_code == 200:
            print("[✅] Ollama server is running.")
            return True
        else:
            print(f"[❌] Ollama server responded with status code {response.status_code}.")
            return False
    except requests.exceptions.ConnectionError:
        print(f"[❌] Could not connect to Ollama server at {OLLAMA_URL}.")
        print("Please ensure Ollama is installed and running.")
        print("Download Ollama from: https://ollama.com/")
        print("After installation, Ollama usually starts automatically.")
        return False
    except requests.exceptions.Timeout:
        print(f"[❌] Connection to Ollama server timed out.")
        return False
    except Exception as e:
        print(f"[❌] An unexpected error occurred while checking Ollama status: {e}")
        return False

def get_available_ollama_models():
    """Fetches a list of models available on the local Ollama server."""
    try:
        response = requests.get(OLLAMA_TAGS_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        models = [m['name'].split(':')[0] for m in data.get('models', [])]
        return sorted(list(set(models))) # Return unique model names
    except requests.exceptions.RequestException as e:
        print(f"[❌] Error fetching Ollama models: {e}")
        return []

def pull_ollama_model(model_name):
    """Attempts to pull a specified Ollama model."""
    print(f"[⬇️] Attempting to pull model '{model_name}'. This may take some time...")
    try:
        # Use subprocess to run 'ollama pull' command
        # This allows us to see the progress of the pull command
        pull_process = subprocess.run(
            ["ollama", "pull", model_name],
            capture_output=False, # Let subprocess print directly to console
            text=True,
            check=True
        )
        print(f"[✅] Model '{model_name}' pulled successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[❌] Failed to pull model '{model_name}'. Error: {e}")
        print("Please check your internet connection or try 'ollama pull' manually.")
        return False
    except FileNotFoundError:
        print("[❌] 'ollama' command not found. Make sure Ollama is installed and in your PATH.")
        return False
    except Exception as e:
        print(f"[❌] An unexpected error occurred during model pull: {e}")
        return False

def select_ollama_model(cli_model_name=None):
    """
    Guides the user to select an Ollama model, pulling it if necessary.
    Returns the chosen model name or None if selection fails.
    """
    if cli_model_name:
        print(f"[⚙️] Using model '{cli_model_name}' specified via command line.")
        available_models = get_available_ollama_models()
        if cli_model_name in available_models:
            return cli_model_name
        else:
            print(f"[⚠️] Model '{cli_model_name}' not found locally.")
            confirm = input(f"Do you want to pull '{cli_model_name}' now? (y/N): ").lower()
            if confirm == 'y':
                if pull_ollama_model(cli_model_name):
                    return cli_model_name
                else:
                    return None
            else:
                print("[🛑] Model not pulled. Cannot proceed without the specified model.")
                return None

    models = get_available_ollama_models()
    if not models:
        print("[ℹ️] No Ollama models found locally.")
        print("You need to pull at least one model. Recommended: 'phi3' or 'mistral'.")
        suggested_model = input("Enter a model name to pull (e.g., phi3): ").strip()
        if suggested_model:
            if pull_ollama_model(suggested_model):
                return suggested_model
            else:
                return None
        else:
            print("[🛑] No model specified. Cannot proceed.")
            return None

    print("\n[📚] Available Ollama models:")
    for i, model in enumerate(models):
        print(f"  {i+1}. {model}")

    while True:
        choice = input(f"Enter the number of the model to use, or type a model name to pull (e.g., phi3): ").strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(models):
                chosen_model = models[idx]
                print(f"[✅] Selected model: {chosen_model}")
                return chosen_model
            else:
                print("[❌] Invalid number. Please try again.")
        elif choice:
            # User typed a model name, try to pull it
            if pull_ollama_model(choice):
                return choice
            else:
                print("[❌] Failed to pull model. Please try again or choose from available models.")
        else:
            print("[❌] Invalid input. Please enter a number or a model name.")


def send_to_ollama(prompt, model_name, watch_mode=False):
    """
    Send prompt to local Ollama and receive response.
    Handles streaming responses from Ollama.
    If watch_mode is True, prints raw streaming output.
    """
    status_message_prefix = " [🤖] Querying Ollama for documentation..."
    
    if not watch_mode:
        sys.stdout.write(status_message_prefix + ' ' * 40 + '\r')
        sys.stdout.flush()
        start_spinner()
    else:
        sys.stdout.write(status_message_prefix + '\n')
        sys.stdout.flush()
        sys.stdout.write("--- Ollama Raw Output Start ---\n")
        sys.stdout.write(f"Prompt sent:\n---\n{prompt}\n---\n") # Print the full prompt in watch mode
        sys.stdout.flush()


    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": True # Enable streaming
    }

    output = ""
    try:
        response = requests.post(OLLAMA_GENERATE_URL, json=payload, stream=True, timeout=300)
        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                decoded = line.decode('utf-8')
                try:
                    data = json.loads(decoded)
                    if data.get("done"):
                        break
                    response_part = data.get("response", "")
                    output += response_part
                    if watch_mode:
                        sys.stdout.write(response_part)
                        sys.stdout.flush()
                except json.JSONDecodeError:
                    sys.stdout.write(f"\n[⚠️] Could not decode JSON line: {decoded}\n")
                    sys.stdout.flush()
                    output += decoded
        
        if not watch_mode:
            stop_spinner()
            sys.stdout.write(f"\r{status_message_prefix} [✅] Ollama response received.\n")
            sys.stdout.flush()
        else:
            sys.stdout.write("\n--- Ollama Raw Output End ---\n")
            sys.stdout.write("[✅] Ollama response received.\n")
            sys.stdout.flush()
        return output.strip()

    except requests.exceptions.ConnectionError as e:
        if not watch_mode: stop_spinner()
        sys.stdout.write(f"\r{status_message_prefix} [❌] Error connecting to Ollama: {e}\n")
        sys.stdout.flush()
        return None
    except requests.exceptions.Timeout:
        if not watch_mode: stop_spinner()
        sys.stdout.write(f"\r{status_message_prefix} [❌] Ollama request timed out after {300} seconds.\n")
        sys.stdout.flush()
        return None
    except requests.exceptions.RequestException as e:
        if not watch_mode: stop_spinner()
        sys.stdout.write(f"\r{status_message_prefix} [❌] Ollama API Request Error: {e}\n")
        sys.stdout.flush()
        return None
    except Exception as e:
        if not watch_mode: stop_spinner()
        sys.stdout.write(f"\r{status_message_prefix} [❌] An unexpected error occurred while querying Ollama: {e}\n")
        sys.stdout.flush()
        return None

def generate_documentation(diff, commit_message, model_name, watch_mode=False):
    """
    Prepares a detailed prompt for Ollama to generate concise documentation
    based on the provided Git diff and commit message, with a word limit.
    """
    truncated_diff = diff[:DIFF_LIMIT] + ("\n... (truncated)" if len(diff) > DIFF_LIMIT else "")

    prompt = f"""
You are an expert software engineer and technical writer. Your task is to generate concise, clear, and detailed documentation for a Git commit, focusing on the changes introduced by the diff.

Consider the following:
- The programming language is Dart.
- The documentation should explain *what* was changed, *why* it was changed, and *how* it impacts the codebase (e.g., new features, bug fixes, performance improvements, refactoring).
- Provide code examples if necessary to illustrate key changes.
- The tone should be professional and informative.
- Structure the documentation clearly with headings and bullet points.
- If the diff is very small or trivial, state that it's a minor change.
- **IMPORTANT**: The documentation must be concise and easy to understand, focusing only on important information. It should be approximately 300 words or less.

Here is the commit message:
"{commit_message}"

Here is the Git diff that you MUST analyze:
```diff
{truncated_diff if truncated_diff else "[No significant diff content provided or diff was empty.]"}
```

Please generate the documentation in Markdown format. Start directly with the content, no introductory phrases like "Here is the documentation".
"""
    print("[📝] Generating documentation prompt for Ollama...")
    documentation = send_to_ollama(prompt, model_name, watch_mode)
    return documentation

def append_to_documentation_file(file_path, commit_hash, author, commit_message, commit_date, generated_docs):
    """
    Appends the new documentation entry to the specified Markdown file.
    Creates the file if it doesn't exist.
    """
    print(f"[✍️] Appending documentation for {commit_hash} to {file_path}...")
    
    doc_entry = f"""
---
## Commit Documentation

**Commit Hash**: `{commit_hash}`
**Author**: {author}
**Date**: {commit_date}
**Commit Message**: {commit_message}

### Changes and Rationale
{generated_docs if generated_docs else "No detailed documentation generated by Ollama. The diff might be too small or Ollama encountered an issue."}
---
"""
    mode = 'a' if os.path.exists(file_path) else 'w'
    with open(file_path, mode, encoding='utf-8') as f:
        f.write(doc_entry)
    print(f"[✅] Documentation for commit {commit_hash} successfully added to {file_path}.")

def handle_generate_docs(args):
    """Handles the 'generate-docs' action."""
    # 0. Check Ollama server status
    if not check_ollama_status():
        print("[🛑] Ollama server is not running. Please start it to proceed.")
        return

    # 0.5. Select Ollama model
    ollama_model_to_use = select_ollama_model(args.model)
    if not ollama_model_to_use:
        print("[🛑] No Ollama model selected or available. Exiting.")
        return

    print("🚀 Starting Git Documentation Generator 🚀")

    # Determine how many diffs to process based on arguments and file existence
    num_diffs_to_process = 1 # Default: process only the latest commit

    if args.diffno is not None:
        num_diffs_to_process = args.diffno
        print(f"[⚙️] Processing {num_diffs_to_process} diff(s) as specified by --diffno.")
    elif not os.path.exists(OUTPUT_FILE):
        num_diffs_to_process = 5 # Default if no file exists
        print(f"[⚙️] No existing documentation file found. Defaulting to processing the last {num_diffs_to_process} diffs.")
    else:
        print(f"[⚙️] Existing documentation file found. Defaulting to processing only the latest diff.")


    # 1. Get recent commit info
    recent_commits = get_recent_commit_info(num_diffs_to_process)
    if not recent_commits:
        print("[🛑] Exiting: Could not get any commit information.")
        return

    # 2. Read existing documented hashes
    documented_hashes = read_documented_hashes(OUTPUT_FILE)

    # 3. Process each commit
    for commit_hash, author, commit_message, commit_date in recent_commits:
        if commit_hash in documented_hashes:
            print(f"[ℹ️] Commit {commit_hash} is already documented in {OUTPUT_FILE}. Skipping.")
            continue

        print(f"\n--- Processing new commit: {commit_hash} ---")

        # 4. Get the git diff for the current commit
        diff = get_git_diff(commit_hash)
        if not diff:
            print(f"[ℹ️] No significant diff found for commit {commit_hash}. Skipping documentation generation.")
            continue

        # 5. Generate documentation using Ollama (spinner will run here, or raw output if --watch)
        generated_docs = generate_documentation(diff, commit_message, ollama_model_to_use, args.watch)
        if not generated_docs:
            print(f"[❌] Failed to generate documentation from Ollama for commit {commit_hash}. Please check Ollama server and model.")
            continue

        # 6. Append to the documentation file
        append_to_documentation_file(OUTPUT_FILE, commit_hash, author, commit_message, commit_date, generated_docs)

    print("\n🎉 Git Documentation Generation Complete! 🎉")

def main():
    """
    Main function to orchestrate the documentation generation process.
    """
    parser = argparse.ArgumentParser(
        description="Generate Git commit documentation using Ollama.",
        formatter_class=argparse.RawTextHelpFormatter # For better help formatting
    )

    # Global arguments
    parser.add_argument(
        "--model",
        type=str,
        help="Specify the Ollama model to use (e.g., 'phi3', 'mistral').\n"
             "If not provided, the script will prompt you to select one."
    )
    parser.add_argument(
        "--diffno",
        type=int,
        help="Number of recent diffs to process. Overrides default behavior.\n"
             "Default: 1 (latest commit) if 'refactoring.md' exists, 5 otherwise."
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch raw streaming output from Ollama during generation."
    )

    # Subcommands (can be expanded later if needed)
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # 'generate-docs' command - this will be the default if no command is given
    generate_parser = subparsers.add_parser(
        "generate-docs",
        help="Generate documentation for Git commits (default action)."
    )
    # No specific arguments for this subcommand, as global args apply

    args = parser.parse_args()

    # If no command is specified, default to 'generate-docs'
    if args.command is None:
        handle_generate_docs(args)
    elif args.command == "generate-docs":
        handle_generate_docs(args)
    # Add other command handlers here if you expand the CLI
    # elif args.command == "help":
    #     parser.print_help() # argparse handles this automatically with --help
    # else:
    #     parser.print_help()


if __name__ == "__main__":
    main()
