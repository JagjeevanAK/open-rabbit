import * as vscode from 'vscode';
import {
    ReviewRequest,
    LocalReviewRequest,
    TaskResponse,
    TaskStatusResponse,
    ReviewResult,
    ReviewComment,
    ReviewSummary,
} from '../types';

export class ApiClient {
    private baseUrl!: string;
    private pollingInterval!: number;

    constructor() {
        this.loadConfig();
        vscode.workspace.onDidChangeConfiguration((e) => {
            if (e.affectsConfiguration('openRabbit')) {
                this.loadConfig();
            }
        });
    }

    private loadConfig(): void {
        const config = vscode.workspace.getConfiguration('openRabbit');
        this.baseUrl = config.get<string>('backendUrl', 'http://localhost:8080');
        this.pollingInterval = config.get<number>('pollingInterval', 2000);
    }

    // Trigger a code review for local changes
    async triggerLocalReview(request: LocalReviewRequest): Promise<TaskResponse> {
        const reviewRequest: ReviewRequest = {
            repoUrl: request.repoPath,
            branch: request.branch,
            changedFiles: request.changedFiles.map(f => f.path),
            prDescription: request.commitMessage,
            autoPost: false,
        };

        return this.triggerReview(reviewRequest);
    }

    // Trigger a code review via the backend API
    async triggerReview(request: ReviewRequest): Promise<TaskResponse> {
        const url = `${this.baseUrl}/feedback/review/pr`;

        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    repo_url: request.repoUrl,
                    pr_number: request.prNumber,
                    branch: request.branch,
                    changed_files: request.changedFiles,
                    pr_description: request.prDescription,
                    generate_tests: request.generateTests ?? false,
                    auto_post: request.autoPost ?? false,
                }),
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`API error: ${response.status} - ${errorText}`);
            }

            return await response.json() as TaskResponse;
        } catch (error) {
            if (error instanceof Error) {
                throw new Error(`Failed to trigger review: ${error.message}`);
            }
            throw error;
        }
    }

    // status of a review task
    async getReviewStatus(taskId: string): Promise<TaskStatusResponse> {
        const url = `${this.baseUrl}/feedback/review/status/${taskId}`;

        try {
            const response = await fetch(url);

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`API error: ${response.status} - ${errorText}`);
            }

            return await response.json() as TaskStatusResponse;
        } catch (error) {
            if (error instanceof Error) {
                throw new Error(`Failed to get review status: ${error.message}`);
            }
            throw error;
        }
    }

    // Get the full result of a completed review
    async getReviewResult(taskId: string): Promise<TaskStatusResponse> {
        const url = `${this.baseUrl}/feedback/review/result/${taskId}`;

        try {
            const response = await fetch(url);

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`API error: ${response.status} - ${errorText}`);
            }

            return await response.json() as TaskStatusResponse;
        } catch (error) {
            if (error instanceof Error) {
                throw new Error(`Failed to get review result: ${error.message}`);
            }
            throw error;
        }
    }

    // Poll for review completion
    async waitForReviewCompletion(
        taskId: string,
        onProgress?: (status: string) => void,
        timeoutMs: number = 300000
    ): Promise<ReviewResult> {
        const startTime = Date.now();

        while (Date.now() - startTime < timeoutMs) {
            const status = await this.getReviewStatus(taskId);

            if (onProgress) {
                onProgress(status.status);
            }

            if (status.status === 'completed') {
                return this.transformApiResult(status);
            }

            if (status.status === 'failed') {
                throw new Error(status.error || 'Review failed');
            }

            await this.delay(this.pollingInterval);
        }

        throw new Error('Review timed out');
    }

    // Transform API response to internal ReviewResult format
    private transformApiResult(apiResponse: TaskStatusResponse): ReviewResult {
        const result = apiResponse.result;

        const comments: ReviewComment[] = (result?.comments || []).map(c => ({
            file: c.file,
            line: c.line,
            endLine: c.end_line,
            severity: (c.severity as 'info' | 'warning' | 'error') || 'info',
            category: c.category || 'general',
            message: c.message,
            suggestion: c.suggestion,
            suggestionCode: c.suggestion_code,
        }));

        const summary: ReviewSummary = {
            totalFiles: result?.files_reviewed || 0,
            totalIssues: result?.issues_found || comments.length,
            issuesBySeverity: {
                info: comments.filter(c => c.severity === 'info').length,
                warning: comments.filter(c => c.severity === 'warning').length,
                error: comments.filter(c => c.severity === 'error').length,
            },
            summary: result?.summary || 'Review completed',
        };

        return {
            taskId: apiResponse.task_id,
            status: apiResponse.status as 'pending' | 'running' | 'completed' | 'failed',
            createdAt: apiResponse.created_at,
            completedAt: apiResponse.completed_at,
            summary,
            comments,
            error: apiResponse.error,
        };
    }

    // Health check 
    async healthCheck(): Promise<boolean> {
        try {
            const response = await fetch(`${this.baseUrl}/health`);
            return response.ok;
        } catch {
            return false;
        }
    }

    private delay(ms: number): Promise<void> {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

let apiClientInstance: ApiClient | null = null;

export function getApiClient(): ApiClient {
    if (!apiClientInstance) {
        apiClientInstance = new ApiClient();
    }
    return apiClientInstance;
}
