import * as vscode from 'vscode';
import * as path from 'path';
import { spawn } from 'child_process';

// Define a simple TreeItem for our sidebar view
class DocGenTreeItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState,
        public readonly command?: vscode.Command,
        iconId: string = 'rocket' // Default icon for action items
    ) {
        super(label, collapsibleState);
        this.tooltip = this.label;
        // Default description, can be overridden by specific items
        this.description = "Click to configure and generate";
        this.iconPath = new vscode.ThemeIcon(iconId);
    }
}

// Define a TreeDataProvider for our sidebar view
class DocGenTreeDataProvider implements vscode.TreeDataProvider<DocGenTreeItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<DocGenTreeItem | undefined | null | void> = new vscode.EventEmitter<DocGenTreeItem | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<DocGenTreeItem | undefined | null | void> = this._onDidChangeTreeData.event;

    // Status for the sidebar view, controlling what is displayed
    private _status: 'idle' | 'checking_ollama' | 'ollama_ready' | 'ollama_not_ready' | 'generating' | 'generation_complete' = 'idle';

    constructor() {
        // Initial check for Ollama status when the sidebar is loaded
        this.updateStatus('checking_ollama');
        this.checkOllamaStatusInSidebar(); // Perform initial check
    }

    public updateStatus(newStatus: typeof this._status) {
        this._status = newStatus;
        this._onDidChangeTreeData.fire(); // Notify VS Code to refresh the tree view
    }

    getTreeItem(element: DocGenTreeItem): vscode.TreeItem {
        return element;
    }

    getChildren(element?: DocGenTreeItem): Thenable<DocGenTreeItem[]> {
        if (element) {
            return Promise.resolve([]); // No children for now
        }

        const items: DocGenTreeItem[] = [];
        const openConfigCommand: vscode.Command = {
            command: 'centrim-docgen.openConfigPanel',
            title: 'Open Documentation Configuration',
            tooltip: 'Open the panel to configure and generate documentation'
        };

        switch (this._status) {
            case 'checking_ollama':
                items.push(new DocGenTreeItem(
                    'Checking Ollama Status...',
                    vscode.TreeItemCollapsibleState.None,
                    undefined, // No command for this state
                    'sync~spin' // Spinning icon
                ));
                items[0].description = 'Please wait';
                break;
            case 'ollama_ready':
                items.push(new DocGenTreeItem(
                    'Generate Documentation',
                    vscode.TreeItemCollapsibleState.None,
                    openConfigCommand,
                    'file-text'
                ));
                items[0].description = 'Ollama is Ready!';
                items[0].tooltip = 'Click to open configuration and generate documentation.';
                break;
            case 'ollama_not_ready':
                items.push(new DocGenTreeItem(
                    'Ollama Not Running',
                    vscode.TreeItemCollapsibleState.None,
                    { command: 'centrim-docgen.openSettings', title: 'Open Settings' },
                    'warning'
                ));
                items[0].description = 'Click to open settings and configure Ollama URL.';
                items[0].tooltip = 'Ollama server is unreachable. Please start it or check settings.';
                break;
            case 'generating':
                items.push(new DocGenTreeItem(
                    'Generating Documentation...',
                    vscode.TreeItemCollapsibleState.None,
                    undefined, // No command during generation
                    'tools' // Tool icon, or 'loading~spin' if it exists, 'sync~spin'
                ));
                items[0].description = 'Please wait...';
                break;
            case 'generation_complete':
                items.push(new DocGenTreeItem(
                    'Documentation Generated',
                    vscode.TreeItemCollapsibleState.None,
                    openConfigCommand,
                    'check'
                ));
                items[0].description = 'Click to generate again.';
                break;
            default: // 'idle' or unhandled states
                items.push(new DocGenTreeItem(
                    'Generate Documentation',
                    vscode.TreeItemCollapsibleState.None,
                    openConfigCommand,
                    'rocket'
                ));
                items[0].description = 'Open configuration panel.';
                break;
        }

        // Add a manual status check command, always visible
        items.push(new DocGenTreeItem(
            'Refresh Ollama Status',
            vscode.TreeItemCollapsibleState.None,
            { command: 'centrim-docgen.checkStatus', title: 'Check Ollama Status Now' },
            'sync' // Refresh icon
        ));

        return Promise.resolve(items);
    }

    // Helper to probe multiple Ollama URLs and update sidebar
    private async checkOllamaStatusInSidebar() {
        const userUrl = vscode.workspace.getConfiguration('centrimDocGen').get<string>('ollamaUrl');
        const candidates = [
            userUrl,
            'http://localhost:11434',
            'http://127.0.0.1:11434',
        ].filter((u): u is string => typeof u === 'string' && !!u);
        let foundUrl: string | null = null;
        for (const url of candidates) {
            try {
                const response = await fetch(url);
                if (response.ok) {
                    foundUrl = url;
                    break;
                }
            } catch (e) { }
        }
        if (foundUrl) {
            this.updateStatus('ollama_ready');
            // Save detected URL to workspace config for future use
            await vscode.workspace.getConfiguration('centrimDocGen').update('ollamaUrl', foundUrl, vscode.ConfigurationTarget.Workspace);
        } else {
            this.updateStatus('ollama_not_ready');
        }
    }
}


