/**
 * GitHub Git Data API utilities for atomic multi-file commits.
 * 
 * Uses the low-level Git Data API to create commits with multiple files
 * in a single atomic operation (blob -> tree -> commit -> update ref).
 */

import type { GitHubClient } from "../types/github.js";

export interface FileToCommit {
    path: string;
    content: string;
}

export interface CommitOptions {
    owner: string;
    repo: string;
    branch: string;
    files: FileToCommit[];
    message: string;
}

export interface CommitResult {
    success: boolean;
    sha?: string;
    commitUrl?: string;
    error?: string;
}

/**
 * Create an atomic multi-file commit using GitHub's Git Data API.
 * 
 * This is more reliable than creating multiple single-file commits because:
 * 1. All files are committed in a single operation
 * 2. If any file fails, the entire commit is rolled back
 * 3. Only one commit appears in history (cleaner git log)
 * 
 * Flow:
 * 1. Get current branch ref (SHA of latest commit)
 * 2. Get the tree of the latest commit
 * 3. Create blobs for each new file
 * 4. Create a new tree with the new blobs
 * 5. Create a new commit pointing to the new tree
 * 6. Update the branch ref to point to the new commit
 * 
 * @param octokit - Authenticated Octokit instance
 * @param options - Commit options including files, message, branch
 * @returns CommitResult with success status and commit SHA
 */
export async function createMultiFileCommit(
    octokit: GitHubClient,
    options: CommitOptions
): Promise<CommitResult> {
    const { owner, repo, branch, files, message } = options;

    if (files.length === 0) {
        return { success: false, error: "No files provided to commit" };
    }

    try {
        // Step 1: Get the current branch reference (SHA of latest commit)
        const { data: refData } = await octokit.git.getRef({
            owner,
            repo,
            ref: `heads/${branch}`,
        });
        const latestCommitSha = refData.object.sha;

        // Step 2: Get the tree of the latest commit
        const { data: commitData } = await octokit.git.getCommit({
            owner,
            repo,
            commit_sha: latestCommitSha,
        });
        const baseTreeSha = commitData.tree.sha;

        // Step 3: Create blobs for each file
        const treeItems: Array<{
            path: string;
            mode: "100644";
            type: "blob";
            sha: string;
        }> = [];

        for (const file of files) {
            const { data: blobData } = await octokit.git.createBlob({
                owner,
                repo,
                content: Buffer.from(file.content).toString("base64"),
                encoding: "base64",
            });

            treeItems.push({
                path: file.path,
                mode: "100644", // Regular file
                type: "blob",
                sha: blobData.sha,
            });
        }

        // Step 4: Create a new tree with the new blobs
        const { data: newTree } = await octokit.git.createTree({
            owner,
            repo,
            base_tree: baseTreeSha,
            tree: treeItems,
        });

        // Step 5: Create a new commit pointing to the new tree
        const { data: newCommit } = await octokit.git.createCommit({
            owner,
            repo,
            message,
            tree: newTree.sha,
            parents: [latestCommitSha],
        });

        // Step 6: Update the branch ref to point to the new commit
        await octokit.git.updateRef({
            owner,
            repo,
            ref: `heads/${branch}`,
            sha: newCommit.sha,
        });

        const commitUrl = `https://github.com/${owner}/${repo}/commit/${newCommit.sha}`;

        console.log(`[githubCommit] Successfully committed ${files.length} files to ${owner}/${repo}@${branch}`);
        console.log(`[githubCommit] Commit SHA: ${newCommit.sha}`);

        return {
            success: true,
            sha: newCommit.sha,
            commitUrl,
        };
    } catch (error: any) {
        console.error("[githubCommit] Error creating multi-file commit:", error);
        
        // Extract meaningful error message
        let errorMessage = "Unknown error";
        if (error.message) {
            errorMessage = error.message;
        }
        if (error.response?.data?.message) {
            errorMessage = error.response.data.message;
        }
        
        return {
            success: false,
            error: errorMessage,
        };
    }
}

/**
 * Check if a branch exists in the repository.
 */
export async function branchExists(
    octokit: GitHubClient,
    owner: string,
    repo: string,
    branch: string
): Promise<boolean> {
    try {
        await octokit.git.getRef({
            owner,
            repo,
            ref: `heads/${branch}`,
        });
        return true;
    } catch (error: any) {
        if (error.status === 404) {
            return false;
        }
        throw error;
    }
}

/**
 * Get the SHA of the latest commit on a branch.
 */
export async function getLatestCommitSha(
    octokit: GitHubClient,
    owner: string,
    repo: string,
    branch: string
): Promise<string | null> {
    try {
        const { data: refData } = await octokit.git.getRef({
            owner,
            repo,
            ref: `heads/${branch}`,
        });
        return refData.object.sha;
    } catch (error: any) {
        if (error.status === 404) {
            return null;
        }
        throw error;
    }
}

/**
 * Get file content from a specific branch.
 * Returns null if file doesn't exist.
 */
export async function getFileContent(
    octokit: GitHubClient,
    owner: string,
    repo: string,
    path: string,
    branch: string
): Promise<string | null> {
    try {
        const { data } = await octokit.repos.getContent({
            owner,
            repo,
            path,
            ref: branch,
        });

        if ("content" in data && data.content && data.encoding === "base64") {
            return Buffer.from(data.content, "base64").toString("utf-8");
        }

        return null;
    } catch (error: any) {
        if (error.status === 404) {
            return null;
        }
        throw error;
    }
}

/**
 * List files in a directory on a specific branch.
 * Returns empty array if directory doesn't exist.
 */
export async function listDirectoryFiles(
    octokit: GitHubClient,
    owner: string,
    repo: string,
    path: string,
    branch: string
): Promise<string[]> {
    try {
        const { data } = await octokit.repos.getContent({
            owner,
            repo,
            path,
            ref: branch,
        });

        if (Array.isArray(data)) {
            return data
                .filter((item) => item.type === "file")
                .map((item) => item.path);
        }

        return [];
    } catch (error: any) {
        if (error.status === 404) {
            return [];
        }
        throw error;
    }
}

/**
 * Recursively list all files in a repository matching a pattern.
 */
export async function listAllFiles(
    octokit: GitHubClient,
    owner: string,
    repo: string,
    branch: string,
    path: string = ""
): Promise<string[]> {
    const files: string[] = [];

    try {
        const { data } = await octokit.repos.getContent({
            owner,
            repo,
            path,
            ref: branch,
        });

        if (Array.isArray(data)) {
            for (const item of data) {
                if (item.type === "file") {
                    files.push(item.path);
                } else if (item.type === "dir") {
                    // Recursively get files from subdirectory
                    const subFiles = await listAllFiles(octokit, owner, repo, branch, item.path);
                    files.push(...subFiles);
                }
            }
        }
    } catch (error: any) {
        if (error.status !== 404) {
            throw error;
        }
    }

    return files;
}
