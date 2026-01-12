/**
 * Sidebar WebView Provider
 * 
 * Provides the sidebar panel UI for displaying review summaries
 * and managing code reviews.
 */

import * as vscode from 'vscode';
import { ReviewResult, WebviewMessage, ExtensionMessage } from '../types';

export class SidebarProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'openRabbit.reviewPanel';

    private _view?: vscode.WebviewView;
    private _extensionUri: vscode.Uri;
    private _currentReview: ReviewResult | null = null;
    private _isLoading: boolean = false;

    private _onTriggerReview = new vscode.EventEmitter<void>();
    readonly onTriggerReview = this._onTriggerReview.event;

    private _onShowChanges = new vscode.EventEmitter<void>();
    readonly onShowChanges = this._onShowChanges.event;

    private _onOpenSettings = new vscode.EventEmitter<void>();
    readonly onOpenSettings = this._onOpenSettings.event;

    private _onOpenFile = new vscode.EventEmitter<{ file: string; line: number }>();
    readonly onOpenFile = this._onOpenFile.event;

    constructor(extensionUri: vscode.Uri) {
        this._extensionUri = extensionUri;
    }

    resolveWebviewView(
        webviewView: vscode.WebviewView,
        context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken
    ): void {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri],
        };

        webviewView.webview.html = this._getHtmlContent(webviewView.webview);

        webviewView.webview.onDidReceiveMessage((message: WebviewMessage) => {
            switch (message.command) {
                case 'triggerReview':
                    this._onTriggerReview.fire();
                    break;
                case 'showChanges':
                    this._onShowChanges.fire();
                    break;
                case 'openSettings':
                    this._onOpenSettings.fire();
                    break;
                case 'openFile':
                    const payload = message.payload as { file: string; line: number };
                    this._onOpenFile.fire(payload);
                    break;
                case 'refresh':
                    this.refresh();
                    break;
            }
        });
    }

    updateReview(review: ReviewResult): void {
        this._currentReview = review;
        this._isLoading = false;
        this._sendMessage({
            type: 'reviewUpdate',
            data: review,
        });
    }

    setLoading(loading: boolean): void {
        this._isLoading = loading;
        this._sendMessage({
            type: 'loading',
            data: loading,
        });
    }

    showError(message: string): void {
        this._sendMessage({
            type: 'error',
            data: message,
        });
    }

    updateStatus(status: string): void {
        this._sendMessage({
            type: 'statusUpdate',
            data: status,
        });
    }

    refresh(): void {
        if (this._view) {
            this._view.webview.html = this._getHtmlContent(this._view.webview);
        }
    }

    private _sendMessage(message: ExtensionMessage): void {
        if (this._view) {
            this._view.webview.postMessage(message);
        }
    }

    private _getHtmlContent(webview: vscode.Webview): string {
        const styleUri = webview.asWebviewUri(
            vscode.Uri.joinPath(this._extensionUri, 'resources', 'sidebar.css')
        );

        const nonce = this._getNonce();

        return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}';">
  <title>Open Rabbit</title>
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
      background-color: var(--vscode-sideBar-background);
      padding: 12px;
    }
    
    .header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 16px;
      padding-bottom: 12px;
      border-bottom: 1px solid var(--vscode-widget-border);
    }
    
    .logo {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    
    .logo-icon {
      width: 24px;
      height: 24px;
    }
    
    .logo-text {
      font-weight: 600;
      font-size: 14px;
    }
    
    .actions {
      display: flex;
      gap: 8px;
    }
    
    .btn {
      background: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
      border: none;
      padding: 6px 12px;
      border-radius: 4px;
      cursor: pointer;
      font-size: 12px;
      display: flex;
      align-items: center;
      gap: 6px;
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
    
    .btn-icon {
      background: transparent;
      border: none;
      color: var(--vscode-foreground);
      cursor: pointer;
      padding: 4px;
      border-radius: 4px;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    
    .btn-icon:hover {
      background: var(--vscode-toolbar-hoverBackground);
    }
    
    .status-card {
      background: var(--vscode-editor-background);
      border-radius: 6px;
      padding: 12px;
      margin-bottom: 16px;
    }
    
    .status-header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;
    }
    
    .status-indicator {
      width: 8px;
      height: 8px;
      border-radius: 50%;
    }
    
    .status-indicator.idle { background: var(--vscode-charts-gray); }
    .status-indicator.running { background: var(--vscode-charts-blue); animation: pulse 1.5s infinite; }
    .status-indicator.completed { background: var(--vscode-charts-green); }
    .status-indicator.failed { background: var(--vscode-charts-red); }
    
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.5; }
    }
    
    .status-title {
      font-weight: 500;
    }
    
    .status-message {
      font-size: 12px;
      color: var(--vscode-descriptionForeground);
    }
    
    .summary-section {
      margin-bottom: 16px;
    }
    
    .section-title {
      font-weight: 600;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--vscode-descriptionForeground);
      margin-bottom: 8px;
    }
    
    .summary-stats {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
    }
    
    .stat-item {
      background: var(--vscode-editor-background);
      border-radius: 6px;
      padding: 12px 8px;
      text-align: center;
    }
    
    .stat-value {
      font-size: 20px;
      font-weight: 600;
    }
    
    .stat-value.info { color: var(--vscode-charts-blue); }
    .stat-value.warning { color: var(--vscode-charts-yellow); }
    .stat-value.error { color: var(--vscode-charts-red); }
    
    .stat-label {
      font-size: 10px;
      color: var(--vscode-descriptionForeground);
      text-transform: uppercase;
    }
    
    .comments-section {
      margin-bottom: 16px;
    }
    
    .comment-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
      max-height: 400px;
      overflow-y: auto;
    }
    
    .comment-item {
      background: var(--vscode-editor-background);
      border-radius: 6px;
      padding: 10px;
      cursor: pointer;
      transition: background-color 0.2s;
      border-left: 3px solid transparent;
    }
    
    .comment-item:hover {
      background: var(--vscode-list-hoverBackground);
    }
    
    .comment-item.severity-info { border-left-color: var(--vscode-charts-blue); }
    .comment-item.severity-warning { border-left-color: var(--vscode-charts-yellow); }
    .comment-item.severity-error { border-left-color: var(--vscode-charts-red); }
    
    .comment-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 4px;
    }
    
    .comment-file {
      font-size: 11px;
      font-family: var(--vscode-editor-font-family);
      color: var(--vscode-textLink-foreground);
    }
    
    .comment-line {
      font-size: 10px;
      color: var(--vscode-descriptionForeground);
    }
    
    .comment-message {
      font-size: 12px;
      line-height: 1.4;
    }
    
    .severity-badge {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      font-size: 10px;
      padding: 2px 6px;
      border-radius: 10px;
      text-transform: uppercase;
      font-weight: 500;
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
    
    .empty-state {
      text-align: center;
      padding: 32px 16px;
      color: var(--vscode-descriptionForeground);
    }
    
    .empty-state-icon {
      font-size: 48px;
      margin-bottom: 12px;
      opacity: 0.5;
    }
    
    .empty-state-title {
      font-weight: 500;
      margin-bottom: 8px;
      color: var(--vscode-foreground);
    }
    
    .empty-state-text {
      font-size: 12px;
      margin-bottom: 16px;
    }
    
    .loading {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 32px;
    }
    
    .spinner {
      width: 32px;
      height: 32px;
      border: 3px solid var(--vscode-editor-background);
      border-top-color: var(--vscode-progressBar-background);
      border-radius: 50%;
      animation: spin 1s linear infinite;
      margin-bottom: 12px;
    }
    
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
    
    .loading-text {
      font-size: 12px;
      color: var(--vscode-descriptionForeground);
    }
  </style>
</head>
<body>
  <div class="header">
    <div class="logo">
      <span class="logo-text">🐰 Open Rabbit</span>
    </div>
    <div class="actions">
      <button class="btn-icon" id="settingsBtn" title="Settings">⚙️</button>
    </div>
  </div>

  <div id="content">
    <div id="emptyState" class="empty-state">
      <div class="empty-state-icon">🔍</div>
      <div class="empty-state-title">No Review Yet</div>
      <div class="empty-state-text">
        Make a commit or click the button below to trigger a code review.
      </div>
      <button class="btn" id="triggerReviewBtn">
        ▶ Start Review
      </button>
    </div>

    <div id="loadingState" class="loading" style="display: none;">
      <div class="spinner"></div>
      <div class="loading-text" id="loadingText">Analyzing code...</div>
    </div>

    <div id="reviewContent" style="display: none;">
      <div class="status-card">
        <div class="status-header">
          <div class="status-indicator" id="statusIndicator"></div>
          <span class="status-title" id="statusTitle">Review Complete</span>
        </div>
        <div class="status-message" id="statusMessage"></div>
      </div>

      <div class="summary-section">
        <div class="section-title">Summary</div>
        <div class="summary-stats">
          <div class="stat-item">
            <div class="stat-value info" id="infoCount">0</div>
            <div class="stat-label">Info</div>
          </div>
          <div class="stat-item">
            <div class="stat-value warning" id="warningCount">0</div>
            <div class="stat-label">Warnings</div>
          </div>
          <div class="stat-item">
            <div class="stat-value error" id="errorCount">0</div>
            <div class="stat-label">Errors</div>
          </div>
        </div>
      </div>

      <div class="comments-section">
        <div class="section-title">Issues</div>
        <div class="comment-list" id="commentList"></div>
      </div>

      <button class="btn" id="showChangesBtn" style="width: 100%;">
        📋 View Detailed Changes
      </button>
    </div>
  </div>

  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    
    // State
    let currentReview = null;
    let isLoading = false;
    
    // Elements
    const emptyState = document.getElementById('emptyState');
    const loadingState = document.getElementById('loadingState');
    const reviewContent = document.getElementById('reviewContent');
    const loadingText = document.getElementById('loadingText');
    const statusIndicator = document.getElementById('statusIndicator');
    const statusTitle = document.getElementById('statusTitle');
    const statusMessage = document.getElementById('statusMessage');
    const infoCount = document.getElementById('infoCount');
    const warningCount = document.getElementById('warningCount');
    const errorCount = document.getElementById('errorCount');
    const commentList = document.getElementById('commentList');
    
    // Event listeners
    document.getElementById('triggerReviewBtn').addEventListener('click', () => {
      vscode.postMessage({ command: 'triggerReview' });
    });
    
    document.getElementById('settingsBtn').addEventListener('click', () => {
      vscode.postMessage({ command: 'openSettings' });
    });
    
    document.getElementById('showChangesBtn').addEventListener('click', () => {
      vscode.postMessage({ command: 'showChanges' });
    });
    
    // Message handler
    window.addEventListener('message', (event) => {
      const message = event.data;
      
      switch (message.type) {
        case 'reviewUpdate':
          updateReview(message.data);
          break;
        case 'loading':
          setLoading(message.data);
          break;
        case 'statusUpdate':
          updateLoadingText(message.data);
          break;
        case 'error':
          showError(message.data);
          break;
      }
    });
    
    function setLoading(loading) {
      isLoading = loading;
      emptyState.style.display = loading ? 'none' : (currentReview ? 'none' : 'block');
      loadingState.style.display = loading ? 'flex' : 'none';
      reviewContent.style.display = loading ? 'none' : (currentReview ? 'block' : 'none');
    }
    
    function updateLoadingText(text) {
      loadingText.textContent = text;
    }
    
    function updateReview(review) {
      currentReview = review;
      
      emptyState.style.display = 'none';
      loadingState.style.display = 'none';
      reviewContent.style.display = 'block';
      
      // Update status
      statusIndicator.className = 'status-indicator ' + review.status;
      statusTitle.textContent = review.status === 'completed' ? 'Review Complete' : 
                                review.status === 'failed' ? 'Review Failed' : 'Reviewing...';
      statusMessage.textContent = review.summary?.summary || '';
      
      // Update stats
      const issues = review.summary?.issuesBySeverity || { info: 0, warning: 0, error: 0 };
      infoCount.textContent = issues.info;
      warningCount.textContent = issues.warning;
      errorCount.textContent = issues.error;
      
      // Update comments
      commentList.innerHTML = '';
      (review.comments || []).forEach((comment) => {
        const item = document.createElement('div');
        item.className = 'comment-item severity-' + comment.severity;
        item.innerHTML = \`
          <div class="comment-header">
            <span class="comment-file">\${comment.file}</span>
            <span class="comment-line">Line \${comment.line}</span>
          </div>
          <div class="comment-message">\${comment.message}</div>
        \`;
        item.addEventListener('click', () => {
          vscode.postMessage({ 
            command: 'openFile', 
            payload: { file: comment.file, line: comment.line } 
          });
        });
        commentList.appendChild(item);
      });
    }
    
    function showError(message) {
      loadingState.style.display = 'none';
      reviewContent.style.display = 'none';
      emptyState.style.display = 'block';
      emptyState.innerHTML = \`
        <div class="empty-state-icon">⚠️</div>
        <div class="empty-state-title">Error</div>
        <div class="empty-state-text">\${message}</div>
        <button class="btn" onclick="vscode.postMessage({ command: 'triggerReview' })">
          🔄 Retry
        </button>
      \`;
    }
  </script>
</body>
</html>`;
    }

    private _getNonce(): string {
        let text = '';
        const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
        for (let i = 0; i < 32; i++) {
            text += possible.charAt(Math.floor(Math.random() * possible.length));
        }
        return text;
    }
}
