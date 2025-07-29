import os
import subprocess
import re

def run_command(command, cwd=None):
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

def get_structured_commit_changes(commit_hash, parent_hash=None, file_limit=20, hunk_limit=5, symbol_limit=5):
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
        if lang in ['Other', '']:
            continue
        diff_hunks = run_command([
            "git", "diff", "-U3", "--function-context", parent_hash, commit_hash, "--", file_path
        ])
        if not diff_hunks:
            continue
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
    lang_map = {}
    for f in file_summaries:
        lang_map.setdefault(f['language'], []).append(f)
    return lang_map

def get_recent_commit_info(num_commits):
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
    print(f"[🔍] Fetching git diff for commit {commit_hash}...")
    diff = run_command(["git", "diff", f"{commit_hash}~1", commit_hash])
    if diff:
        print(f"[✅] Diff fetched ({len(diff)} characters).")
    else:
        print("[ℹ️] No diff found for this commit (e.g., initial commit or merge commit without changes).")
    return diff

def get_file_content_before_commit(file_path, commit_hash):
    try:
        content = run_command(["git", "show", f"{commit_hash}~1:{file_path}"])
        return content if content else ""
    except:
        return ""
