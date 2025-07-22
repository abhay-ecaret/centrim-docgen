import * as vscode from 'vscode';
import * as path from 'path';
import { spawn } from 'child_process';

export function activate(context: vscode.ExtensionContext) {

	console.log('Congratulations, "centrim-docgen" is now active!');

	// The command ID must match the one in package.json
	let disposable = vscode.commands.registerCommand('centrim-docgen.generateDocs', async () => {
		// Create an output channel to show script progress
		const outputChannel = vscode.window.createOutputChannel("Centrim DocGen");
		outputChannel.show(true); // Show the channel immediately
		outputChannel.appendLine("--- Centrim DocGen Session Started ---");

		// Get the current workspace folder path
		const workspaceFolders = vscode.workspace.workspaceFolders;
		if (!workspaceFolders || workspaceFolders.length === 0) {
			vscode.window.showErrorMessage("No workspace folder open. Please open a Git repository folder.");
			outputChannel.appendLine("Error: No workspace folder open.");
			outputChannel.appendLine("--- Centrim DocGen Session Ended ---");
			return;
		}

		const repoPath = workspaceFolders[0].uri.fsPath; // Get the path of the first workspace folder

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
		const modelSuggestions = ['phi3', 'mistral', 'tinyllama', 'llama3']; // Common Ollama models
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

		// --- Prepare Python Script Execution ---

		// Path to your Python script within the extension
		// Ensure this path matches where you placed git_doc_tool.py
		const pythonScriptPath = path.join(context.extensionPath, 'src', 'python_scripts', 'git_doc_tool.py');

		// Determine the Python executable
		const pythonExec = process.platform === 'win32' ? 'python' : 'python3';

		const args = [
			pythonScriptPath,
			...diffnoArg,
			...modelArg,
			...watchArg
		];

		outputChannel.appendLine(`Executing: ${pythonExec} ${args.join(' ')}`);
		outputChannel.appendLine(`In directory: ${repoPath}`);
		outputChannel.appendLine("------------------------------------");

		try {
			// Spawn the Python script
			const pythonProcess = spawn(pythonExec, args, { cwd: repoPath });

			// Pipe Python script's stdout to VS Code output channel
			pythonProcess.stdout.on('data', (data) => {
				outputChannel.append(data.toString());
			});

			// Pipe Python script's stderr to VS Code output channel
			pythonProcess.stderr.on('data', (data) => {
				outputChannel.append(data.toString());
				// Show error message in a toast, but only the first line to avoid spam
				vscode.window.showErrorMessage(`Centrim DocGen Error: ${data.toString().split('\n')[0]}`);
			});

			// Handle process exit
			pythonProcess.on('close', (code) => {
				if (code === 0) {
					vscode.window.showInformationMessage('Centrim DocGen: Documentation generated successfully!');
					outputChannel.appendLine("Centrim DocGen: Script finished successfully.");
					// Optional: Refresh the explorer if refactoring.md is open/visible
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
