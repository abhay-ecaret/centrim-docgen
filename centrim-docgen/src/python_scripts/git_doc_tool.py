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
import re

# Configuration
OLLAMA_URL = "http://localhost:11434" # Base URL for Ollama API
OLLAMA_GENERATE_URL = f"{OLLAMA_URL}/api/generate"
OLLAMA_TAGS_URL = f"{OLLAMA_URL}/api/tags"
 
OUTPUT_FILE = "refactoring.md"
SYSTEM_DOCS_FILE = "system_documentation.md"

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

# --- Structured Git Change Extraction ---
def get_structured_commit_changes(commit_hash, parent_hash=None, file_limit=20, hunk_limit=5, symbol_limit=5):
    """
    Extracts a structured summary of code changes for a commit:
    - Per file: path, status (A/M/D), language, and changed functions/classes (with diff hunks)
    - Returns a dict grouped by language
    """
    # 1. Get changed files and status
    if parent_hash is None:
        parent_hash = f"{commit_hash}~1"
    name_status = run_command(["git", "diff", "--name-status", parent_hash, commit_hash])
    if not name_status:
        print(f"[❌] No changed files found for commit {commit_hash}")
        return {}
    file_lines = name_status.splitlines()
    file_summaries = []
    for line in file_lines[:file_limit]:
        parts = line.strip().split('\t')
        if len(parts) < 2:
            continue
        status, file_path = parts[0], parts[1]
        ext = os.path.splitext(file_path)[1].lower()
        # Language detection
        lang = None
        if ext == '.py':
            lang = 'Python'
        elif ext in ['.js', '.jsx']:
            lang = 'JavaScript'
        elif ext in ['.ts', '.tsx']:
            lang = 'TypeScript'
        elif ext == '.go':
            lang = 'Go'
        elif ext == '.rs':
            lang = 'Rust'
        elif ext == '.php':
            lang = 'PHP'
        elif ext == '.sql':
            lang = 'SQL'
        elif ext in ['.md']:
            lang = 'Documentation'
        elif ext in ['.yml', '.yaml']:
            lang = 'Configuration'
        else:
            lang = ext[1:].upper() if ext else 'Other'
        # Only process source/config/docs files
        if lang in ['Other', '']:
            continue
        # 2. Get diff hunks for this file
        diff_hunks = run_command([
            "git", "diff", "-U3", "--function-context", parent_hash, commit_hash, "--", file_path
        ])
        if not diff_hunks:
            continue
        # 3. Extract changed symbols (functions/classes)
        symbol_pattern = re.compile(r'^@@.*?@@[ ]*(def |function |class )?([\w_]+)?', re.MULTILINE)
        symbols = []
        for match in symbol_pattern.finditer(diff_hunks):
            symbol_type = 'unknown'
            if match.group(1):
                if 'def' in match.group(1):
                    symbol_type = 'function'
                elif 'class' in match.group(1):
                    symbol_type = 'class'
                elif 'function' in match.group(1):
                    symbol_type = 'function'
            symbol_name = match.group(2) or ''
            # Extract the hunk for this symbol
            hunk_start = match.start()
            hunk_end = diff_hunks.find('@@', hunk_start + 2)
            if hunk_end == -1:
                hunk_end = len(diff_hunks)
            hunk = diff_hunks[hunk_start:hunk_end]
            symbols.append({
                'type': symbol_type,
                'name': symbol_name,
                'diff': hunk[:1000] + ('\n... (truncated)' if len(hunk) > 1000 else '')
            })
            if len(symbols) >= symbol_limit:
                break
        file_summaries.append({
            'file': file_path,
            'status': status,
            'language': lang,
            'changed_symbols': symbols[:symbol_limit],
            'diff_summary': diff_hunks[:2000] + ('\n... (truncated)' if len(diff_hunks) > 2000 else '')
        })
    # 4. Group by language
    lang_map = {}
    for f in file_summaries:
        lang_map.setdefault(f['language'], []).append(f)
    return lang_map

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

