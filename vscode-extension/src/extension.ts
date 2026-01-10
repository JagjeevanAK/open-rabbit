/**
 * Open Rabbit VS Code Extension
 * 
 * AI-powered code review triggered on git commits.
 * Features:
 * - Automatic review on commit
 * - Sidebar panel for review summary
 * - Floating window for detailed changes
 * - Workspace-scoped history persistence
 */

import * as vscode from 'vscode';
import { SidebarProvider } from './views/SidebarProvider';
import { ChangesPanel } from './views/ChangesPanel';
import { getApiClient } from './api/apiClient';
import { getGitWatcher, GitWatcher } from './git/gitWatcher';
import { initializeStateManager, getStateManager, StateManager } from './state/stateManager';
import { ReviewResult, GitCommit } from './types';

let statusBarItem: vscode.StatusBarItem;
let gitWatcher: GitWatcher;
let stateManager: StateManager;
let sidebarProvider: SidebarProvider;

export async function activate(context: vscode.ExtensionContext) {
	console.log('Open Rabbit extension is activating...');

	// Initialize state manager (workspace-scoped)
	stateManager = initializeStateManager(context);
	console.log(`Workspace: ${stateManager.getWorkspaceId()}`);

	// Initialize sidebar provider
	sidebarProvider = new SidebarProvider(context.extensionUri);

	context.subscriptions.push(
		vscode.window.registerWebviewViewProvider(
			SidebarProvider.viewType,
			sidebarProvider
		)
	);

	// Handle sidebar events
	context.subscriptions.push(
		sidebarProvider.onTriggerReview(() => triggerReview()),
		sidebarProvider.onShowChanges(() => showChangesPanel()),
		sidebarProvider.onOpenSettings(() => openSettings()),
		sidebarProvider.onOpenFile(({ file, line }) => openFileAtLine(file, line))
	);

	// Initialize Git watcher
	gitWatcher = getGitWatcher();
	const gitInitialized = await gitWatcher.initialize();

	if (gitInitialized) {
		// Listen for commits
		context.subscriptions.push(
			gitWatcher.onDidCommit((commit) => handleCommit(commit))
		);
	}

	// Create status bar item
	statusBarItem = vscode.window.createStatusBarItem(
		vscode.StatusBarAlignment.Left,
		100
	);
	statusBarItem.command = 'openRabbit.triggerReview';
	updateStatusBar('idle');
	statusBarItem.show();
	context.subscriptions.push(statusBarItem);

	// Register commands
	context.subscriptions.push(
		vscode.commands.registerCommand('openRabbit.triggerReview', triggerReview),
		vscode.commands.registerCommand('openRabbit.showChangesWindow', showChangesPanel),
		vscode.commands.registerCommand('openRabbit.refreshReview', refreshReview),
		vscode.commands.registerCommand('openRabbit.openSettings', openSettings)
	);

	// Restore last review state for this workspace
	const lastReview = stateManager.getCurrentReview();
	if (lastReview) {
		sidebarProvider.updateReview(lastReview);
	}

	console.log('Open Rabbit extension activated successfully!');
}

/**
 * Handle a new git commit
 */
async function handleCommit(commit: GitCommit): Promise<void> {
	const config = vscode.workspace.getConfiguration('openRabbit');
	const autoReview = config.get<boolean>('autoReviewOnCommit', true);

	if (!autoReview) {
		return;
	}

	// Check if we already processed this commit
	if (commit.hash === stateManager.getLastCommitHash()) {
		return;
	}

	await stateManager.setLastCommitHash(commit.hash);

	vscode.window.showInformationMessage(
		`New commit detected: ${commit.message.substring(0, 50)}...`,
		'Review Now',
		'Dismiss'
	).then(selection => {
		if (selection === 'Review Now') {
			triggerReview();
		}
	});

	// Auto-trigger review
	await triggerReview();
}

/**
 * Trigger a code review
 */
async function triggerReview(): Promise<void> {
	const apiClient = getApiClient();

	// Check backend health
	const isHealthy = await apiClient.healthCheck();
	if (!isHealthy) {
		vscode.window.showErrorMessage(
			'Open Rabbit backend is not available. Please check that the server is running.',
			'Open Settings'
		).then(selection => {
			if (selection === 'Open Settings') {
				openSettings();
			}
		});
		return;
	}

	// Get repository info
	const repoInfo = gitWatcher.getCurrentRepository();
	if (!repoInfo) {
		vscode.window.showWarningMessage('No Git repository found in the workspace.');
		return;
	}

	// Get changed files
	const changedFiles = await gitWatcher.getUncommittedChanges();
	if (changedFiles.length === 0) {
		vscode.window.showInformationMessage('No changes to review.');
		return;
	}

	try {
		// Update UI state
		sidebarProvider.setLoading(true);
		updateStatusBar('running');
		await stateManager.setLoading(true);

		sidebarProvider.updateStatus('Triggering review...');

		// Trigger review
		const taskResponse = await apiClient.triggerLocalReview({
			repoPath: repoInfo.remoteUrl || repoInfo.rootUri,
			branch: repoInfo.branch,
			changedFiles: changedFiles,
		});

		sidebarProvider.updateStatus(`Review started (${taskResponse.task_id})`);

		// Poll for completion
		const result = await apiClient.waitForReviewCompletion(
			taskResponse.task_id,
			(status) => {
				sidebarProvider.updateStatus(`Status: ${status}`);
			}
		);

		// Update state and UI
		await stateManager.setCurrentReview(result);
		sidebarProvider.updateReview(result);
		updateStatusBar('completed', result.summary?.totalIssues);

		// Show floating window if enabled
		const config = vscode.workspace.getConfiguration('openRabbit');
		if (config.get<boolean>('showFloatingWindow', true)) {
			showChangesPanel(result);
		}

		// Show notification
		const issueCount = result.summary?.totalIssues || 0;
		vscode.window.showInformationMessage(
			`Code review complete: ${issueCount} issue${issueCount !== 1 ? 's' : ''} found.`,
			'View Details'
		).then(selection => {
			if (selection === 'View Details') {
				showChangesPanel(result);
			}
		});

	} catch (error) {
		const errorMessage = error instanceof Error ? error.message : 'Unknown error';
		sidebarProvider.showError(errorMessage);
		updateStatusBar('failed');
		vscode.window.showErrorMessage(`Code review failed: ${errorMessage}`);
	} finally {
		sidebarProvider.setLoading(false);
		await stateManager.setLoading(false);
	}
}