class DocGenConfigPanel {
    public static currentPanel: DocGenConfigPanel | undefined;
    private readonly _panel: vscode.WebviewPanel;
    private readonly _extensionUri: vscode.Uri;
    private _disposables: vscode.Disposable[] = [];
    private _treeDataProvider: DocGenTreeDataProvider; // Reference to the sidebar data provider

    public static createOrShow(extensionUri: vscode.Uri, treeDataProvider: DocGenTreeDataProvider) {
        const column = vscode.window.activeTextEditor
            ? vscode.window.activeTextEditor.viewColumn
            : undefined;

        if (DocGenConfigPanel.currentPanel) {
            DocGenConfigPanel.currentPanel._panel.reveal(column);
            DocGenConfigPanel.currentPanel._treeDataProvider = treeDataProvider; // Update ref if needed
            DocGenConfigPanel.currentPanel._checkOllamaStatus(); // Re-check status on reveal
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            'centrimDocGenConfig',
            'Centrim DocGen Configuration',
            column || vscode.ViewColumn.One,
            {
                enableScripts: true,
                localResourceRoots: [vscode.Uri.joinPath(extensionUri, 'media')]
            }
        );

        DocGenConfigPanel.currentPanel = new DocGenConfigPanel(panel, extensionUri, treeDataProvider);
    }

