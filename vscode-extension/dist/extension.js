"use strict";
var __create = Object.create;
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __getProtoOf = Object.getPrototypeOf;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __export = (target, all) => {
  for (var name in all)
    __defProp(target, name, { get: all[name], enumerable: true });
};
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(
  // If the importer is in node compatibility mode or this is not an ESM
  // file that has been converted to a CommonJS file using a Babel-
  // compatible transform (i.e. "__esModule" has not been set), then set
  // "default" to the CommonJS "module.exports" for node compatibility.
  isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", { value: mod, enumerable: true }) : target,
  mod
));
var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);

// src/extension.ts
var extension_exports = {};
__export(extension_exports, {
  activate: () => activate,
  deactivate: () => deactivate
});
module.exports = __toCommonJS(extension_exports);
var vscode6 = __toESM(require("vscode"));

// src/views/SidebarProvider.ts
var vscode = __toESM(require("vscode"));
var SidebarProvider = class {
  static viewType = "openRabbit.reviewPanel";
  _view;
  _extensionUri;
  _currentReview = null;
  _isLoading = false;
  // Event emitters for communicating with extension
  _onTriggerReview = new vscode.EventEmitter();
  onTriggerReview = this._onTriggerReview.event;
  _onShowChanges = new vscode.EventEmitter();
  onShowChanges = this._onShowChanges.event;
  _onOpenSettings = new vscode.EventEmitter();
  onOpenSettings = this._onOpenSettings.event;
  _onOpenFile = new vscode.EventEmitter();
  onOpenFile = this._onOpenFile.event;
  constructor(extensionUri) {
    this._extensionUri = extensionUri;
  }
  resolveWebviewView(webviewView, context, _token) {
    this._view = webviewView;
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri]
    };
    webviewView.webview.html = this._getHtmlContent(webviewView.webview);
    webviewView.webview.onDidReceiveMessage((message) => {
      switch (message.command) {
        case "triggerReview":
          this._onTriggerReview.fire();
          break;
        case "showChanges":
          this._onShowChanges.fire();
          break;
        case "openSettings":
          this._onOpenSettings.fire();
          break;
        case "openFile":
          const payload = message.payload;
          this._onOpenFile.fire(payload);
          break;
        case "refresh":
          this.refresh();
          break;
      }
    });
  }
  /**
   * Update the sidebar with new review data
   */
  updateReview(review) {
    this._currentReview = review;
    this._isLoading = false;
    this._sendMessage({
      type: "reviewUpdate",
      data: review
    });
  }
  /**
   * Set loading state
   */
  setLoading(loading) {
    this._isLoading = loading;
    this._sendMessage({
      type: "loading",
      data: loading
    });
  }
  /**
   * Show error message
   */
  showError(message) {
    this._sendMessage({
      type: "error",
      data: message
    });
  }
  /**
   * Update status message
   */
  updateStatus(status) {
    this._sendMessage({
      type: "statusUpdate",
      data: status
    });
  }
  /**
   * Refresh the sidebar view
   */
  refresh() {
    if (this._view) {
      this._view.webview.html = this._getHtmlContent(this._view.webview);
    }
  }
  _sendMessage(message) {
    if (this._view) {
      this._view.webview.postMessage(message);
    }
  }
  _getHtmlContent(webview) {
    const styleUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this._extensionUri, "resources", "sidebar.css")
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
      <span class="logo-text">\u{1F430} Open Rabbit</span>
    </div>
    <div class="actions">
      <button class="btn-icon" id="settingsBtn" title="Settings">\u2699\uFE0F</button>
    </div>
  </div>

  <div id="content">
    <div id="emptyState" class="empty-state">
      <div class="empty-state-icon">\u{1F50D}</div>
      <div class="empty-state-title">No Review Yet</div>
      <div class="empty-state-text">
        Make a commit or click the button below to trigger a code review.
      </div>
      <button class="btn" id="triggerReviewBtn">
        \u25B6 Start Review
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
        \u{1F4CB} View Detailed Changes
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
        <div class="empty-state-icon">\u26A0\uFE0F</div>
        <div class="empty-state-title">Error</div>
        <div class="empty-state-text">\${message}</div>
        <button class="btn" onclick="vscode.postMessage({ command: 'triggerReview' })">
          \u{1F504} Retry
        </button>
      \`;
    }
  </script>
</body>
</html>`;
  }
  _getNonce() {
    let text = "";
    const possible = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
    for (let i = 0; i < 32; i++) {
      text += possible.charAt(Math.floor(Math.random() * possible.length));
    }
    return text;
  }
};

