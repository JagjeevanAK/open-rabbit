// Extends probot's Octokit types to be compatible with our utility functions.
// This approach uses declaration merging instead of creating wrapper types.

import type { Context } from "probot";

// Extract the Octokit type from Probot's Context
export type ProbotOctokit = Context["octokit"];

// Git tree item - properties may be optional in API response
export interface GitTreeItem {
    path?: string;
    mode?: string;
    type?: string;
    sha?: string;
    size?: number;
    url?: string;
}

// Tree item for creating a new tree
export interface CreateTreeItem {
    path: string;
    mode: "100644" | "100755" | "040000" | "160000" | "120000";
    type: "blob" | "tree" | "commit";
    sha: string;
}

// Repository content item (file or directory)
export interface RepoContentItem {
    name: string;
    path: string;
    sha: string;
    type: "file" | "dir" | "symlink" | "submodule";
    content?: string;
    encoding?: string;
}

// Uses Probot's Octokit type directly - this ensures compatibility
// with context.octokit while still providing type safety.
export type GitHubClient = ProbotOctokit;

export {};
