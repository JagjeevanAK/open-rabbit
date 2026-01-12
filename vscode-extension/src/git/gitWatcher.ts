import * as vscode from 'vscode';
import { FileChange, GitRepository, GitCommit } from '../types';

interface GitExtension {
    getAPI(version: number): GitAPI;
}

interface GitAPI {
    repositories: Repository[];
    onDidOpenRepository: vscode.Event<Repository>;
    onDidCloseRepository: vscode.Event<Repository>;
}

interface Repository {
    rootUri: vscode.Uri;
    state: RepositoryState;
    inputBox: { value: string };
    diff(cached?: boolean): Promise<string>;
    diffWith(ref: string, path?: string): Promise<string>;
    log(options?: { maxEntries?: number }): Promise<Commit[]>;
}

interface RepositoryState {
    HEAD: Branch | undefined;
    refs: Ref[];
    remotes: Remote[];
    workingTreeChanges: Change[];
    indexChanges: Change[];
    mergeChanges: Change[];
    onDidChange: vscode.Event<void>;
}

interface Branch {
    name?: string;
    commit?: string;
    upstream?: { name: string; remote: string };
}

interface Ref {
    type: number;
    name?: string;
    commit?: string;
}

interface Remote {
    name: string;
    fetchUrl?: string;
    pushUrl?: string;
}

interface Change {
    uri: vscode.Uri;
    originalUri: vscode.Uri;
    renameUri?: vscode.Uri;
    status: number;
}

interface Commit {
    hash: string;
    message: string;
    parents: string[];
    authorEmail?: string;
    authorName?: string;
    authorDate?: Date;
    commitDate?: Date;
}

export class GitWatcher implements vscode.Disposable {
    private gitApi: GitAPI | undefined;
    private disposables: vscode.Disposable[] = [];
    private lastCommitHash: string | null = null;

    private _onDidCommit = new vscode.EventEmitter<GitCommit>();
    readonly onDidCommit = this._onDidCommit.event;

    private _onDidChangeRepository = new vscode.EventEmitter<GitRepository | null>();
    readonly onDidChangeRepository = this._onDidChangeRepository.event;

    async initialize(): Promise<boolean> {
        const gitExtension = vscode.extensions.getExtension<GitExtension>('vscode.git');

        if (!gitExtension) {
            vscode.window.showWarningMessage('Git extension not found. Open Rabbit requires Git.');
            return false;
        }

        if (!gitExtension.isActive) {
            await gitExtension.activate();
        }

        this.gitApi = gitExtension.exports.getAPI(1);

        // Watch for repository changes
        this.disposables.push(
            this.gitApi.onDidOpenRepository(() => this.onRepositoryOpen()),
            this.gitApi.onDidCloseRepository(() => this.onRepositoryClose())
        );

        // Set up watchers for existing repositories
        for (const repo of this.gitApi.repositories) {
            this.watchRepository(repo);
        }

        // Initialize last commit hash
        await this.updateLastCommitHash();

        return true;
    }

    private watchRepository(repo: Repository): void {
        const stateChangeDisposable = repo.state.onDidChange(() => {
            this.checkForNewCommit(repo);
        });
        this.disposables.push(stateChangeDisposable);
    }

