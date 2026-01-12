/**
 * State Manager
 * 
 * Manages extension state with workspace-scoped persistence.
 * Each project/workspace gets its own isolated review history.
 */

import * as vscode from 'vscode';
import { ReviewResult, ExtensionState } from '../types';

const STATE_KEY = 'openRabbit.state';
const MAX_HISTORY_SIZE = 50;

export class StateManager {
    private context: vscode.ExtensionContext;
    private state: ExtensionState;

    constructor(context: vscode.ExtensionContext) {
        this.context = context;
        this.state = this.loadState();
    }

    private loadState(): ExtensionState {
        const savedState = this.context.workspaceState.get<ExtensionState>(STATE_KEY);

        if (savedState) {
            // Restore dates 
            if (savedState.reviewHistory) {
                savedState.reviewHistory = savedState.reviewHistory.map(r => ({
                    ...r,
                    createdAt: r.createdAt,
                    completedAt: r.completedAt,
                }));
            }
            return savedState;
        }

        return {
            currentReview: null,
            reviewHistory: [],
            isLoading: false,
            lastCommitHash: null,
        };
    }

    private async saveState(): Promise<void> {
        await this.context.workspaceState.update(STATE_KEY, this.state);
    }

    getCurrentReview(): ReviewResult | null {
        return this.state.currentReview;
    }

    async setCurrentReview(review: ReviewResult): Promise<void> {
        this.state.currentReview = review;

        // Add to history if completed
        if (review.status === 'completed' || review.status === 'failed') {
            this.addToHistory(review);
        }

        await this.saveState();
    }

    async clearCurrentReview(): Promise<void> {
        this.state.currentReview = null;
        await this.saveState();
    }

    getReviewHistory(): ReviewResult[] {
        return this.state.reviewHistory;
    }

    private addToHistory(review: ReviewResult): void {
        // Avoid duplicates
        const existingIndex = this.state.reviewHistory.findIndex(
            r => r.taskId === review.taskId
        );

        if (existingIndex >= 0) {
            // Update existing
            this.state.reviewHistory[existingIndex] = review;
        } else {
            // Add new to front
            this.state.reviewHistory.unshift(review);

            // Trim to max size
            if (this.state.reviewHistory.length > MAX_HISTORY_SIZE) {
                this.state.reviewHistory = this.state.reviewHistory.slice(0, MAX_HISTORY_SIZE);
            }
        }
    }

    async clearHistory(): Promise<void> {
        this.state.reviewHistory = [];
        await this.saveState();
    }

    isLoading(): boolean {
        return this.state.isLoading;
    }

    async setLoading(loading: boolean): Promise<void> {
        this.state.isLoading = loading;
        await this.saveState();
    }

    getLastCommitHash(): string | null {
        return this.state.lastCommitHash;
    }

    async setLastCommitHash(hash: string | null): Promise<void> {
        this.state.lastCommitHash = hash;
        await this.saveState();
    }

    getReviewById(taskId: string): ReviewResult | undefined {
        if (this.state.currentReview?.taskId === taskId) {
            return this.state.currentReview;
        }
        return this.state.reviewHistory.find(r => r.taskId === taskId);
    }

    getWorkspaceId(): string {
        const folders = vscode.workspace.workspaceFolders;
        if (folders && folders.length > 0) {
            return folders[0].uri.fsPath;
        }
        return 'no-workspace';
    }

    async resetState(): Promise<void> {
        this.state = {
            currentReview: null,
            reviewHistory: [],
            isLoading: false,
            lastCommitHash: null,
        };
        await this.saveState();
    }
}

let stateManagerInstance: StateManager | null = null;

export function initializeStateManager(context: vscode.ExtensionContext): StateManager {
    stateManagerInstance = new StateManager(context);
    return stateManagerInstance;
}

export function getStateManager(): StateManager {
    if (!stateManagerInstance) {
        throw new Error('StateManager not initialized. Call initializeStateManager first.');
    }
    return stateManagerInstance;
}
