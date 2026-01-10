
// Review Request/Response Types

export interface ReviewRequest {
    repoUrl: string;
    prNumber?: number;
    branch?: string;
    changedFiles?: string[];
    prDescription?: string;
    generateTests?: boolean;
    autoPost?: boolean;
}

export interface LocalReviewRequest {
    repoPath: string;
    branch: string;
    changedFiles: FileChange[];
    commitHash?: string;
    commitMessage?: string;
}

export interface FileChange {
    path: string;
    status: 'added' | 'modified' | 'deleted' | 'renamed';
    content?: string;
    diff?: string;
}

// Review Result Types

export type ReviewStatus = 'pending' | 'running' | 'completed' | 'failed';

export type Severity = 'info' | 'warning' | 'error';

export interface ReviewComment {
    file: string;
    line: number;
    endLine?: number;
    severity: Severity;
    category: string;
    message: string;
    suggestion?: string;
    suggestionCode?: string;
}

export interface ReviewSummary {
    totalFiles: number;
    totalIssues: number;
    issuesBySeverity: {
        info: number;
        warning: number;
        error: number;
    };
    overallScore?: number;
    summary: string;
}

export interface ReviewResult {
    taskId: string;
    status: ReviewStatus;
    createdAt: string;
    completedAt?: string;
    summary?: ReviewSummary;
    comments: ReviewComment[];
    error?: string;
}

// API Response Types

export interface TaskResponse {
    task_id: string;
    status: string;
    message: string;
}

export interface TaskStatusResponse {
    task_id: string;
    status: string;
    created_at: string;
    completed_at?: string;
    result?: ReviewApiResult;
    error?: string;
}

export interface ReviewApiResult {
    summary?: string;
    comments?: ApiComment[];
    files_reviewed?: number;
    issues_found?: number;
}

export interface ApiComment {
    file: string;
    line: number;
    end_line?: number;
    severity: string;
    category: string;
    message: string;
    suggestion?: string;
    suggestion_code?: string;
}

// ===== Git Types =====

export interface GitRepository {
    rootUri: string;
    name: string;
    branch: string;
    remoteUrl?: string;
}

export interface GitCommit {
    hash: string;
    message: string;
    author: string;
    date: Date;
    files: string[];
}

// ===== Webview Message Types =====

export type WebviewMessageCommand =
    | 'refresh'
    | 'triggerReview'
    | 'showChanges'
    | 'openSettings'
    | 'openFile'
    | 'applySuggestion'
    | 'dismissComment';

export interface WebviewMessage {
    command: WebviewMessageCommand;
    payload?: unknown;
}

export interface ExtensionMessage {
    type: 'reviewUpdate' | 'statusUpdate' | 'error' | 'loading';
    data: unknown;
}

// Configuration Types

export interface ExtensionConfig {
    backendUrl: string;
    autoReviewOnCommit: boolean;
    showFloatingWindow: boolean;
    severityThreshold: Severity;
    pollingInterval: number;
}

// State Types

export interface ExtensionState {
    currentReview: ReviewResult | null;
    reviewHistory: ReviewResult[];
    isLoading: boolean;
    lastCommitHash: string | null;
}
