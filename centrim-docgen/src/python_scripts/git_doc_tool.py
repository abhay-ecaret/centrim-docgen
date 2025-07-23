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

def generate_documentation(diff, commit_message, model_name, watch_mode=False, custom_query=None):
    """
    Prepares a business-focused, language-independent prompt for Ollama to generate 
    human-readable documentation based on the provided Git diff and commit message.
    Uses custom_query if provided.
    """
    truncated_diff = diff[:DIFF_LIMIT] + ("\n... (truncated)" if len(diff) > DIFF_LIMIT else "")

    if custom_query:
        # Use the custom query directly
        prompt = f"""
{custom_query}

Here is the Git diff that you MUST analyze:
```diff
{truncated_diff if truncated_diff else "[No significant diff content provided or diff was empty.]"}
```
"""
    else:
        # Use the improved business-focused prompt
        prompt = f"""
You are a business analyst and technical documentation expert. Your task is to create clear, human-readable documentation that explains the business impact and functional changes of a software commit.

**IMPORTANT GUIDELINES:**
- Focus on WHAT changed from a business/functional perspective, not HOW it was implemented
- Explain WHY the change was made (business reasons, user benefits, problem solving)
- Write for non-technical stakeholders who need to understand the impact
- Do NOT include code snippets, technical implementation details, or programming syntax
- Use clear, professional language that anyone can understand
- Keep it concise (200-300 words maximum)
- Structure with clear headings and bullet points for readability

**ANALYSIS FOCUS AREAS:**
- New features or functionality added
- Bug fixes and their user impact  
- Performance improvements and benefits
- User experience enhancements
- Business process changes
- Security improvements (in business terms)
- Data handling or workflow changes
- Integration with other systems

**OUTPUT FORMAT:**
Use this structure (adapt as needed):

### Summary
Brief overview of what was accomplished in business terms.

### Changes Made
- List functional changes that users or business will notice
- Focus on capabilities, not code

### Business Impact
- Why this change matters
- Who benefits and how
- Problems solved or improvements gained

### User Impact
- Changes users will see or experience
- Any behavior differences they should expect

**REMEMBER:** 
- No code snippets or technical jargon
- Write as if explaining to a project manager or business owner
- Focus on value and outcomes, not technical implementation

Here is the commit message for context:
"{commit_message}"

Here is the Git diff to analyze for business changes:
```diff
{truncated_diff if truncated_diff else "[No significant diff content provided or diff was empty.]"}
```

Generate clear, business-focused documentation following the guidelines above:
"""
    print("[📝] Generating business-focused documentation prompt for Ollama...")
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

### Business Documentation
{generated_docs if generated_docs else "No detailed documentation generated. The changes might be too technical or minimal to provide business impact analysis."}
---
"""
    mode = 'a' if os.path.exists(file_path) else 'w'
    with open(file_path, mode, encoding='utf-8') as f:
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

    print("🚀 Starting Business-Focused Git Documentation Generator 🚀")

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

        generated_docs = generate_documentation(diff, commit_message, model_to_use, args.watch, args.custom_query)
        if not generated_docs:
            print(f"[❌] Failed to generate documentation from Ollama for commit {commit_hash}. Please check Ollama server and model.")
            continue

        append_to_documentation_file(OUTPUT_FILE, commit_hash, author, commit_message, commit_date, generated_docs)

    print("\n🎉 Business Documentation Generation Complete! 🎉")

def main():
    """
    Main function to orchestrate the documentation generation process.
    """
    parser = argparse.ArgumentParser(
        description="Generate business-focused Git commit documentation using Ollama.",
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
        "--watch",
        action="store_true",
        help="Watch raw streaming output from Ollama during generation."
    )
    parser.add_argument(
        "--custom-query",
        type=str,
        help="Provide a custom query/prompt for Ollama. Overrides the default business-focused prompt."
    )

    args = parser.parse_args()
    handle_generate_docs(args)

if __name__ == "__main__":
    main()