// src/views/ChangesPanel.ts
var vscode2 = __toESM(require("vscode"));
var ChangesPanel = class _ChangesPanel {
  static viewType = "openRabbit.changesPanel";
  static currentPanel;
  _panel;
  _extensionUri;
  _disposables = [];
  _reviewResult = null;
  // Event emitters
  _onApplySuggestion = new vscode2.EventEmitter();
  onApplySuggestion = this._onApplySuggestion.event;
  _onOpenFile = new vscode2.EventEmitter();
  onOpenFile = this._onOpenFile.event;
  constructor(panel, extensionUri) {
    this._panel = panel;
    this._extensionUri = extensionUri;
    this._update();
    this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
    this._panel.onDidChangeViewState(
      (e) => {
        if (this._panel.visible) {
          this._update();
        }
      },
      null,
      this._disposables
    );
    this._panel.webview.onDidReceiveMessage(
      (message) => {
        switch (message.command) {
          case "openFile":
            this._onOpenFile.fire(message.payload);
            break;
          case "applySuggestion":
            this._onApplySuggestion.fire(message.payload);
            break;
        }
      },
      null,
      this._disposables
    );
  }
  /**
   * Create or show the changes panel
   */
  static createOrShow(extensionUri, reviewResult) {
    const column = vscode2.ViewColumn.Beside;
    if (_ChangesPanel.currentPanel) {
      _ChangesPanel.currentPanel._panel.reveal(column);
      if (reviewResult) {
        _ChangesPanel.currentPanel.updateReview(reviewResult);
      }
      return _ChangesPanel.currentPanel;
    }
    const panel = vscode2.window.createWebviewPanel(
      _ChangesPanel.viewType,
      "Open Rabbit - Changes",
      column,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [extensionUri]
      }
    );
    _ChangesPanel.currentPanel = new _ChangesPanel(panel, extensionUri);
    if (reviewResult) {
      _ChangesPanel.currentPanel.updateReview(reviewResult);
    }
    return _ChangesPanel.currentPanel;
  }
  /**
   * Update the panel with new review data
   */
  updateReview(reviewResult) {
    this._reviewResult = reviewResult;
    this._update();
  }
  _update() {
    this._panel.webview.html = this._getHtmlContent();
  }
  _getHtmlContent() {
    const nonce = this._getNonce();
    const review = this._reviewResult;
    const fileGroups = /* @__PURE__ */ new Map();
    if (review?.comments) {
      for (const comment of review.comments) {
        if (!fileGroups.has(comment.file)) {
          fileGroups.set(comment.file, []);
        }
        fileGroups.get(comment.file).push(comment);
      }
    }
    const filesHtml = review ? Array.from(fileGroups.entries()).map(([file, comments]) => `
      <div class="file-section">
        <div class="file-header" onclick="toggleFile('${this._escapeHtml(file)}')">
          <span class="file-icon">\u{1F4C4}</span>
          <span class="file-name">${this._escapeHtml(file)}</span>
          <span class="file-badge">${comments.length} issues</span>
          <span class="toggle-icon" id="toggle-${this._escapeHtml(file).replace(/[^a-zA-Z0-9]/g, "-")}">\u25BC</span>
        </div>
        <div class="file-content" id="content-${this._escapeHtml(file).replace(/[^a-zA-Z0-9]/g, "-")}">
          ${comments.map((c) => this._renderComment(c)).join("")}
        </div>
      </div>
    `).join("") : "";
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
        <span style="font-size: 24px;">\u{1F430}</span>
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
    ` : ""}

    <div class="files-container">
      ${filesHtml || '<div class="empty-state"><div class="empty-state-icon">\u2728</div><div class="empty-state-title">No issues found!</div><p>Your code looks good.</p></div>'}
    </div>
  ` : `
    <div class="empty-state">
      <div class="empty-state-icon">\u{1F4CB}</div>
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
        toggle.textContent = content.classList.contains('collapsed') ? '\u25B6' : '\u25BC';
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
  _renderComment(comment) {
    const hasSuggestion = comment.suggestion || comment.suggestionCode;
    return `
      <div class="comment-card severity-${comment.severity}">
        <div class="comment-header">
          <div class="comment-location">
            <span class="comment-line">Line ${comment.line}${comment.endLine && comment.endLine !== comment.line ? `-${comment.endLine}` : ""}</span>
            <span class="severity-badge ${comment.severity}">${comment.severity}</span>
            ${comment.category ? `<span class="comment-category">${this._escapeHtml(comment.category)}</span>` : ""}
          </div>
        </div>
        <div class="comment-message">${this._escapeHtml(comment.message)}</div>
        ${hasSuggestion ? `
          <div class="suggestion-box">
            <div class="suggestion-label">\u{1F4A1} Suggestion</div>
            ${comment.suggestion ? `<p style="font-size: 12px; margin-bottom: 8px;">${this._escapeHtml(comment.suggestion)}</p>` : ""}
            ${comment.suggestionCode ? `<pre class="suggestion-code">${this._escapeHtml(comment.suggestionCode)}</pre>` : ""}
          </div>
          <div class="comment-actions">
            <button class="btn" onclick="applySuggestion('${this._escapeJs(comment.file)}', ${comment.line}, '${this._escapeJs(comment.suggestionCode || "")}')">
              \u2713 Apply
            </button>
            <button class="btn btn-secondary" onclick="openFile('${this._escapeJs(comment.file)}', ${comment.line})">
              \u{1F4C4} Go to file
            </button>
          </div>
        ` : `
          <div class="comment-actions">
            <button class="btn btn-secondary" onclick="openFile('${this._escapeJs(comment.file)}', ${comment.line})">
              \u{1F4C4} Go to file
            </button>
          </div>
        `}
      </div>
    `;
  }
  _escapeHtml(text) {
    return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
  }
  _escapeJs(text) {
    return text.replace(/\\/g, "\\\\").replace(/'/g, "\\'").replace(/"/g, '\\"').replace(/\n/g, "\\n").replace(/\r/g, "\\r");
  }
  _getNonce() {
    let text = "";
    const possible = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
    for (let i = 0; i < 32; i++) {
      text += possible.charAt(Math.floor(Math.random() * possible.length));
    }
    return text;
  }
  dispose() {
    _ChangesPanel.currentPanel = void 0;
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
};

// src/api/apiClient.ts
var vscode3 = __toESM(require("vscode"));
var ApiClient = class {
  baseUrl;
  pollingInterval;
  constructor() {
    this.loadConfig();
    vscode3.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration("openRabbit")) {
        this.loadConfig();
      }
    });
  }
  loadConfig() {
    const config = vscode3.workspace.getConfiguration("openRabbit");
    this.baseUrl = config.get("backendUrl", "http://localhost:8080");
    this.pollingInterval = config.get("pollingInterval", 2e3);
  }
  /**
   * Trigger a code review for local changes
   */
  async triggerLocalReview(request) {
    const reviewRequest = {
      repoUrl: request.repoPath,
      branch: request.branch,
      changedFiles: request.changedFiles.map((f) => f.path),
      prDescription: request.commitMessage,
      autoPost: false
      // Local reviews don't post to GitHub
    };
    return this.triggerReview(reviewRequest);
  }
  /**
   * Trigger a code review via the backend API
   */
  async triggerReview(request) {
    const url = `${this.baseUrl}/feedback/review/pr`;
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          repo_url: request.repoUrl,
          pr_number: request.prNumber,
          branch: request.branch,
          changed_files: request.changedFiles,
          pr_description: request.prDescription,
          generate_tests: request.generateTests ?? false,
          auto_post: request.autoPost ?? false
        })
      });
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`API error: ${response.status} - ${errorText}`);
      }
      return await response.json();
    } catch (error) {
      if (error instanceof Error) {
        throw new Error(`Failed to trigger review: ${error.message}`);
      }
      throw error;
    }
  }
  /**
   * Get the status of a review task
   */
  async getReviewStatus(taskId) {
    const url = `${this.baseUrl}/feedback/review/status/${taskId}`;
    try {
      const response = await fetch(url);
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`API error: ${response.status} - ${errorText}`);
      }
      return await response.json();
    } catch (error) {
      if (error instanceof Error) {
        throw new Error(`Failed to get review status: ${error.message}`);
      }
      throw error;
    }
  }
  /**
   * Get the full result of a completed review
   */
  async getReviewResult(taskId) {
    const url = `${this.baseUrl}/feedback/review/result/${taskId}`;
    try {
      const response = await fetch(url);
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`API error: ${response.status} - ${errorText}`);
      }
      return await response.json();
    } catch (error) {
      if (error instanceof Error) {
        throw new Error(`Failed to get review result: ${error.message}`);
      }
      throw error;
    }
  }
  /**
   * Poll for review completion
   */
  async waitForReviewCompletion(taskId, onProgress, timeoutMs = 3e5) {
    const startTime = Date.now();
    while (Date.now() - startTime < timeoutMs) {
      const status = await this.getReviewStatus(taskId);
      if (onProgress) {
        onProgress(status.status);
      }
      if (status.status === "completed") {
        return this.transformApiResult(status);
      }
      if (status.status === "failed") {
        throw new Error(status.error || "Review failed");
      }
      await this.delay(this.pollingInterval);
    }
    throw new Error("Review timed out");
  }
  /**
   * Transform API response to internal ReviewResult format
   */
  transformApiResult(apiResponse) {
    const result = apiResponse.result;
    const comments = (result?.comments || []).map((c) => ({
      file: c.file,
      line: c.line,
      endLine: c.end_line,
      severity: c.severity || "info",
      category: c.category || "general",
      message: c.message,
      suggestion: c.suggestion,
      suggestionCode: c.suggestion_code
    }));
    const summary = {
      totalFiles: result?.files_reviewed || 0,
      totalIssues: result?.issues_found || comments.length,
      issuesBySeverity: {
        info: comments.filter((c) => c.severity === "info").length,
        warning: comments.filter((c) => c.severity === "warning").length,
        error: comments.filter((c) => c.severity === "error").length
      },
      summary: result?.summary || "Review completed"
    };
    return {
      taskId: apiResponse.task_id,
      status: apiResponse.status,
      createdAt: apiResponse.created_at,
      completedAt: apiResponse.completed_at,
      summary,
      comments,
      error: apiResponse.error
    };
  }
  /**
   * Health check for the backend
   */
  async healthCheck() {
    try {
      const response = await fetch(`${this.baseUrl}/health`);
      return response.ok;
    } catch {
      return false;
    }
  }
  delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
};
var apiClientInstance = null;
function getApiClient() {
  if (!apiClientInstance) {
    apiClientInstance = new ApiClient();
  }
  return apiClientInstance;
}

// src/git/gitWatcher.ts
var vscode4 = __toESM(require("vscode"));
var GitWatcher = class {
  gitApi;
  disposables = [];
  lastCommitHash = null;
  _onDidCommit = new vscode4.EventEmitter();
  onDidCommit = this._onDidCommit.event;
  _onDidChangeRepository = new vscode4.EventEmitter();
  onDidChangeRepository = this._onDidChangeRepository.event;
  async initialize() {
    const gitExtension = vscode4.extensions.getExtension("vscode.git");
    if (!gitExtension) {
      vscode4.window.showWarningMessage("Git extension not found. Open Rabbit requires Git.");
      return false;
    }
    if (!gitExtension.isActive) {
      await gitExtension.activate();
    }
    this.gitApi = gitExtension.exports.getAPI(1);
    this.disposables.push(
      this.gitApi.onDidOpenRepository(() => this.onRepositoryOpen()),
      this.gitApi.onDidCloseRepository(() => this.onRepositoryClose())
    );
    for (const repo of this.gitApi.repositories) {
      this.watchRepository(repo);
    }
    await this.updateLastCommitHash();
    return true;
  }
  watchRepository(repo) {
    const stateChangeDisposable = repo.state.onDidChange(() => {
      this.checkForNewCommit(repo);
    });
    this.disposables.push(stateChangeDisposable);
  }
  async checkForNewCommit(repo) {
    const currentHash = repo.state.HEAD?.commit;
    if (!currentHash || currentHash === this.lastCommitHash) {
      return;
    }
    const previousHash = this.lastCommitHash;
    this.lastCommitHash = currentHash;
    try {
      const logs = await repo.log({ maxEntries: 1 });
      if (logs.length > 0) {
        const latestCommit = logs[0];
        const changedFiles = await this.getCommitChangedFiles(repo, currentHash, previousHash);
        const commit = {
          hash: latestCommit.hash,
          message: latestCommit.message,
          author: latestCommit.authorName || "Unknown",
          date: latestCommit.commitDate || /* @__PURE__ */ new Date(),
          files: changedFiles
        };
        this._onDidCommit.fire(commit);
      }
    } catch (error) {
      console.error("Error getting commit info:", error);
    }
  }
  async getCommitChangedFiles(repo, currentHash, previousHash) {
    try {
      const diffRef = previousHash || `${currentHash}~1`;
      const diff = await repo.diffWith(diffRef);
      const files = [];
      const diffLines = diff.split("\n");
      for (const line of diffLines) {
        if (line.startsWith("diff --git")) {
          const match = line.match(/diff --git a\/(.+?) b\/(.+)/);
          if (match) {
            files.push(match[2]);
          }
        }
      }
      return files;
    } catch {
      return [];
    }
  }
  async updateLastCommitHash() {
    const repo = this.getActiveRepository();
    if (repo) {
      this.lastCommitHash = repo.state.HEAD?.commit || null;
    }
  }
  onRepositoryOpen() {
    const repo = this.getActiveRepository();
    if (repo) {
      this.watchRepository(repo);
      this._onDidChangeRepository.fire(this.getGitRepositoryInfo(repo));
    }
  }
  onRepositoryClose() {
    this._onDidChangeRepository.fire(null);
  }
  /**
   * Get the active repository (first one if multiple)
   */
  getActiveRepository() {
    return this.gitApi?.repositories[0];
  }
  /**
   * Get current repository info
   */
  getCurrentRepository() {
    const repo = this.getActiveRepository();
    if (!repo) {
      return null;
    }
    return this.getGitRepositoryInfo(repo);
  }
  getGitRepositoryInfo(repo) {
    const remotes = repo.state.remotes;
    const originRemote = remotes.find((r) => r.name === "origin");
    return {
      rootUri: repo.rootUri.fsPath,
      name: repo.rootUri.path.split("/").pop() || "",
      branch: repo.state.HEAD?.name || "main",
      remoteUrl: originRemote?.fetchUrl || originRemote?.pushUrl
    };
  }
  /**
   * Get uncommitted changes (working tree + staged)
   */
  async getUncommittedChanges() {
    const repo = this.getActiveRepository();
    if (!repo) {
      return [];
    }
    const changes = [];
    const allChanges = [
      ...repo.state.workingTreeChanges,
      ...repo.state.indexChanges
    ];
    for (const change of allChanges) {
      const status = this.mapChangeStatus(change.status);
      changes.push({
        path: vscode4.workspace.asRelativePath(change.uri),
        status
      });
    }
    const seen = /* @__PURE__ */ new Set();
    return changes.filter((c) => {
      if (seen.has(c.path)) {
        return false;
      }
      seen.add(c.path);
      return true;
    });
  }
  /**
   * Get the diff for uncommitted changes
   */
  async getUncommittedDiff() {
    const repo = this.getActiveRepository();
    if (!repo) {
      return "";
    }
    try {
      const stagedDiff = await repo.diff(true);
      const unstagedDiff = await repo.diff(false);
      return `${stagedDiff}
${unstagedDiff}`;
    } catch {
      return "";
    }
  }
  mapChangeStatus(status) {
    switch (status) {
      case 1:
      // Added
      case 5:
        return "added";
      case 2:
      // Deleted
      case 6:
        return "deleted";
      case 3:
        return "renamed";
      default:
        return "modified";
    }
  }
  /**
   * Get the current branch name
   */
  getCurrentBranch() {
    const repo = this.getActiveRepository();
    return repo?.state.HEAD?.name || null;
  }
  /**
   * Get the last commit hash
   */
  getLastCommitHash() {
    return this.lastCommitHash;
  }
  dispose() {
    this._onDidCommit.dispose();
    this._onDidChangeRepository.dispose();
    this.disposables.forEach((d) => d.dispose());
  }
};
var gitWatcherInstance = null;
function getGitWatcher() {
  if (!gitWatcherInstance) {
    gitWatcherInstance = new GitWatcher();
  }
  return gitWatcherInstance;
}

// src/state/stateManager.ts
var vscode5 = __toESM(require("vscode"));
var STATE_KEY = "openRabbit.state";
var MAX_HISTORY_SIZE = 50;
var StateManager = class {
  context;
  state;
  constructor(context) {
    this.context = context;
    this.state = this.loadState();
  }
  /**
   * Load state from workspace-scoped storage
   * This ensures each project has its own isolated state
   */
  loadState() {
    const savedState = this.context.workspaceState.get(STATE_KEY);
    if (savedState) {
      if (savedState.reviewHistory) {
        savedState.reviewHistory = savedState.reviewHistory.map((r) => ({
          ...r,
          createdAt: r.createdAt,
          completedAt: r.completedAt
        }));
      }
      return savedState;
    }
    return {
      currentReview: null,
      reviewHistory: [],
      isLoading: false,
      lastCommitHash: null
    };
  }
  /**
   * Save state to workspace-scoped storage
   */
  async saveState() {
    await this.context.workspaceState.update(STATE_KEY, this.state);
  }
  /**
   * Get current review
   */
  getCurrentReview() {
    return this.state.currentReview;
  }
  /**
   * Set current review and add to history
   */
  async setCurrentReview(review) {
    this.state.currentReview = review;
    if (review.status === "completed" || review.status === "failed") {
      this.addToHistory(review);
    }
    await this.saveState();
  }
  /**
   * Clear current review
   */
  async clearCurrentReview() {
    this.state.currentReview = null;
    await this.saveState();
  }
  /**
   * Get review history for current workspace
   */
  getReviewHistory() {
    return this.state.reviewHistory;
  }
  /**
   * Add a review to history
   */
  addToHistory(review) {
    const existingIndex = this.state.reviewHistory.findIndex(
      (r) => r.taskId === review.taskId
    );
    if (existingIndex >= 0) {
      this.state.reviewHistory[existingIndex] = review;
    } else {
      this.state.reviewHistory.unshift(review);
      if (this.state.reviewHistory.length > MAX_HISTORY_SIZE) {
        this.state.reviewHistory = this.state.reviewHistory.slice(0, MAX_HISTORY_SIZE);
      }
    }
  }
  /**
   * Clear all history for current workspace
   */
  async clearHistory() {
    this.state.reviewHistory = [];
    await this.saveState();
  }
  /**
   * Get loading state
   */
  isLoading() {
    return this.state.isLoading;
  }
  /**
   * Set loading state
   */
  async setLoading(loading) {
    this.state.isLoading = loading;
    await this.saveState();
  }
  /**
   * Get last commit hash
   */
  getLastCommitHash() {
    return this.state.lastCommitHash;
  }
  /**
   * Set last commit hash
   */
  async setLastCommitHash(hash) {
    this.state.lastCommitHash = hash;
    await this.saveState();
  }
  /**
   * Get a review from history by task ID
   */
  getReviewById(taskId) {
    if (this.state.currentReview?.taskId === taskId) {
      return this.state.currentReview;
    }
    return this.state.reviewHistory.find((r) => r.taskId === taskId);
  }
  /**
   * Get workspace identifier (for debugging)
   */
  getWorkspaceId() {
    const folders = vscode5.workspace.workspaceFolders;
    if (folders && folders.length > 0) {
      return folders[0].uri.fsPath;
    }
    return "no-workspace";
  }
  /**
   * Reset all state (for testing or user request)
   */
  async resetState() {
    this.state = {
      currentReview: null,
      reviewHistory: [],
      isLoading: false,
      lastCommitHash: null
    };
    await this.saveState();
  }
};
var stateManagerInstance = null;
function initializeStateManager(context) {
  stateManagerInstance = new StateManager(context);
  return stateManagerInstance;
}

// src/extension.ts
var statusBarItem;
var gitWatcher;
var stateManager;
var sidebarProvider;
async function activate(context) {
  console.log("Open Rabbit extension is activating...");
  stateManager = initializeStateManager(context);
  console.log(`Workspace: ${stateManager.getWorkspaceId()}`);
  sidebarProvider = new SidebarProvider(context.extensionUri);
  context.subscriptions.push(
    vscode6.window.registerWebviewViewProvider(
      SidebarProvider.viewType,
      sidebarProvider
    )
  );
  context.subscriptions.push(
    sidebarProvider.onTriggerReview(() => triggerReview()),
    sidebarProvider.onShowChanges(() => showChangesPanel()),
    sidebarProvider.onOpenSettings(() => openSettings()),
    sidebarProvider.onOpenFile(({ file, line }) => openFileAtLine(file, line))
  );
  gitWatcher = getGitWatcher();
  const gitInitialized = await gitWatcher.initialize();
  if (gitInitialized) {
    context.subscriptions.push(
      gitWatcher.onDidCommit((commit) => handleCommit(commit))
    );
  }
  statusBarItem = vscode6.window.createStatusBarItem(
    vscode6.StatusBarAlignment.Left,
    100
  );
  statusBarItem.command = "openRabbit.triggerReview";
  updateStatusBar("idle");
  statusBarItem.show();
  context.subscriptions.push(statusBarItem);
  context.subscriptions.push(
    vscode6.commands.registerCommand("openRabbit.triggerReview", triggerReview),
    vscode6.commands.registerCommand("openRabbit.showChangesWindow", showChangesPanel),
    vscode6.commands.registerCommand("openRabbit.refreshReview", refreshReview),
    vscode6.commands.registerCommand("openRabbit.openSettings", openSettings)
  );
  const lastReview = stateManager.getCurrentReview();
  if (lastReview) {
    sidebarProvider.updateReview(lastReview);
  }
  console.log("Open Rabbit extension activated successfully!");
}
async function handleCommit(commit) {
  const config = vscode6.workspace.getConfiguration("openRabbit");
  const autoReview = config.get("autoReviewOnCommit", true);
  if (!autoReview) {
    return;
  }
  if (commit.hash === stateManager.getLastCommitHash()) {
    return;
  }
  await stateManager.setLastCommitHash(commit.hash);
  vscode6.window.showInformationMessage(
    `New commit detected: ${commit.message.substring(0, 50)}...`,
    "Review Now",
    "Dismiss"
  ).then((selection) => {
    if (selection === "Review Now") {
      triggerReview();
    }
  });
  await triggerReview();
}
async function triggerReview() {
  const apiClient = getApiClient();
  const isHealthy = await apiClient.healthCheck();
  if (!isHealthy) {
    vscode6.window.showErrorMessage(
      "Open Rabbit backend is not available. Please check that the server is running.",
      "Open Settings"
    ).then((selection) => {
      if (selection === "Open Settings") {
        openSettings();
      }
    });
    return;
  }
  const repoInfo = gitWatcher.getCurrentRepository();
  if (!repoInfo) {
    vscode6.window.showWarningMessage("No Git repository found in the workspace.");
    return;
  }
  const changedFiles = await gitWatcher.getUncommittedChanges();
  if (changedFiles.length === 0) {
    vscode6.window.showInformationMessage("No changes to review.");
    return;
  }
  try {
    sidebarProvider.setLoading(true);
    updateStatusBar("running");
    await stateManager.setLoading(true);
    sidebarProvider.updateStatus("Triggering review...");
    const taskResponse = await apiClient.triggerLocalReview({
      repoPath: repoInfo.remoteUrl || repoInfo.rootUri,
      branch: repoInfo.branch,
      changedFiles
    });
    sidebarProvider.updateStatus(`Review started (${taskResponse.task_id})`);
    const result = await apiClient.waitForReviewCompletion(
      taskResponse.task_id,
      (status) => {
        sidebarProvider.updateStatus(`Status: ${status}`);
      }
    );
    await stateManager.setCurrentReview(result);
    sidebarProvider.updateReview(result);
    updateStatusBar("completed", result.summary?.totalIssues);
    const config = vscode6.workspace.getConfiguration("openRabbit");
    if (config.get("showFloatingWindow", true)) {
      showChangesPanel(result);
    }
    const issueCount = result.summary?.totalIssues || 0;
    vscode6.window.showInformationMessage(
      `Code review complete: ${issueCount} issue${issueCount !== 1 ? "s" : ""} found.`,
      "View Details"
    ).then((selection) => {
      if (selection === "View Details") {
        showChangesPanel(result);
      }
    });
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : "Unknown error";
    sidebarProvider.showError(errorMessage);
    updateStatusBar("failed");
    vscode6.window.showErrorMessage(`Code review failed: ${errorMessage}`);
  } finally {
    sidebarProvider.setLoading(false);
    await stateManager.setLoading(false);
  }
}
function showChangesPanel(review) {
  const reviewToShow = review || stateManager.getCurrentReview();
  if (!reviewToShow) {
    vscode6.window.showInformationMessage("No review results to display. Trigger a review first.");
    return;
  }
  const panel = ChangesPanel.createOrShow(
    vscode6.extensions.getExtension("open-rabbit.open-rabbit")?.extensionUri || vscode6.Uri.file(""),
    reviewToShow
  );
  panel.onOpenFile(({ file, line }) => openFileAtLine(file, line));
  panel.onApplySuggestion(({ file, line, suggestion }) => {
    applySuggestion(file, line, suggestion);
  });
}
async function refreshReview() {
  sidebarProvider.refresh();
  const currentReview = stateManager.getCurrentReview();
  if (currentReview) {
    sidebarProvider.updateReview(currentReview);
  }
}
function openSettings() {
  vscode6.commands.executeCommand(
    "workbench.action.openSettings",
    "openRabbit"
  );
}
async function openFileAtLine(file, line) {
  const workspaceFolders = vscode6.workspace.workspaceFolders;
  if (!workspaceFolders) {
    return;
  }
  const filePath = vscode6.Uri.joinPath(workspaceFolders[0].uri, file);
  try {
    const document = await vscode6.workspace.openTextDocument(filePath);
    const editor = await vscode6.window.showTextDocument(document);
    const position = new vscode6.Position(Math.max(0, line - 1), 0);
    editor.selection = new vscode6.Selection(position, position);
    editor.revealRange(
      new vscode6.Range(position, position),
      vscode6.TextEditorRevealType.InCenter
    );
  } catch (error) {
    vscode6.window.showWarningMessage(`Could not open file: ${file}`);
  }
}
async function applySuggestion(file, line, suggestion) {
  if (!suggestion) {
    return;
  }
  const workspaceFolders = vscode6.workspace.workspaceFolders;
  if (!workspaceFolders) {
    return;
  }
  const filePath = vscode6.Uri.joinPath(workspaceFolders[0].uri, file);
  try {
    const document = await vscode6.workspace.openTextDocument(filePath);
    const editor = await vscode6.window.showTextDocument(document);
    const lineIndex = Math.max(0, line - 1);
    const lineText = document.lineAt(lineIndex);
    await editor.edit((editBuilder) => {
      editBuilder.replace(lineText.range, suggestion);
    });
    vscode6.window.showInformationMessage("Suggestion applied!");
  } catch (error) {
    vscode6.window.showErrorMessage(`Could not apply suggestion: ${error}`);
  }
}
function updateStatusBar(status, issueCount) {
  switch (status) {
    case "idle":
      statusBarItem.text = "$(rabbit) Open Rabbit";
      statusBarItem.tooltip = "Click to trigger code review";
      statusBarItem.backgroundColor = void 0;
      break;
    case "running":
      statusBarItem.text = "$(sync~spin) Reviewing...";
      statusBarItem.tooltip = "Code review in progress";
      statusBarItem.backgroundColor = void 0;
      break;
    case "completed":
      const count = issueCount ?? 0;
      statusBarItem.text = `$(check) ${count} issue${count !== 1 ? "s" : ""}`;
      statusBarItem.tooltip = "Code review complete. Click to review again.";
      statusBarItem.backgroundColor = count > 0 ? new vscode6.ThemeColor("statusBarItem.warningBackground") : void 0;
      break;
    case "failed":
      statusBarItem.text = "$(error) Review failed";
      statusBarItem.tooltip = "Code review failed. Click to retry.";
      statusBarItem.backgroundColor = new vscode6.ThemeColor("statusBarItem.errorBackground");
      break;
  }
}
function deactivate() {
  console.log("Open Rabbit extension deactivated");
}
// Annotate the CommonJS export names for ESM import in node:
0 && (module.exports = {
  activate,
  deactivate
});
//# sourceMappingURL=extension.js.map