    private async checkForNewCommit(repo: Repository): Promise<void> {
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

                // Get changed files from the commit
                const changedFiles = await this.getCommitChangedFiles(repo, currentHash, previousHash);

                const commit: GitCommit = {
                    hash: latestCommit.hash,
                    message: latestCommit.message,
                    author: latestCommit.authorName || 'Unknown',
                    date: latestCommit.commitDate || new Date(),
                    files: changedFiles,
                };

                this._onDidCommit.fire(commit);
            }
        } catch (error) {
            console.error('Error getting commit info:', error);
        }
    }

    private async getCommitChangedFiles(
        repo: Repository,
        currentHash: string,
        previousHash: string | null
    ): Promise<string[]> {
        try {
            const diffRef = previousHash || `${currentHash}~1`;
            const diff = await repo.diffWith(diffRef);

            // Parse diff to extract file paths
            const files: string[] = [];
            const diffLines = diff.split('\n');

            for (const line of diffLines) {
                if (line.startsWith('diff --git')) {
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

    private async updateLastCommitHash(): Promise<void> {
        const repo = this.getActiveRepository();
        if (repo) {
            this.lastCommitHash = repo.state.HEAD?.commit || null;
        }
    }

    private onRepositoryOpen(): void {
        const repo = this.getActiveRepository();
        if (repo) {
            this.watchRepository(repo);
            this._onDidChangeRepository.fire(this.getGitRepositoryInfo(repo));
        }
    }

    private onRepositoryClose(): void {
        this._onDidChangeRepository.fire(null);
    }

    // Get active repo
    getActiveRepository(): Repository | undefined {
        return this.gitApi?.repositories[0];
    }

    // Get current repo info
    getCurrentRepository(): GitRepository | null {
        const repo = this.getActiveRepository();
        if (!repo) {
            return null;
        }
        return this.getGitRepositoryInfo(repo);
    }

    private getGitRepositoryInfo(repo: Repository): GitRepository {
        const remotes = repo.state.remotes;
        const originRemote = remotes.find(r => r.name === 'origin');

        return {
            rootUri: repo.rootUri.fsPath,
            name: repo.rootUri.path.split('/').pop() || '',
            branch: repo.state.HEAD?.name || 'main',
            remoteUrl: originRemote?.fetchUrl || originRemote?.pushUrl,
        };
    }

    // Get uncommitted changes (working tree + staged)
    async getUncommittedChanges(): Promise<FileChange[]> {
        const repo = this.getActiveRepository();
        if (!repo) {
            return [];
        }

        const changes: FileChange[] = [];

        const allChanges = [
            ...repo.state.workingTreeChanges,
            ...repo.state.indexChanges,
        ];

        for (const change of allChanges) {
            const status = this.mapChangeStatus(change.status);
            changes.push({
                path: vscode.workspace.asRelativePath(change.uri),
                status,
            });
        }

        // Remove duplicates
        const seen = new Set<string>();
        return changes.filter(c => {
            if (seen.has(c.path)) {
                return false;
            }
            seen.add(c.path);
            return true;
        });
    }

    // Get the diff for uncommitted changes (staged and unstaged)
    async getUncommittedDiff(): Promise<string> {
        const repo = this.getActiveRepository();
        if (!repo) {
            return '';
        }

        try {
            const stagedDiff = await repo.diff(true);
            const unstagedDiff = await repo.diff(false);
            return `${stagedDiff}\n${unstagedDiff}`;
        } catch {
            return '';
        }
    }

    private mapChangeStatus(status: number): FileChange['status'] {
        // Git status codes: 
        // 0 = Index Modified, 
        // 3 = Index Renamed, 
        // 1,5 = Index Added, 
        // 2,6 = Index Deleted, etc.
        switch (status) {
            case 1: 
            case 5: 
                return 'added';
            case 2: 
            case 6: 
                return 'deleted';
            case 3: 
                return 'renamed';
            default:
                return 'modified';
        }
    }

    // current branch name
    getCurrentBranch(): string | null {
        const repo = this.getActiveRepository();
        return repo?.state.HEAD?.name || null;
    }

    // last commit hash
    getLastCommitHash(): string | null {
        return this.lastCommitHash;
    }

    dispose(): void {
        this._onDidCommit.dispose();
        this._onDidChangeRepository.dispose();
        this.disposables.forEach(d => d.dispose());
    }
}

let gitWatcherInstance: GitWatcher | null = null;

export function getGitWatcher(): GitWatcher {
    if (!gitWatcherInstance) {
        gitWatcherInstance = new GitWatcher();
    }
    return gitWatcherInstance;
}
