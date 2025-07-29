import re
import os
from ollama_utils import send_to_ollama

OUTPUT_FILE = "refactoring.md"

def create_simple_prompt(diff, commit_message, commit_hash, diff_limit):
    truncated_diff = diff[:diff_limit] + ("\n... (diff truncated)" if len(diff) > diff_limit else "")
    file_pattern = r'diff --git a/(.*?) b/'
    changed_files = re.findall(file_pattern, diff)
    files_list = ", ".join(changed_files[:5]) + ("..." if len(changed_files) > 5 else "")
    prompt = f"""Commit: {commit_message}\n\nFiles changed: {files_list}\n\nLook at this git diff and tell me:\n- What changed\n- Which files were modified  \n- What was added, deleted, or updated\n\nBe brief and clear.\n\n```diff\n{truncated_diff}\n```"""
    return prompt

def generate_documentation(diff, commit_message, commit_hash, model_name, watch_mode=False, diff_limit=5000):
    print(f"[📝] Generating simple documentation for commit {commit_hash[:8]}...")
    prompt = create_simple_prompt(diff, commit_message, commit_hash, diff_limit)
    documentation = send_to_ollama(prompt, model_name, watch_mode)
    return documentation

def append_to_documentation_file(file_path, commit_hash, author, commit_message, commit_date, generated_docs):
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
    if not os.path.exists(file_path):
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("# Git Commit Documentation\n\n")
            f.write("This file contains developer-focused documentation for each commit.\n\n")
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(doc_entry)
    print(f"[✅] Documentation for commit {commit_hash} successfully added to {file_path}.")