/**
 * Show the changes panel
 */
function showChangesPanel(review?: ReviewResult): void {
	const reviewToShow = review || stateManager.getCurrentReview();

	if (!reviewToShow) {
		vscode.window.showInformationMessage('No review results to display. Trigger a review first.');
		return;
	}

	const panel = ChangesPanel.createOrShow(
		vscode.extensions.getExtension('open-rabbit.open-rabbit')?.extensionUri ||
		vscode.Uri.file(''),
		reviewToShow
	);

	// Handle panel events
	panel.onOpenFile(({ file, line }) => openFileAtLine(file, line));
	panel.onApplySuggestion(({ file, line, suggestion }) => {
		applySuggestion(file, line, suggestion);
	});
}

/**
 * Refresh the current review
 */
async function refreshReview(): Promise<void> {
	sidebarProvider.refresh();
	const currentReview = stateManager.getCurrentReview();
	if (currentReview) {
		sidebarProvider.updateReview(currentReview);
	}
}

/**
 * Open extension settings
 */
function openSettings(): void {
	vscode.commands.executeCommand(
		'workbench.action.openSettings',
		'openRabbit'
	);
}

/**
 * Open a file at a specific line
 */
async function openFileAtLine(file: string, line: number): Promise<void> {
	const workspaceFolders = vscode.workspace.workspaceFolders;
	if (!workspaceFolders) {
		return;
	}

	const filePath = vscode.Uri.joinPath(workspaceFolders[0].uri, file);

	try {
		const document = await vscode.workspace.openTextDocument(filePath);
		const editor = await vscode.window.showTextDocument(document);

		const position = new vscode.Position(Math.max(0, line - 1), 0);
		editor.selection = new vscode.Selection(position, position);
		editor.revealRange(
			new vscode.Range(position, position),
			vscode.TextEditorRevealType.InCenter
		);
	} catch (error) {
		vscode.window.showWarningMessage(`Could not open file: ${file}`);
	}
}

/**
 * Apply a code suggestion
 */
async function applySuggestion(file: string, line: number, suggestion: string): Promise<void> {
	if (!suggestion) {
		return;
	}

	const workspaceFolders = vscode.workspace.workspaceFolders;
	if (!workspaceFolders) {
		return;
	}

	const filePath = vscode.Uri.joinPath(workspaceFolders[0].uri, file);

	try {
		const document = await vscode.workspace.openTextDocument(filePath);
		const editor = await vscode.window.showTextDocument(document);

		const lineIndex = Math.max(0, line - 1);
		const lineText = document.lineAt(lineIndex);

		await editor.edit(editBuilder => {
			editBuilder.replace(lineText.range, suggestion);
		});

		vscode.window.showInformationMessage('Suggestion applied!');
	} catch (error) {
		vscode.window.showErrorMessage(`Could not apply suggestion: ${error}`);
	}
}

/**
 * Update the status bar
 */
function updateStatusBar(
	status: 'idle' | 'running' | 'completed' | 'failed',
	issueCount?: number
): void {
	switch (status) {
		case 'idle':
			statusBarItem.text = '$(rabbit) Open Rabbit';
			statusBarItem.tooltip = 'Click to trigger code review';
			statusBarItem.backgroundColor = undefined;
			break;
		case 'running':
			statusBarItem.text = '$(sync~spin) Reviewing...';
			statusBarItem.tooltip = 'Code review in progress';
			statusBarItem.backgroundColor = undefined;
			break;
		case 'completed':
			const count = issueCount ?? 0;
			statusBarItem.text = `$(check) ${count} issue${count !== 1 ? 's' : ''}`;
			statusBarItem.tooltip = 'Code review complete. Click to review again.';
			statusBarItem.backgroundColor = count > 0
				? new vscode.ThemeColor('statusBarItem.warningBackground')
				: undefined;
			break;
		case 'failed':
			statusBarItem.text = '$(error) Review failed';
			statusBarItem.tooltip = 'Code review failed. Click to retry.';
			statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
			break;
	}
}

export function deactivate() {
	console.log('Open Rabbit extension deactivated');
}