def get_file_content_before_commit(file_path, commit_hash):
    """
    Get the content of a file before the commit for context.
    """
    try:
        content = run_command(["git", "show", f"{commit_hash}~1:{file_path}"])
        return content if content else ""
    except:
        return ""

def analyze_diff_context(diff):
    """
    Analyze the diff to understand what type of changes are being made.
    Returns context information to help optimize the prompt.
    """
    if not diff:
        return {"type": "unknown", "files": [], "languages": []}
    
    # Extract file types and paths
    file_pattern = r'diff --git a/(.*?) b/(.*?)(?:\n|$)'
    files = re.findall(file_pattern, diff)
    file_paths = [f[0] for f in files]
    
    # Determine primary languages/frameworks
    languages = set()
    frameworks = set()
    
    for file_path in file_paths:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.py']:
            languages.add('Python')
        elif ext in ['.js', '.jsx']:
            languages.add('JavaScript')
            if 'react' in file_path.lower():
                frameworks.add('React')
        elif ext in ['.ts', '.tsx']:
            languages.add('TypeScript')
        elif ext in ['.go']:
            languages.add('Go')
        elif ext in ['.rs']:
            languages.add('Rust')
        elif ext in ['.sql']:
            languages.add('SQL')
        elif ext in ['.md']:
            languages.add('Documentation')
        elif ext in ['.yml', '.yaml']:
            languages.add('Configuration')
    
    # Analyze change patterns
    change_type = "general"
    # Dependency changes
    if "package.json" in file_paths or "requirements.txt" in file_paths or "go.mod" in file_paths:
        change_type = "dependencies"
    # Test changes
    elif any("test" in fp.lower() for fp in file_paths):
        change_type = "testing"
    # Config changes
    elif any("config" in fp.lower() or "env" in fp.lower() for fp in file_paths):
        change_type = "configuration"
    # Docs changes
    elif "README" in diff or "CHANGELOG" in diff:
        change_type = "documentation"
    else:
        # Look for additions and deletions of classes/functions/defs
        has_add = any(s in diff for s in ["+class ", "+function ", "+def "])
        has_del = any(s in diff for s in ["-class ", "-function ", "-def "])
        if has_add and has_del:
            change_type = "feature"
        elif has_add:
            change_type = "feature"
        elif has_del:
            change_type = "removal"
        elif "fix" in diff.lower() or "bug" in diff.lower():
            change_type = "bugfix"
    return {
        "type": change_type,
        "files": file_paths[:10],  # Limit to first 10 files
        "languages": list(languages),
        "frameworks": list(frameworks)
    }

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

def ensure_model_available(model_name):
    """
    Ensures the specified model is available locally.
    Returns True if model is available, False otherwise.
    """
    if not model_name:
        print("[❌] No model specified.")
        return False
        
    print(f"[⚙️] Checking if model '{model_name}' is available...")
    available_models = get_available_ollama_models()
    
    if model_name in available_models:
        print(f"[✅] Model '{model_name}' is available.")
        return True
    else:
        print(f"[⚠️] Model '{model_name}' not found locally. Attempting to pull...")
        return pull_ollama_model(model_name)

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

def create_simple_prompt(diff, commit_message, commit_hash, diff_limit):
    """
    Create a super simple, direct prompt that AI models can easily understand.
    Focus on exactly what you want: what changed, which files, what was added/deleted/updated.
    """
    # Truncate diff if too long
    truncated_diff = diff[:diff_limit] + ("\n... (diff truncated)" if len(diff) > diff_limit else "")
    
    # Extract file names from diff for context
    file_pattern = r'diff --git a/(.*?) b/'
    changed_files = re.findall(file_pattern, diff)
    files_list = ", ".join(changed_files[:5]) + ("..." if len(changed_files) > 5 else "")
    
    prompt = f"""Commit: {commit_message}

Files changed: {files_list}

Look at this git diff and tell me:
- What changed
- Which files were modified  
- What was added, deleted, or updated

Be brief and clear.

```diff
{truncated_diff}
```"""

    return prompt

