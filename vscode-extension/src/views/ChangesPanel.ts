/**
 * Changes Panel (Floating Window)
 * 
 * Provides a detailed view of code changes with inline review comments.
 * Opens as a webview panel that can be floated or positioned beside the editor.
 */

import * as vscode from 'vscode';
import { ReviewResult, ReviewComment } from '../types';

export class ChangesPanel {
    public static readonly viewType = 'openRabbit.changesPanel';

    private static currentPanel: ChangesPanel | undefined;

    private readonly _panel: vscode.WebviewPanel;
    private readonly _extensionUri: vscode.Uri;
    private _disposables: vscode.Disposable[] = [];
    private _reviewResult: ReviewResult | null = null;

    private _onApplySuggestion = new vscode.EventEmitter<{ file: string; line: number; suggestion: string }>();
    readonly onApplySuggestion = this._onApplySuggestion.event;

    private _onOpenFile = new vscode.EventEmitter<{ file: string; line: number }>();
    readonly onOpenFile = this._onOpenFile.event;

    private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri) {
        this._panel = panel;
        this._extensionUri = extensionUri;

        // Set initial content
        this._update();

        // Handle panel disposal
        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);

        // Handle view state changes
        this._panel.onDidChangeViewState(
            e => {
                if (this._panel.visible) {
                    this._update();
                }
            },
            null,
            this._disposables
        );

        // Handle messages from webview
        this._panel.webview.onDidReceiveMessage(
            message => {
                switch (message.command) {
                    case 'openFile':
                        this._onOpenFile.fire(message.payload);
                        break;
                    case 'applySuggestion':
                        this._onApplySuggestion.fire(message.payload);
                        break;
                }
            },
            null,
            this._disposables
        );
    }

    public static createOrShow(extensionUri: vscode.Uri, reviewResult?: ReviewResult): ChangesPanel {
        const column = vscode.ViewColumn.Beside;

        // If panel already exists
        if (ChangesPanel.currentPanel) {
            ChangesPanel.currentPanel._panel.reveal(column);
            if (reviewResult) {
                ChangesPanel.currentPanel.updateReview(reviewResult);
            }
            return ChangesPanel.currentPanel;
        }

        const panel = vscode.window.createWebviewPanel(
            ChangesPanel.viewType,
            'Open Rabbit - Changes',
            column,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
                localResourceRoots: [extensionUri],
            }
        );

        ChangesPanel.currentPanel = new ChangesPanel(panel, extensionUri);

        if (reviewResult) {
            ChangesPanel.currentPanel.updateReview(reviewResult);
        }

        return ChangesPanel.currentPanel;
    }

    public updateReview(reviewResult: ReviewResult): void {
        this._reviewResult = reviewResult;
        this._update();
    }

    private _update(): void {
        this._panel.webview.html = this._getHtmlContent();
    }

    private _getHtmlContent(): string {
        const nonce = this._getNonce();
        const review = this._reviewResult;

        const fileGroups = new Map<string, ReviewComment[]>();
        if (review?.comments) {
            for (const comment of review.comments) {
                if (!fileGroups.has(comment.file)) {
                    fileGroups.set(comment.file, []);
                }
                fileGroups.get(comment.file)!.push(comment);
            }
        }

        const filesHtml = review ? Array.from(fileGroups.entries()).map(([file, comments]) => `
      <div class="file-section">
        <div class="file-header" onclick="toggleFile('${this._escapeHtml(file)}')">
          <span class="file-icon">📄</span>
          <span class="file-name">${this._escapeHtml(file)}</span>
          <span class="file-badge">${comments.length} issues</span>
          <span class="toggle-icon" id="toggle-${this._escapeHtml(file).replace(/[^a-zA-Z0-9]/g, '-')}">▼</span>
        </div>
        <div class="file-content" id="content-${this._escapeHtml(file).replace(/[^a-zA-Z0-9]/g, '-')}">
          ${comments.map(c => this._renderComment(c)).join('')}
        </div>
      </div>
    `).join('') : '';

        return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${this._panel.webview.cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}';">
  <title>Open Rabbit - Changes</title>
  <style>
    :root {
      --vscode-font-family: var(--vscode-editor-font-family, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif);
    }
    
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }
    
    body {
      font-family: var(--vscode-font-family);
      font-size: var(--vscode-font-size, 13px);
      color: var(--vscode-foreground);
      background-color: var(--vscode-editor-background);
      padding: 16px;
    }
    
    .header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 20px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--vscode-widget-border);
    }
    
    .header-title {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    
    .header-title h1 {
      font-size: 18px;
      font-weight: 600;
    }
    
    .header-stats {
      display: flex;
      gap: 16px;
    }
    
    .stat {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
    }
    
    .stat-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
    }
    
    .stat-dot.info { background: var(--vscode-charts-blue); }
    .stat-dot.warning { background: var(--vscode-charts-yellow); }
    .stat-dot.error { background: var(--vscode-charts-red); }
    
    .summary-card {
      background: var(--vscode-sideBar-background);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 20px;
    }
    
    .summary-text {
      font-size: 13px;
      line-height: 1.6;
      color: var(--vscode-foreground);
    }
    
    .file-section {
      margin-bottom: 12px;
      border-radius: 8px;
      overflow: hidden;
      background: var(--vscode-sideBar-background);
    }
    
    .file-header {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px 16px;
      cursor: pointer;
      background: var(--vscode-sideBarSectionHeader-background);
      transition: background-color 0.2s;
    }
    
    .file-header:hover {
      background: var(--vscode-list-hoverBackground);
    }
    
    .file-icon {
      font-size: 16px;
    }
    
    .file-name {
      flex: 1;
      font-family: var(--vscode-editor-font-family);
      font-size: 13px;
      color: var(--vscode-textLink-foreground);
    }
    
    .file-badge {
      font-size: 11px;
      padding: 2px 8px;
      border-radius: 10px;
      background: var(--vscode-badge-background);
      color: var(--vscode-badge-foreground);
    }
    
    .toggle-icon {
      font-size: 10px;
      transition: transform 0.2s;
    }
    
    .file-content {
      padding: 8px;
    }
    
    .file-content.collapsed {
      display: none;
    }
    
    .comment-card {
      background: var(--vscode-editor-background);
      border-radius: 6px;
      padding: 12px;
      margin-bottom: 8px;
      border-left: 3px solid var(--vscode-charts-blue);
    }
    
    .comment-card.severity-info { border-left-color: var(--vscode-charts-blue); }
    .comment-card.severity-warning { border-left-color: var(--vscode-charts-yellow); }
    .comment-card.severity-error { border-left-color: var(--vscode-charts-red); }
    
    .comment-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 8px;
    }
    
    .comment-location {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    
    .comment-line {
      font-family: var(--vscode-editor-font-family);
      font-size: 12px;
      color: var(--vscode-descriptionForeground);
    }
    
    .severity-badge {
      font-size: 10px;
      padding: 2px 8px;
      border-radius: 10px;
      text-transform: uppercase;
      font-weight: 600;
    }
    
    .severity-badge.info {
      background: rgba(0, 122, 204, 0.2);
      color: var(--vscode-charts-blue);
    }
    
    .severity-badge.warning {
      background: rgba(255, 193, 7, 0.2);
      color: var(--vscode-charts-yellow);
    }
    
    .severity-badge.error {
      background: rgba(244, 67, 54, 0.2);
      color: var(--vscode-charts-red);
    }
    
    .comment-category {
      font-size: 10px;
      padding: 2px 6px;
      border-radius: 4px;
      background: var(--vscode-textBlockQuote-background);
      color: var(--vscode-descriptionForeground);
      margin-left: 8px;
    }
    
    .comment-message {
      font-size: 13px;
      line-height: 1.5;
      margin-bottom: 8px;
    }
    
    .suggestion-box {
      background: var(--vscode-textBlockQuote-background);
      border-radius: 4px;
      padding: 10px;
      margin-top: 8px;
    }
    
    .suggestion-label {
      font-size: 11px;
      font-weight: 600;
      color: var(--vscode-charts-green);
      margin-bottom: 6px;
    }
    
    .suggestion-code {
      font-family: var(--vscode-editor-font-family);
      font-size: 12px;
      background: var(--vscode-editor-background);
      padding: 8px;
      border-radius: 4px;
      overflow-x: auto;
      white-space: pre-wrap;
    }
    
    .comment-actions {
      display: flex;
      gap: 8px;
      margin-top: 10px;
    }
    
    .btn {
      background: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
      border: none;
      padding: 6px 12px;
      border-radius: 4px;
      cursor: pointer;
      font-size: 11px;
      display: flex;
      align-items: center;
      gap: 4px;
      transition: background-color 0.2s;
    }
    
    .btn:hover {
      background: var(--vscode-button-hoverBackground);
    }
    
    .btn-secondary {
      background: var(--vscode-button-secondaryBackground);
      color: var(--vscode-button-secondaryForeground);
    }
    
    .btn-secondary:hover {
      background: var(--vscode-button-secondaryHoverBackground);
    }
    
    .empty-state {
      text-align: center;
      padding: 48px 24px;
      color: var(--vscode-descriptionForeground);
    }
    
    .empty-state-icon {
      font-size: 64px;
      margin-bottom: 16px;
      opacity: 0.5;
    }
    
    .empty-state-title {
      font-size: 16px;
      font-weight: 500;
      margin-bottom: 8px;
      color: var(--vscode-foreground);
    }
  </style>
</head>
<body>
  ${review ? `
    <div class="header">
      <div class="header-title">
        <span style="font-size: 24px;">🐰</span>
        <h1>Code Review Results</h1>
      </div>
      <div class="header-stats">
        <div class="stat">
          <span class="stat-dot info"></span>
          <span>${review.summary?.issuesBySeverity.info || 0} Info</span>
        </div>
        <div class="stat">
          <span class="stat-dot warning"></span>
          <span>${review.summary?.issuesBySeverity.warning || 0} Warnings</span>
        </div>
        <div class="stat">
          <span class="stat-dot error"></span>
          <span>${review.summary?.issuesBySeverity.error || 0} Errors</span>
        </div>
      </div>
    </div>

    ${review.summary?.summary ? `
      <div class="summary-card">
        <div class="summary-text">${this._escapeHtml(review.summary.summary)}</div>
      </div>
    ` : ''}

    <div class="files-container">
      ${filesHtml || '<div class="empty-state"><div class="empty-state-icon">✨</div><div class="empty-state-title">No issues found!</div><p>Your code looks good.</p></div>'}
    </div>
  ` : `
    <div class="empty-state">
      <div class="empty-state-icon">📋</div>
      <div class="empty-state-title">No Review Data</div>
      <p>Trigger a code review to see results here.</p>
    </div>
  `}

  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    
    function toggleFile(file) {
      const safeId = file.replace(/[^a-zA-Z0-9]/g, '-');
      const content = document.getElementById('content-' + safeId);
      const toggle = document.getElementById('toggle-' + safeId);
      
      if (content && toggle) {
        content.classList.toggle('collapsed');
        toggle.textContent = content.classList.contains('collapsed') ? '▶' : '▼';
      }
    }
    
    function openFile(file, line) {
      vscode.postMessage({ 
        command: 'openFile', 
        payload: { file, line } 
      });
    }
    
    function applySuggestion(file, line, suggestion) {
      vscode.postMessage({ 
        command: 'applySuggestion', 
        payload: { file, line, suggestion } 
      });
    }
  </script>
</body>
</html>`;
    }

    private _renderComment(comment: ReviewComment): string {
        const hasSuggestion = comment.suggestion || comment.suggestionCode;

        return `
      <div class="comment-card severity-${comment.severity}">
        <div class="comment-header">
          <div class="comment-location">
            <span class="comment-line">Line ${comment.line}${comment.endLine && comment.endLine !== comment.line ? `-${comment.endLine}` : ''}</span>
            <span class="severity-badge ${comment.severity}">${comment.severity}</span>
            ${comment.category ? `<span class="comment-category">${this._escapeHtml(comment.category)}</span>` : ''}
          </div>
        </div>
        <div class="comment-message">${this._escapeHtml(comment.message)}</div>
        ${hasSuggestion ? `
          <div class="suggestion-box">
            <div class="suggestion-label">💡 Suggestion</div>
            ${comment.suggestion ? `<p style="font-size: 12px; margin-bottom: 8px;">${this._escapeHtml(comment.suggestion)}</p>` : ''}
            ${comment.suggestionCode ? `<pre class="suggestion-code">${this._escapeHtml(comment.suggestionCode)}</pre>` : ''}
          </div>
          <div class="comment-actions">
            <button class="btn" onclick="applySuggestion('${this._escapeJs(comment.file)}', ${comment.line}, '${this._escapeJs(comment.suggestionCode || '')}')">
              ✓ Apply
            </button>
            <button class="btn btn-secondary" onclick="openFile('${this._escapeJs(comment.file)}', ${comment.line})">
              📄 Go to file
            </button>
          </div>
        ` : `
          <div class="comment-actions">
            <button class="btn btn-secondary" onclick="openFile('${this._escapeJs(comment.file)}', ${comment.line})">
              📄 Go to file
            </button>
          </div>
        `}
      </div>
    `;
    }

    private _escapeHtml(text: string): string {
        return text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    private _escapeJs(text: string): string {
        return text
            .replace(/\\/g, '\\\\')
            .replace(/'/g, "\\'")
            .replace(/"/g, '\\"')
            .replace(/\n/g, '\\n')
            .replace(/\r/g, '\\r');
    }

    private _getNonce(): string {
        let text = '';
        const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
        for (let i = 0; i < 32; i++) {
            text += possible.charAt(Math.floor(Math.random() * possible.length));
        }
        return text;
    }

    public dispose(): void {
        ChangesPanel.currentPanel = undefined;
        this._panel.dispose();
        this._onApplySuggestion.dispose();
        this._onOpenFile.dispose();
        while (this._disposables.length) {
            const d = this._disposables.pop();
            if (d) {
                d.dispose();
            }
        }
    }
}
