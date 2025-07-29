import argparse
import os
from git_utils import get_recent_commit_info, get_git_diff
from ollama_utils import check_ollama_status, ensure_model_available
from docgen import generate_documentation, append_to_documentation_file, OUTPUT_FILE

def read_documented_hashes(file_path):
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

def handle_generate_docs(args):
    if not check_ollama_status():
        print("[🛑] Ollama server is not running. Please start it to proceed.")
        return
    # Only allow the four compliant models
    allowed_models = ['phi3:medium', 'mistral:7b', 'deepseek-coder:6.7b', 'qwen2.5-coder:7b']
    model_to_use = args.model if args.model in allowed_models else 'phi3:medium'
    if not ensure_model_available(model_to_use):
        print(f"[🛑] Model '{model_to_use}' is not available and could not be pulled. Exiting.")
        return
    print("🚀 Starting Simple Git Documentation Generator 🚀")
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
    parser = argparse.ArgumentParser(
        description="Generate simple Git commit documentation using Ollama.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--model",
        type=str,
        help="Specify the Ollama model to use (e.g., 'phi3', 'mistral').\nIf not provided, defaults to 'phi3'."
    )
    parser.add_argument(
        "--diffno",
        type=int,
        help="Number of recent diffs to process. Overrides default behavior.\nDefault: 1 (latest commit) if 'refactoring.md' exists, 5 otherwise."
    )
    parser.add_argument(
        "--diff-limit",
        type=int,
        default=6000,
        help="Character limit for Git diff content sent to the AI model.\nPrevents model overload with very large diffs. (Default: 6000)"
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