def generate_documentation(diff, commit_message, commit_hash, model_name, watch_mode=False, diff_limit=5000):
    """
    Generate simple, clear documentation using the optimized prompt.
    """
    print(f"[📝] Generating simple documentation for commit {commit_hash[:8]}...")
    prompt = create_simple_prompt(diff, commit_message, commit_hash, diff_limit)
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

## Commit: {commit_hash[:8]}

**Author:** {author}  
**Date:** {commit_date}  
**Message:** {commit_message}

{generated_docs if generated_docs else "No documentation generated."}

---
"""
    
    # Handle file creation with header
    if not os.path.exists(file_path):
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("# Git Commit Documentation\n\n")
            f.write("This file contains developer-focused documentation for each commit.\n\n")
    
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(doc_entry)
    print(f"[✅] Documentation for commit {commit_hash} successfully added to {file_path}.")


def handle_generate_docs(args):
    """Handles the documentation generation with all parameters from command line."""
    if not check_ollama_status():
        print("[🛑] Ollama server is not running. Please start it to proceed.")
        return

    # Use default model if none specified
    model_to_use = args.model if args.model else 'phi3'
    
    if not ensure_model_available(model_to_use):
        print(f"[🛑] Model '{model_to_use}' is not available and could not be pulled. Exiting.")
        return

    print("🚀 Starting Simple Git Documentation Generator 🚀")

    # Determine number of diffs to process
    num_diffs_to_process = 1 
    if args.diffno is not None:
        num_diffs_to_process = args.diffno
        print(f"[⚙️] Processing {num_diffs_to_process} diff(s) as specified by --diffno.")
    elif not os.path.exists(OUTPUT_FILE):
        num_diffs_to_process = 5 
        print(f"[⚙️] No existing documentation file found. Defaulting to processing the last {num_diffs_to_process} diffs.")
    else:
        print(f"[⚙️] Existing documentation file found. Defaulting to processing only the latest diff.")

    recent_commits = get_recent_commit_info(num_diffs_to_process)
    if not recent_commits:
        print("[🛑] Exiting: Could not get any commit information.")
        return

    documented_hashes = read_documented_hashes(OUTPUT_FILE)

    for commit_hash, author, commit_message, commit_date in recent_commits:
        if commit_hash in documented_hashes:
            print(f"[ℹ️] Commit {commit_hash} is already documented in {OUTPUT_FILE}. Skipping.")
            continue

        print(f"\n--- Processing new commit: {commit_hash} ---")

        diff = get_git_diff(commit_hash)
        if not diff:
            print(f"[ℹ️] No significant diff found for commit {commit_hash}. Skipping documentation generation.")
            continue

        generated_docs = generate_documentation(
            diff,
            commit_message,
            commit_hash,
            model_to_use,
            args.watch,
            args.diff_limit
        )
        if not generated_docs:
            print(f"[❌] Failed to generate documentation from Ollama for commit {commit_hash}. Please check Ollama server and model.")
            continue

        append_to_documentation_file(OUTPUT_FILE, commit_hash, author, commit_message, commit_date, generated_docs)

    print("\n🎉 Documentation Generation Complete! 🎉")

def main():
    """
    Main function to orchestrate the documentation generation process.
    """
    parser = argparse.ArgumentParser(
        description="Generate simple Git commit documentation using Ollama.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument(
        "--model",
        type=str,
        help="Specify the Ollama model to use (e.g., 'phi3', 'mistral').\n"
             "If not provided, defaults to 'phi3'."
    )
    parser.add_argument(
        "--diffno",
        type=int,
        help="Number of recent diffs to process. Overrides default behavior.\n"
             "Default: 1 (latest commit) if 'refactoring.md' exists, 5 otherwise."
    )
    parser.add_argument(
        "--diff-limit",
        type=int,
        default=6000,
        help="Character limit for Git diff content sent to the AI model.\n"
             "Prevents model overload with very large diffs. (Default: 6000)"
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch raw streaming output from Ollama during generation."
    )

    args = parser.parse_args()
    handle_generate_docs(args)

if __name__ == "__main__":
    main()