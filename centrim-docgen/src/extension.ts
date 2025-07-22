import * as vscode from 'vscode';
import * as path from 'path';
import { spawn } from 'child_process';

// Define a simple TreeItem for our sidebar view
class DocGenTreeItem extends vscode.TreeItem {
	constructor(
		public readonly label: string,
		public readonly collapsibleState: vscode.TreeItemCollapsibleState,
		public readonly command?: vscode.Command
	) {
		super(label, collapsibleState);
		this.tooltip = this.label;
		this.description = "Click to generate documentation";
	}
}

// Define a TreeDataProvider for our sidebar view
class DocGenTreeDataProvider implements vscode.TreeDataProvider<DocGenTreeItem> {
	getTreeItem(element: DocGenTreeItem): vscode.TreeItem {
		return element;
	}

	getChildren(element?: DocGenTreeItem): Thenable<DocGenTreeItem[]> {
		if (element) {
			// No children for now, just a single action
			return Promise.resolve([]);
		} else {
			// Root elements of the tree view
			const generateDocsCommand: vscode.Command = {
				command: 'centrim-docgen.generateDocs', // Command to execute
				title: 'Generate Commit Documentation',
				tooltip: 'Generate documentation for the latest Git commit(s) using Ollama.'
			};
			return Promise.resolve([
				new DocGenTreeItem('Generate Docs', vscode.TreeItemCollapsibleState.None, generateDocsCommand)
			]);
		}
	}
}


export function activate(context: vscode.ExtensionContext) {

	console.log('Congratulations, "centrim-docgen" is now active!');

	// Register the TreeDataProvider for the custom sidebar view
	vscode.window.registerTreeDataProvider(
		'centrimDocGenSidebarView', // This ID must match the 'id' in package.json under 'contributes.views'
		new DocGenTreeDataProvider()
	);

	// Register the main command
	let disposable = vscode.commands.registerCommand('centrim-docgen.generateDocs', async () => {
		const outputChannel = vscode.window.createOutputChannel("Centrim DocGen");
		outputChannel.show(true);
		outputChannel.appendLine("--- Centrim DocGen Session Started ---");

		const workspaceFolders = vscode.workspace.workspaceFolders;
		if (!workspaceFolders || workspaceFolders.length === 0) {
			vscode.window.showErrorMessage("No workspace folder open. Please open a Git repository folder.");
			outputChannel.appendLine("Error: No workspace folder open.");
			outputChannel.appendLine("--- Centrim DocGen Session Ended ---");
			return;
		}

		const repoPath = workspaceFolders[0].uri.fsPath;

		// --- Collect User Inputs ---

		// 1. Get --diffno (optional)
		const diffnoInput = await vscode.window.showInputBox({
			prompt: "Enter number of recent diffs to process (e.g., 5). Leave empty for default.",
			placeHolder: "Default: 1 (latest) if refactoring.md exists, 5 otherwise"
		});
		let diffnoArg: string[] = [];
		if (diffnoInput && !isNaN(parseInt(diffnoInput))) {
			diffnoArg = ['--diffno', diffnoInput];
		}

		// 2. Get --model (optional, with quick pick suggestions)
		const modelSuggestions = ['phi3', 'mistral', 'tinyllama', 'llama3'];
		const modelInput = await vscode.window.showQuickPick(modelSuggestions, {
			placeHolder: "Select Ollama model (e.g., 'phi3') or type custom name. Leave empty for interactive prompt.",
			canPickMany: false
		});
		let modelArg: string[] = [];
		if (modelInput) {
			modelArg = ['--model', modelInput];
		}

		// 3. Get --watch (optional)
		const watchMode = await vscode.window.showQuickPick(['Yes', 'No'], {
			title: "Enable --watch mode? (Show raw Ollama output)",
			placeHolder: "No"
		});
		let watchArg: string[] = [];
		if (watchMode === 'Yes') {
			watchArg = ['--watch'];
		}

		// 4. Get Custom Query (optional)
		const useCustomQuery = await vscode.window.showQuickPick(['Yes', 'No'], {
			title: "Use a custom query/prompt for Ollama?",
			placeHolder: "No"
		});
		let customQueryArg: string[] = [];
		if (useCustomQuery === 'Yes') {
			const queryText = await vscode.window.showInputBox({
				prompt: "Enter your custom query/prompt for Ollama:",
				placeHolder: "e.g., 'Summarize these changes in a very technical way.'"
			});
			if (queryText) {
				customQueryArg = ['--custom-query', queryText];
			} else {
				vscode.window.showWarningMessage("No custom query entered. Proceeding with default prompt.");
			}
		}

		// --- Prepare Python Script Execution ---

		const pythonScriptPath = path.join(context.extensionPath, 'src', 'python_scripts', 'git_doc_tool.py');
		const pythonExec = process.platform === 'win32' ? 'python' : 'python3';

		const args = [
			pythonScriptPath,
			...diffnoArg,
			...modelArg,
			...watchArg,
			...customQueryArg // Add the custom query argument
		];

		outputChannel.appendLine(`Executing: ${pythonExec} ${args.join(' ')}`);
		outputChannel.appendLine(`In directory: ${repoPath}`);
		outputChannel.appendLine("------------------------------------");

		try {
			const pythonProcess = spawn(pythonExec, args, { cwd: repoPath });

			pythonProcess.stdout.on('data', (data) => {
				outputChannel.append(data.toString());
			});

			pythonProcess.stderr.on('data', (data) => {
				outputChannel.append(data.toString());
				vscode.window.showErrorMessage(`Centrim DocGen Error: ${data.toString().split('\n')[0]}`);
			});

			pythonProcess.on('close', (code) => {
				if (code === 0) {
					vscode.window.showInformationMessage('Centrim DocGen: Documentation generated successfully!');
					outputChannel.appendLine("Centrim DocGen: Script finished successfully.");
					vscode.commands.executeCommand('workbench.files.action.refreshExplorer');
				} else {
					vscode.window.showErrorMessage(`Centrim DocGen: Script exited with code ${code}. Check output channel for details.`);
					outputChannel.appendLine(`Centrim DocGen: Script exited with code ${code}.`);
				}
				outputChannel.appendLine("--- Centrim DocGen Session Ended ---");
			});

			pythonProcess.on('error', (err) => {
				vscode.window.showErrorMessage(`Failed to start Python script: ${err.message}. Make sure Python is installed and in your PATH.`);
				outputChannel.appendLine(`Error starting Python script: ${err.message}`);
				outputChannel.appendLine("--- Centrim DocGen Session Ended ---");
			});

		} catch (error: any) {
			vscode.window.showErrorMessage(`An unexpected error occurred: ${error.message}`);
			outputChannel.appendLine(`Unexpected error: ${error.message}`);
			outputChannel.appendLine("--- Centrim DocGen Session Ended ---");
		}
	});

	context.subscriptions.push(disposable);
}

export function deactivate() { }