    private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri, treeDataProvider: DocGenTreeDataProvider) {
        this._panel = panel;
        this._extensionUri = extensionUri;
        this._treeDataProvider = treeDataProvider; // Assign the reference

        this._update();

        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);

        this._panel.webview.onDidReceiveMessage(
            message => {
                switch (message.command) {
                    case 'generateDocs':
                        this._generateDocs(message.config);
                        return;
                    case 'checkOllamaStatus':
                        this._checkOllamaStatus();
                        return;
                    case 'stopGeneration':
                        this.stopGeneration();
                        return;
                }
            },
            null,
            this._disposables
        );
    }

    // Probe multiple Ollama URLs and update config/UI
    private async _checkOllamaStatus() {
        const userUrl = vscode.workspace.getConfiguration('centrimDocGen').get<string>('ollamaUrl');
        const candidates = [
            userUrl,
            'http://localhost:11434',
            'http://127.0.0.1:11434',
        ].filter((u): u is string => typeof u === 'string' && !!u);
        let foundUrl = null;
        for (const url of candidates) {
            try {
                const response = await fetch(url);
                if (response.ok) {
                    foundUrl = url;
                    break;
                }
            } catch (e) { }
        }
        if (foundUrl) {
            this._panel.webview.postMessage({
                command: 'ollamaStatus',
                isRunning: true,
                url: foundUrl
            });
            this._treeDataProvider.updateStatus('ollama_ready');
            await vscode.workspace.getConfiguration('centrimDocGen').update('ollamaUrl', foundUrl, vscode.ConfigurationTarget.Workspace);
        } else {
            this._panel.webview.postMessage({
                command: 'ollamaStatus',
                isRunning: false
            });
            this._treeDataProvider.updateStatus('ollama_not_ready');
        }
    }

    private _currentPythonProcess: any = null;

    private async _generateDocs(config: any) {
        // Probe Ollama URL before running
        const userUrl = vscode.workspace.getConfiguration('centrimDocGen').get<string>('ollamaUrl');
        const candidates = [
            userUrl,
            'http://localhost:11434',
            'http://127.0.0.1:11434',
        ].filter((u): u is string => typeof u === 'string' && !!u);
        let foundUrl: string | null = null;
        for (const url of candidates) {
            try {
                const response = await fetch(url);
                if (response.ok) {
                    foundUrl = url;
                    break;
                }
            } catch (e) { }
        }
        if (!foundUrl) {
            vscode.window.showErrorMessage('No running Ollama server found at any known URL. Please start Ollama and try again.');
            this._panel.webview.postMessage({ command: 'generationComplete', success: false, error: 'No Ollama server found.' });
            this._treeDataProvider.updateStatus('ollama_not_ready');
            return;
        }
        await vscode.workspace.getConfiguration('centrimDocGen').update('ollamaUrl', foundUrl, vscode.ConfigurationTarget.Workspace);
        const outputChannel = vscode.window.createOutputChannel("Centrim DocGen");
        outputChannel.show(true);
        outputChannel.appendLine("--- Centrim DocGen Session Started ---");

        // Update sidebar status
        this._treeDataProvider.updateStatus('generating');

        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders || workspaceFolders.length === 0) {
            vscode.window.showErrorMessage("No workspace folder open. Please open a Git repository folder.");
            outputChannel.appendLine("Error: No workspace folder open.");
            outputChannel.appendLine("--- Centrim DocGen Session Ended ---");
            this._panel.webview.postMessage({ command: 'generationComplete', success: false, error: "No workspace folder open." });
            this._treeDataProvider.updateStatus('idle'); // Revert to idle
            return;
        }

        const repoPath = workspaceFolders[0].uri.fsPath;

        // Prepare arguments based on config
        const args = [
            path.join(this._extensionUri.fsPath, 'src', 'python_scripts', 'main.py')
        ];

        if (config.diffno) {
            args.push('--diffno', config.diffno.toString());
        }

        if (config.model) {
            args.push('--model', config.model);
        }

        // Add diff-limit argument from webview config
        if (config.diffLimit) {
            args.push('--diff-limit', config.diffLimit.toString());
        } else {
            // Optionally, if not set in the webview, use the default from VS Code settings
            const defaultDiffLimit = vscode.workspace.getConfiguration('centrimDocgen').get<number>('diffLimit');
            if (defaultDiffLimit !== undefined) {
                args.push('--diff-limit', defaultDiffLimit.toString());
            }
        }

        if (config.watch) {
            args.push('--watch');
        }


        const pythonExec = process.platform === 'win32' ? 'python' : 'python3';

        outputChannel.appendLine(`Executing: ${pythonExec} ${args.join(' ')}`);
        outputChannel.appendLine(`In directory: ${repoPath}`);
        outputChannel.appendLine("------------------------------------");

        // Update webview with progress
        this._panel.webview.postMessage({
            command: 'generationStarted'
        });

        try {
            const pythonProcess = spawn(pythonExec, args, { cwd: repoPath });
            this._currentPythonProcess = pythonProcess;

            pythonProcess.stdout.on('data', (data) => {
                outputChannel.append(data.toString());
                this._panel.webview.postMessage({
                    command: 'outputUpdate',
                    data: data.toString()
                });
            });

            pythonProcess.stderr.on('data', (data) => {
                outputChannel.append(data.toString());
                this._panel.webview.postMessage({
                    command: 'errorUpdate',
                    data: data.toString()
                });
                vscode.window.showErrorMessage(`Centrim DocGen Error: ${data.toString().split('\n')[0]}`);
            });

            pythonProcess.on('close', (code) => {
                this._currentPythonProcess = null;
                if (code === 0) {
                    vscode.window.showInformationMessage('Centrim DocGen: Documentation generated successfully!');
                    outputChannel.appendLine("Centrim DocGen: Script finished successfully.");
                    vscode.commands.executeCommand('workbench.files.action.refreshExplorer');
                    this._panel.webview.postMessage({
                        command: 'generationComplete',
                        success: true
                    });
                    this._treeDataProvider.updateStatus('generation_complete'); // Update sidebar status
                } else {
                    vscode.window.showErrorMessage(`Centrim DocGen: Script exited with code ${code}. Check output channel for details.`);
                    outputChannel.appendLine(`Centrim DocGen: Script exited with code ${code}.`);
                    this._panel.webview.postMessage({
                        command: 'generationComplete',
                        success: false,
                        code: code
                    });
                    this._treeDataProvider.updateStatus('ollama_ready'); // Revert to ready state on failure
                }
                outputChannel.appendLine("--- Centrim DocGen Session Ended ---");
            });

            pythonProcess.on('error', (err) => {
                this._currentPythonProcess = null;
                vscode.window.showErrorMessage(`Failed to start Python script: ${err.message}. Make sure Python is installed and in your PATH.`);
                outputChannel.appendLine(`Error starting Python script: ${err.message}`);
                outputChannel.appendLine("--- Centrim DocGen Session Ended ---");
                this._panel.webview.postMessage({
                    command: 'generationComplete',
                    success: false,
                    error: err.message
                });
                this._treeDataProvider.updateStatus('ollama_not_ready'); // Indicate issue with Ollama/Python
            });

        } catch (error: any) {
            this._currentPythonProcess = null;
            vscode.window.showErrorMessage(`An unexpected error occurred: ${error.message}`);
            outputChannel.appendLine(`Unexpected error: ${error.message}`);
            outputChannel.appendLine("--- Centrim DocGen Session Ended ---");
            this._panel.webview.postMessage({
                command: 'generationComplete',
                success: false,
                error: error.message
            });
            this._treeDataProvider.updateStatus('ollama_not_ready'); // Indicate issue
        }
    }
    public stopGeneration() {
        if (this._currentPythonProcess) {
            this._currentPythonProcess.kill('SIGTERM');
            this._currentPythonProcess = null;
        }
    }

    public dispose() {
        DocGenConfigPanel.currentPanel = undefined;
        this._panel.dispose();
        while (this._disposables.length) {
            const x = this._disposables.pop();
            if (x) {
                x.dispose();
            }
        }
    }

    private _update() {
        const webview = this._panel.webview;
        this._panel.title = 'Centrim DocGen Configuration';
        this._panel.webview.html = this._getHtmlForWebview(webview);
    }

    private _getHtmlForWebview(webview: vscode.Webview) {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Centrim DocGen Configuration</title>
    <style>
        * {
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: var(--vscode-editor-background);
            color: var(--vscode-editor-foreground);
            line-height: 1.6;
        }
        
        .container {
            max-width: 800px;
            margin: 0 auto;
        }
        
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            border: 1px solid var(--vscode-panel-border);
            border-radius: 8px;
            background: var(--vscode-panel-background);
        }
        
        .header h1 {
            margin: 0 0 10px 0;
            color: var(--vscode-textLink-foreground);
            font-size: 24px;
        }
        
        .header p {
            margin: 0;
            opacity: 0.8;
        }
        
        .status-bar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 6px;
            background: var(--vscode-inputValidation-infoBorder);
            color: var(--vscode-inputValidation-infoForeground);
        }
        
        .status-indicator {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: var(--vscode-inputValidation-errorBorder);
        }
        
        .status-dot.running {
            background: var(--vscode-inputValidation-infoBorder);
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        .form-section {
            background: var(--vscode-panel-background);
            border: 1px solid var(--vscode-panel-border);
            border-radius: 8px;
            padding: 25px;
            margin-bottom: 20px;
        }
        
        .form-section h3 {
            margin: 0 0 20px 0;
            color: var(--vscode-textLink-foreground);
            font-size: 18px;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-group:last-child {
            margin-bottom: 0;
        }
        
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
            color: var(--vscode-input-foreground);
        }
        
        input, select, textarea {
            width: 100%;
            padding: 10px 12px;
            border: 1px solid var(--vscode-input-border);
            border-radius: 4px;
            background: var(--vscode-input-background);
            color: var(--vscode-input-foreground);
            font-size: 14px;
            font-family: inherit;
        }
        
        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: var(--vscode-focusBorder);
        }
        
        textarea {
            resize: vertical;
            min-height: 80px;
        }
        
        .checkbox-group {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .checkbox-group input[type="checkbox"] {
            width: auto;
            margin: 0;
        }
        
        .help-text {
            font-size: 12px;
            color: var(--vscode-input-placeholderForeground);
            margin-top: 5px;
        }
        
        .button-group {
            display: flex;
            gap: 15px;
            justify-content: center;
            margin-top: 30px;
        }
        
        button {
            padding: 12px 24px;
            border: none;
            border-radius: 4px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .btn-primary {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
        }
        
        .btn-primary:hover {
            background: var(--vscode-button-hoverBackground);
        }
        
        .btn-secondary {
            background: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
        }
        
        .btn-secondary:hover {
            background: var(--vscode-button-secondaryHoverBackground);
        }
        
        .btn-primary:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        
        .progress-section {
            display: none;
            background: var(--vscode-panel-background);
            border: 1px solid var(--vscode-panel-border);
            border-radius: 8px;
            padding: 20px;
            margin-top: 20px;
        }
        
        .progress-bar {
            width: 100%;
            height: 4px;
        // Only allow the four compliant models
        const allowedModels = ['phi3:medium', 'mistral:7b', 'deepseek-coder:6.7b', 'qwen2.5-coder:7b'];
        let selectedModel = config.model;
        if (!allowedModels.includes(selectedModel)) {
            selectedModel = 'phi3:medium';
        }
        args.push('--model', selectedModel);
            overflow: hidden;
            margin-bottom: 10px;
        }
        
        .progress-fill {
            height: 100%;
            background: var(--vscode-button-background);
            width: 0%;
            animation: indeterminate 2s infinite;
        }
        
        @keyframes indeterminate {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }
        
        .output-area {
            max-height: 200px;
            overflow-y: auto;
            background: var(--vscode-terminal-background);
            color: var(--vscode-terminal-foreground);
            font-family: var(--vscode-editor-font-family), monospace;
            font-size: 12px;
            padding: 10px;
            border-radius: 4px;
            white-space: pre-wrap;
        }
        
        .model-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 10px;
            margin-top: 10px;
        }
        
        .model-option {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px;
            border: 1px solid var(--vscode-input-border);
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .model-option:hover {
            background: var(--vscode-list-hoverBackground);
        }
        
        .model-option input[type="radio"] {
            width: auto;
            margin: 0;
        }
        
        .error-message {
            background: var(--vscode-inputValidation-errorBackground);
            color: var(--vscode-inputValidation-errorForeground);
            border: 1px solid var(--vscode-inputValidation-errorBorder);
            padding: 10px;
            border-radius: 4px;
            margin-top: 10px;
        }
        
        .success-message {
            background: var(--vscode-inputValidation-infoBackground);
            color: var(--vscode-inputValidation-infoForeground);
            border: 1px solid var(--vscode-inputValidation-infoBorder);
            padding: 10px;
            border-radius: 4px;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Centrim DocGen</h1>
            <p>Generate business-focused Git commit documentation using Ollama</p>
        </div>
        
        <div class="status-bar">
            <div class="status-indicator">
                <div class="status-dot" id="statusDot"></div>
                <span id="statusText">Checking Ollama status...</span>
            </div>
            <button class="btn-secondary" onclick="checkOllamaStatus()">Refresh Status</button>
        </div>
        
        <form id="configForm">
            <div class="form-section">
                <h3>📊 Processing Configuration</h3>
                
                <div class="form-group">
                    <label for="diffno">Number of Recent Commits to Process</label>
                    <input type="number" id="diffno" name="diffno" min="1" max="50" placeholder="Leave empty for default behavior">
                    <div class="help-text">Default: 1 if refactoring.md exists, 5 otherwise</div>
                </div>

                <div class="form-group">
                    <label for="diffLimit">Diff Character Limit for AI</label>
                    <input type="number" id="diffLimit" name="diffLimit" min="1000" max="50000" placeholder="e.g., 5000">
                    <div class="help-text">Maximum characters of Git diff to send to the AI model. Larger diffs may be truncated. Default: 5000.</div>
                </div>
            </div>
            
            <div class="form-section">
                <h3>🤖 Model Configuration</h3>
                
                <div class="form-group">
                    <label>Ollama Model</label>
                    <div class="model-grid">
                        <div class="model-option">
                            <input type="radio" id="phi3medium" name="model" value="phi3:medium" checked>
                            <label for="phi3medium">Phi3:Medium (MIT, Microsoft-backed)</label>
                        </div>
                        <div class="model-option">
                            <input type="radio" id="mistral7b" name="model" value="mistral:7b">
                            <label for="mistral7b">Mistral 7B (Apache 2.0)</label>
                        </div>
                        <div class="model-option">
                            <input type="radio" id="deepseekcoder" name="model" value="deepseek-coder:6.7b">
                            <label for="deepseekcoder">DeepSeek Coder 6.7B (Apache 2.0)</label>
                        </div>
                        <div class="model-option">
                            <input type="radio" id="qwen25coder" name="model" value="qwen2.5-coder:7b">
                            <label for="qwen25coder">Qwen2.5 Coder 7B</label>
                        </div>
                    </div>
                    <div class="help-text">Only the above compliant models are allowed. Model will be automatically downloaded if not available locally.</div>
                </div>
            </div>
            
            <div class="form-section">
                <h3>⚙️ Advanced Options</h3>
                <div class="form-group">
                    <div class="checkbox-group">
                        <input type="checkbox" id="watch" name="watch">
                        <label for="watch">Enable Watch Mode (Show raw Ollama output)</label>
                    </div>
                    <div class="help-text">Useful for debugging or seeing detailed processing</div>
                </div>
            </div>
            <div class="button-group">
                <button type="button" class="btn-secondary" onclick="resetForm()">Reset Form</button>
                <button type="submit" class="btn-primary" id="generateBtn">
                    🚀 Generate Documentation
                </button>
                <button type="button" class="btn-secondary" id="stopBtn" style="display:none;">
                    ⏹️ Stop
                </button>
            </div>
        </form>
        
        <div class="progress-section" id="progressSection">
            <h3>📝 Generation Progress</h3>
            <div class="progress-bar">
                <div class="progress-fill"></div>
            </div>
            <div class="output-area" id="outputArea"></div>
        </div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        
        // Check Ollama status on load
        window.addEventListener('load', () => {
            checkOllamaStatus();
        });
        
        function checkOllamaStatus() {
            document.getElementById('statusText').textContent = 'Checking Ollama status...';
            document.getElementById('statusDot').className = 'status-dot';
            vscode.postMessage({ command: 'checkOllamaStatus' });
        }
        
        function resetForm() {
            document.getElementById('configForm').reset();
            document.getElementById('phi3').checked = true;
        }
        
        document.getElementById('configForm').addEventListener('submit', (e) => {
            document.getElementById('stopBtn').style.display = 'inline-block';
            e.preventDefault();
            const formData = new FormData(e.target);
            const config = {
                diffno: formData.get('diffno') ? parseInt(formData.get('diffno')) : null,
                model: formData.get('model'),
                diffLimit: formData.get('diffLimit') ? parseInt(formData.get('diffLimit')) : null,
                watch: formData.get('watch') === 'on'
            };
            document.getElementById('progressSection').style.display = 'block';
            document.getElementById('generateBtn').disabled = true;
            document.getElementById('generateBtn').textContent = '⏳ Generating...';
            document.getElementById('outputArea').textContent = '';
            vscode.postMessage({ 
                command: 'generateDocs', 
                config: config 
            });
        });
        
        // Handle messages from extension
        window.addEventListener('message', event => {
            const message = event.data;
            
            switch (message.command) {
                case 'generationStarted':
                    document.getElementById('stopBtn').style.display = 'inline-block';
                    break;
                case 'ollamaStatus':
                    const statusDot = document.getElementById('statusDot');
                    const statusText = document.getElementById('statusText');
                    const generateBtn = document.getElementById('generateBtn');
                    
                    if (message.isRunning) {
                        statusDot.className = 'status-dot running';
                        statusText.textContent = 'Ollama server is running ✅';
                        generateBtn.disabled = false;
                    } else {
                        statusDot.className = 'status-dot';
                        statusText.textContent = 'Ollama server is not running ❌';
                        generateBtn.disabled = true;
                    }
                    break;
                    
                case 'generationStarted':
                    document.getElementById('outputArea').textContent += 'Starting documentation generation...\\n';
                    break;
                    
                case 'outputUpdate':
                    document.getElementById('outputArea').textContent += message.data;
                    document.getElementById('outputArea').scrollTop = document.getElementById('outputArea').scrollHeight;
                    break;
                    
                case 'errorUpdate':
                    document.getElementById('outputArea').textContent += '❌ ' + message.data;
                    document.getElementById('outputArea').scrollTop = document.getElementById('outputArea').scrollHeight;
                    break;
                    
                case 'generationComplete':
                    const btn = document.getElementById('generateBtn');
                    btn.disabled = false;
                    document.getElementById('stopBtn').style.display = 'none';
        document.getElementById('stopBtn').addEventListener('click', () => {
            vscode.postMessage({ command: 'stopGeneration' });
            document.getElementById('stopBtn').style.display = 'none';
        });
                    
                    if (message.success) {
                        btn.textContent = '✅ Generation Complete!';
                        document.getElementById('outputArea').textContent += '\\n🎉 Documentation generated successfully!\\n';
                        setTimeout(() => {
                            btn.textContent = '🚀 Generate Documentation';
                        }, 3000);
                    } else {
                        btn.textContent = '❌ Generation Failed';
                        document.getElementById('outputArea').textContent += '\\n❌ Generation failed' + (message.error ? ': ' + message.error : '') + ' \\n';
                        setTimeout(() => {
                            btn.textContent = '🚀 Generate Documentation';
                        }, 3000);
                    }
                    break;
            }
        });
    </script>
</body>
</html>`;
    }
}

export function activate(context: vscode.ExtensionContext) {
    console.log('Congratulations, "centrim-docgen" is now active!');

    const docGenTreeDataProvider = new DocGenTreeDataProvider(); // Instantiate the data provider
    vscode.window.registerTreeDataProvider(
        'centrimDocGenSidebarView', // This ID from package.json
        docGenTreeDataProvider
    );

    // Register command to open config panel
    let openConfigPanelDisposable = vscode.commands.registerCommand('centrim-docgen.openConfigPanel', () => {
        // Pass the treeDataProvider instance to the webview panel
        DocGenConfigPanel.createOrShow(context.extensionUri, docGenTreeDataProvider);
    });

    // Register the generateDocs command (still used by the command palette)
    let generateDocsDisposable = vscode.commands.registerCommand('centrim-docgen.generateDocs', () => {
        // This command will also open the config panel
        DocGenConfigPanel.createOrShow(context.extensionUri, docGenTreeDataProvider);
    });

    // Register the checkStatus command (triggered by the sidebar's "Refresh Ollama Status" item)
    let checkStatusDisposable = vscode.commands.registerCommand('centrim-docgen.checkStatus', async () => {
        docGenTreeDataProvider.updateStatus('checking_ollama'); // Update sidebar immediately
        // Perform the actual Ollama status check within the TreeDataProvider itself
        const ollamaUrl = vscode.workspace.getConfiguration('centrimDocgen').get<string>('ollamaUrl') || 'http://localhost:11434';
        try {
            const response = await fetch(ollamaUrl as string);
            if (response.ok) {
                docGenTreeDataProvider.updateStatus('ollama_ready');
                vscode.window.showInformationMessage('Ollama server is running.');
            } else {
                docGenTreeDataProvider.updateStatus('ollama_not_ready');
                vscode.window.showWarningMessage('Ollama server is not running or unreachable.');
            }
        } catch (error) {
            docGenTreeDataProvider.updateStatus('ollama_not_ready');
            vscode.window.showErrorMessage('Could not connect to Ollama server. Check URL and ensure it\'s running.');
        }
    });

    // Add disposable to context
    context.subscriptions.push(
        openConfigPanelDisposable,
        generateDocsDisposable,
        checkStatusDisposable
    );
}

export function deactivate() {
    if (DocGenConfigPanel.currentPanel) {
        DocGenConfigPanel.currentPanel.dispose();
    }
}
