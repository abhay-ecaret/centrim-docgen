
# 🚀 Centrim DocGen

Tired of writing documentation after coding?  
Wish your Git commits could just... document themselves?  

Meet **Centrim DocGen** — a VS Code extension that automatically generates concise, AI-powered documentation for your Git commits using local AI models like **phi3**, **mistral**, or even **tinyllama**. It saves everything to a neat `refactoring.md` file in your repo.

---

## ✨ Features

- **AI-Powered Docs** — Get clear, to-the-point summaries of your Git commits.
- **Runs Locally with Ollama** — No internet required after setup; keeps your code private.
- **Flexible Doc Generation** — Document your latest commit or multiple recent ones.
- **Custom Prompts** — Tell the AI how you want your docs to sound.
- **Live Watch Mode** — See AI output live as it generates.
- **Smooth VS Code Integration** — Accessible directly from your VS Code sidebar.

---

## 🛠️ Setup Guide

### 1️⃣ Prerequisites

- [Visual Studio Code](https://code.visualstudio.com/)
- [Git](https://git-scm.com/)
- [Python 3](https://www.python.org/)
- [Ollama (Local AI Models)](https://ollama.com/)

## 📦 Quick Build & Install

```bash
npm install -g @vscode/vsce
git clone git@github-work:abhay-ecaret/centrim-docgen.git
cd centrim-docgen
vsce package
code --install-extension centrim-docgen-*.vsix
```

Check if Ollama is running:
```bash
curl http://localhost:11434
```
If you see a JSON response — you're good!

Pull an AI model:
```
ollama pull phi3
# or
ollama pull mistral
# or
ollama pull tinyllama
```
2️⃣ Install Extension

    Get the .vsix file from your team (e.g. centrim-docgen-X.X.X.vsix).

    Open VS Code.

    Go to Extensions (Ctrl+Shift+X).

    Click the ... menu (top-right) → Install from VSIX...

    Select your .vsix file and install.

🚀 How to Use

    Open your Git project in VS Code.

    Click the Centrim DocGen icon in the Activity Bar.

    Click Generate Docs.

    Follow the prompts:

        Number of commits to document

        Choose AI model

        Enable watch mode?

        Custom prompt? (optional)

    Sit back! Your documentation appears in refactoring.md in your repo.

📄 Example Output

    Commit summaries

    Refactoring notes

    Optional technical explanations (using custom prompts)
