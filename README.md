
---

# centrim-docgen

A **Python CLI tool** that automatically generates concise, AI-powered documentation for your Git commits using **local Ollama models** like `phi3` or `mistral`. Generated docs are appended to a Markdown file (`refactoring.md`), helping you document code changes easily and consistently.

---

## ✨ Features

* **Automated Documentation**: Clear, concise documentation for your Git commits.
* **Local Ollama AI**: Uses local models via Ollama for privacy, speed, and zero API costs.
* **Interactive Setup**: Assists with server checks and model pulling.
* **Flexible Diff Analysis**: Document latest or multiple past commits.
* **Real-time Output Watching**: See raw AI output as it's generated.
* **Concise Summaries**: \~300-word AI-generated summaries focusing on key changes and rationale.

---

## 🚀 Getting Started

### Prerequisites

* **Git** – Installed and configured.
* **Python 3** – Installed.
* **Ollama** – Installed and running locally.

#### Setting up Ollama:

1. Install Ollama: [https://ollama.com/](https://ollama.com/)
2. Verify Ollama is running:

```bash
curl http://localhost:11434
```

3. Pull a model (optional, script can help):

```bash
ollama pull phi3
# or
ollama pull mistral
```

---

## 📦 Installation

1. Save the `git_doc_tool.py` script to your project’s root folder.
2. Ensure Ollama server is running locally.

---

## 💡 Usage

Navigate to your Git repository folder in the terminal.

### Generate Docs for Latest Commit:

```bash
python git_doc_tool.py
```

### Specify Model (Recommended):

```bash
python git_doc_tool.py --model phi3
```

### Document Multiple Recent Commits:

```bash
python git_doc_tool.py --diffno 10
```

### View Raw Ollama Output (Debugging / Curiosity):

```bash
python git_doc_tool.py --watch
```

Or combine options:

```bash
python git_doc_tool.py --model phi3 --diffno 3 --watch
```

### Interactive Model Selection:

If `--model` is not specified, the script will:

* List local Ollama models.
* Offer to pull one if none found.

---

## 📄 Output

* Docs are appended to `refactoring.md` in your Git project root.
* Each entry includes:

  * Commit Hash
  * Author & Date
  * Original Commit Message
  * AI-generated summary (\~300 words)

---

## ⚡ Example Output

```markdown
## Commit: a1b2c3d
**Author**: Abhay  
**Date**: 2025-07-22  
**Message**: Refactor payment service to handle retries

**Changes Summary**:
- Refactored payment service to include automatic retry logic.
- Simplified error handling using centralized failure callbacks.
- Improves transaction stability under network failures.

**Rationale**:
Enhances resilience by reducing transaction drop-offs. This change minimizes manual retries by introducing an automated mechanism, improving user experience.
```

---
