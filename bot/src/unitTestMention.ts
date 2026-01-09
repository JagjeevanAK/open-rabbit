/**
 * Unit Test Mention Handler
 * 
 * Handles @openrabbit unit-test mentions on pull requests.
 * When triggered, generates unit tests for changed files and commits them
 * directly to the PR branch.
 * 
 * Supported triggers:
 * - @openrabbit unit-test
 * - @openrabbit unit-tests
 * - @openrabbit generate-tests
 * - @open-rabbit unit-test (with hyphen)
 * 
 * Optional file arguments:
 * - @openrabbit unit-test src/utils.ts src/api.ts
 */

import { Probot, Context } from "probot";
import axios from "axios";
import {
    detectTestFramework,
    getExistingTestFiles,
    hasExistingTests,
    filterTestableFiles,
} from "./utils/testDetector.js";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8080";

// Rate limiting: 10 minutes between invocations per PR
const RATE_LIMIT_MS = 10 * 60 * 1000;
const rateLimitStore = new Map<string, number>();

// Track active tasks to prevent duplicate processing
const activeTasks = new Set<string>();

/**
 * Command detection patterns
 */
const UNIT_TEST_PATTERNS = [
    /^@open-?rabbit\s+unit-?tests?\b/i,
    /^@open-?rabbit\s+generate-?tests?\b/i,
];

/**
 * Detect if a comment contains a unit test command.
 * 
 * @param body - Comment body
 * @returns Object with triggered flag and optional target files
 */
export function detectUnitTestCommand(body: string): {
    triggered: boolean;
    targetFiles: string[];
} {
    const lines = body.split("\n");
    
    for (const line of lines) {
        const trimmed = line.trim();
        
        for (const pattern of UNIT_TEST_PATTERNS) {
            if (pattern.test(trimmed)) {
                // Extract file arguments after the command
                const afterCommand = trimmed.replace(pattern, "").trim();
                const targetFiles = afterCommand
                    .split(/\s+/)
                    .filter(f => f.length > 0 && !f.startsWith("@"))
                    .map(f => f.trim());
                
                return { triggered: true, targetFiles };
            }
        }
    }
    
    return { triggered: false, targetFiles: [] };
}

/**
 * Get a unique key for rate limiting a PR.
 */
function getRateLimitKey(owner: string, repo: string, prNumber: number): string {
    return `${owner}/${repo}#${prNumber}`;
}

/**
 * Check if a PR is rate limited.
 */
function isRateLimited(owner: string, repo: string, prNumber: number): boolean {
    const key = getRateLimitKey(owner, repo, prNumber);
    const lastRun = rateLimitStore.get(key);
    
    if (!lastRun) return false;
    
    const elapsed = Date.now() - lastRun;
    return elapsed < RATE_LIMIT_MS;
}

/**
 * Get remaining rate limit time in minutes.
 */
function getRateLimitRemaining(owner: string, repo: string, prNumber: number): number {
    const key = getRateLimitKey(owner, repo, prNumber);
    const lastRun = rateLimitStore.get(key);
    
    if (!lastRun) return 0;
    
    const remaining = RATE_LIMIT_MS - (Date.now() - lastRun);
    return Math.ceil(remaining / 60000);
}

/**
 * Update rate limit timestamp.
 */
function updateRateLimit(owner: string, repo: string, prNumber: number): void {
    const key = getRateLimitKey(owner, repo, prNumber);
    rateLimitStore.set(key, Date.now());
}

/**
 * Check if a task is already active for this PR.
 */
function isTaskActive(owner: string, repo: string, prNumber: number): boolean {
    const key = getRateLimitKey(owner, repo, prNumber);
    return activeTasks.has(key);
}

/**
 * Mark task as active.
 */
function setTaskActive(owner: string, repo: string, prNumber: number, active: boolean): void {
    const key = getRateLimitKey(owner, repo, prNumber);
    if (active) {
        activeTasks.add(key);
    } else {
        activeTasks.delete(key);
    }
}

/**
 * Check if a PR is mergeable (no conflicts).
 */
async function checkPRMergeable(
    context: Context<"issue_comment.created">,
    owner: string,
    repo: string,
    prNumber: number
): Promise<{ mergeable: boolean; reason?: string }> {
    try {
        const { data: pr } = await context.octokit.pulls.get({
            owner,
            repo,
            pull_number: prNumber,
        });
        
        // Check if PR is open
        if (pr.state !== "open") {
            return { mergeable: false, reason: "PR is not open" };
        }
        
        // Check mergeable status
        // Note: mergeable can be null if GitHub hasn't computed it yet
        if (pr.mergeable === false) {
            return { mergeable: false, reason: "PR has merge conflicts that must be resolved first" };
        }
        
        if (pr.mergeable_state === "dirty") {
            return { mergeable: false, reason: "PR has merge conflicts that must be resolved first" };
        }
        
        return { mergeable: true };
    } catch (error) {
        console.error("[unitTestMention] Error checking PR mergeable status:", error);
        return { mergeable: false, reason: "Failed to check PR status" };
    }
}

/**
 * Get changed files from a PR.
 */
async function getPRChangedFiles(
    context: Context<"issue_comment.created">,
    owner: string,
    repo: string,
    prNumber: number
): Promise<string[]> {
    try {
        const files: string[] = [];
        let page = 1;
        
        while (true) {
            const { data } = await context.octokit.pulls.listFiles({
                owner,
                repo,
                pull_number: prNumber,
                per_page: 100,
                page,
            });
            
            if (data.length === 0) break;
            
            files.push(...data.map(f => f.filename));
            
            if (data.length < 100) break;
            page++;
        }
        
        return files;
    } catch (error) {
        console.error("[unitTestMention] Error getting PR files:", error);
        return [];
    }
}

/**
 * Get PR details including head branch.
 */
async function getPRDetails(
    context: Context<"issue_comment.created">,
    owner: string,
    repo: string,
    prNumber: number
): Promise<{
    headBranch: string;
    headSha: string;
    baseBranch: string;
    headOwner: string;
    headRepo: string;
} | null> {
    try {
        const { data: pr } = await context.octokit.pulls.get({
            owner,
            repo,
            pull_number: prNumber,
        });
        
        return {
            headBranch: pr.head.ref,
            headSha: pr.head.sha,
            baseBranch: pr.base.ref,
            headOwner: pr.head.repo?.owner.login || owner,
            headRepo: pr.head.repo?.name || repo,
        };
    } catch (error) {
        console.error("[unitTestMention] Error getting PR details:", error);
        return null;
    }
}

/**
 * Post an acknowledgment comment.
 */
async function postAcknowledgment(
    context: Context<"issue_comment.created">,
    message: string
): Promise<number | null> {
    try {
        const { data: comment } = await context.octokit.issues.createComment({
            ...context.issue(),
            body: message,
        });
        return comment.id;
    } catch (error) {
        console.error("[unitTestMention] Error posting comment:", error);
        return null;
    }
}

/**
 * Update an existing comment.
 */
async function updateComment(
    context: Context<"issue_comment.created">,
    commentId: number,
    message: string
): Promise<void> {
    try {
        await context.octokit.issues.updateComment({
            owner: context.payload.repository.owner.login,
            repo: context.payload.repository.name,
            comment_id: commentId,
            body: message,
        });
    } catch (error) {
        console.error("[unitTestMention] Error updating comment:", error);
    }
}

/**
 * Handle the unit test mention command.
 */
async function handleUnitTestMention(
    context: Context<"issue_comment.created">,
    targetFiles: string[]
): Promise<void> {
    const owner = context.payload.repository.owner.login;
    const repo = context.payload.repository.name;
    const prNumber = context.payload.issue.number;
    const installationId = context.payload.installation?.id;
    const requestedBy = context.payload.comment.user.login;
    
    console.log(`[unitTestMention] Processing unit test request for ${owner}/${repo}#${prNumber}`);
    
    // Check if already processing
    if (isTaskActive(owner, repo, prNumber)) {
        await postAcknowledgment(
            context,
            "A unit test generation is already in progress for this PR. Please wait for it to complete."
        );
        return;
    }
    
    // Check rate limit
    if (isRateLimited(owner, repo, prNumber)) {
        const remaining = getRateLimitRemaining(owner, repo, prNumber);
        await postAcknowledgment(
            context,
            `Please wait ${remaining} more minute(s) before requesting unit tests again.`
        );
        return;
    }
    
    // Check PR mergeable status
    const mergeableCheck = await checkPRMergeable(context, owner, repo, prNumber);
    if (!mergeableCheck.mergeable) {
        await postAcknowledgment(
            context,
            `Cannot generate unit tests: ${mergeableCheck.reason}\n\nPlease resolve any issues and try again.`
        );
        return;
    }
    
    // Get PR details
    const prDetails = await getPRDetails(context, owner, repo, prNumber);
    if (!prDetails) {
        await postAcknowledgment(
            context,
            "Failed to get PR details. Please try again."
        );
        return;
    }
    
    // Get changed files
    const allChangedFiles = await getPRChangedFiles(context, owner, repo, prNumber);
    if (allChangedFiles.length === 0) {
        await postAcknowledgment(
            context,
            "No changed files found in this PR."
        );
        return;
    }
    
    // Determine which files to generate tests for
    let filesToTest: string[];
    
    if (targetFiles.length > 0) {
        // User specified specific files
        filesToTest = targetFiles.filter(f => allChangedFiles.includes(f));
        
        if (filesToTest.length === 0) {
            await postAcknowledgment(
                context,
                `None of the specified files were found in this PR's changes.\n\nSpecified: ${targetFiles.join(", ")}\n\nChanged files: ${allChangedFiles.slice(0, 10).join(", ")}${allChangedFiles.length > 10 ? "..." : ""}`
            );
            return;
        }
    } else {
        // Filter testable files
        filesToTest = filterTestableFiles(allChangedFiles);
    }
    
    if (filesToTest.length === 0) {
        await postAcknowledgment(
            context,
            "No testable source files found in the PR changes.\n\nTest files, config files, and non-code files are automatically excluded."
        );
        return;
    }
    
    // Detect test framework and get existing tests
    const frameworkInfo = await detectTestFramework(
        context.octokit,
        owner,
        repo,
        prDetails.headBranch
    );
    
    const existingTestFiles = await getExistingTestFiles(
        context.octokit,
        owner,
        repo,
        prDetails.headBranch
    );
    
    // Filter out files that already have tests
    const filesNeedingTests = filesToTest.filter(
        file => !hasExistingTests(file, existingTestFiles)
    );
    
    if (filesNeedingTests.length === 0) {
        await postAcknowledgment(
            context,
            `All specified files already have tests.\n\nFiles checked: ${filesToTest.join(", ")}`
        );
        return;
    }
    
    // Mark task as active and update rate limit
    setTaskActive(owner, repo, prNumber, true);
    updateRateLimit(owner, repo, prNumber);
    
    // Post acknowledgment
    const skippedCount = filesToTest.length - filesNeedingTests.length;
    let ackMessage = `Starting unit test generation...\n\n`;
    ackMessage += `**Files to test:** ${filesNeedingTests.length}\n`;
    ackMessage += filesNeedingTests.map(f => `- \`${f}\``).join("\n");
    
    if (skippedCount > 0) {
        ackMessage += `\n\n**Skipped:** ${skippedCount} file(s) already have tests`;
    }
    
    ackMessage += `\n\n**Test framework:** ${frameworkInfo.framework}`;
    ackMessage += `\n**Target branch:** \`${prDetails.headBranch}\``;
    ackMessage += `\n\nI'll commit the tests directly to this PR branch when ready.`;
    
    const ackCommentId = await postAcknowledgment(context, ackMessage);
    
    try {
        // Call backend to generate tests
        const response = await axios.post(
            `${BACKEND_URL}/bot/generate-pr-tests`,
            {
                owner,
                repo,
                pr_number: prNumber,
                branch: prDetails.headBranch,
                base_branch: prDetails.baseBranch,
                head_owner: prDetails.headOwner,
                head_repo: prDetails.headRepo,
                installation_id: installationId,
                target_files: filesNeedingTests,
                changed_files: allChangedFiles,
                existing_test_files: existingTestFiles,
                test_framework: frameworkInfo.framework,
                test_directory: frameworkInfo.testDirectory,
                requested_by: requestedBy,
            },
            { timeout: 30000 }
        );
        
        const { task_id } = response.data;
        
        console.log(`[unitTestMention] Task ${task_id} created for ${owner}/${repo}#${prNumber}`);
        
        // Start polling for task completion
        pollTaskStatus(
            context,
            task_id,
            owner,
            repo,
            prNumber,
            prDetails.headBranch,
            filesNeedingTests,
            ackCommentId
        );
        
    } catch (error: any) {
        setTaskActive(owner, repo, prNumber, false);
        
        console.error("[unitTestMention] Error calling backend:", error);
        
        const errorMessage = error.response?.data?.detail || error.message || "Unknown error";
        
        if (ackCommentId) {
            await updateComment(
                context,
                ackCommentId,
                `Failed to start unit test generation.\n\n**Error:** ${errorMessage}`
            );
        } else {
            await postAcknowledgment(
                context,
                `Failed to start unit test generation.\n\n**Error:** ${errorMessage}`
            );
        }
    }
}

/**
 * Poll backend for task completion status.
 */
async function pollTaskStatus(
    context: Context<"issue_comment.created">,
    taskId: string,
    owner: string,
    repo: string,
    prNumber: number,
    _branch: string,
    _filesNeedingTests: string[],
    ackCommentId: number | null
): Promise<void> {
    const maxAttempts = 120; // 10 minutes at 5 second intervals
    let attempts = 0;
    
    const interval = setInterval(async () => {
        attempts++;
        
        try {
            const response = await axios.get(
                `${BACKEND_URL}/bot/task-status/${taskId}`,
                { timeout: 10000 }
            );
            
            const { status, result, error } = response.data;
            
            if (status === "completed") {
                clearInterval(interval);
                setTaskActive(owner, repo, prNumber, false);
                
                const generated = result?.generated_files || [];
                const failed = result?.failed_files || [];
                const commitSha = result?.commit_sha;
                const commitUrl = result?.commit_url;
                
                let message = `Unit test generation completed!\n\n`;
                
                if (generated.length > 0) {
                    message += `**Tests generated:** ${generated.length}\n`;
                    message += generated.map((f: string) => `- \`${f}\``).join("\n");
                    message += `\n\n`;
                }
                
                if (commitSha) {
                    message += `**Commit:** [\`${commitSha.substring(0, 7)}\`](${commitUrl})\n`;
                }
                
                if (failed.length > 0) {
                    message += `\n**Failed to generate tests for:**\n`;
                    message += failed.map((f: any) => `- \`${f.file}\`: ${f.reason}`).join("\n");
                }
                
                if (generated.length === 0 && failed.length === 0) {
                    message = `No tests were generated. The target files may not have testable code or the generation failed.`;
                }
                
                if (ackCommentId) {
                    await updateComment(context, ackCommentId, message);
                } else {
                    await postAcknowledgment(context, message);
                }
                
            } else if (status === "failed") {
                clearInterval(interval);
                setTaskActive(owner, repo, prNumber, false);
                
                const message = `Unit test generation failed.\n\n**Error:** ${error || "Unknown error"}`;
                
                if (ackCommentId) {
                    await updateComment(context, ackCommentId, message);
                } else {
                    await postAcknowledgment(context, message);
                }
                
            } else if (attempts >= maxAttempts) {
                clearInterval(interval);
                setTaskActive(owner, repo, prNumber, false);
                
                const message = `Unit test generation timed out after ${maxAttempts * 5} seconds.\n\n**Task ID:** \`${taskId}\``;
                
                if (ackCommentId) {
                    await updateComment(context, ackCommentId, message);
                } else {
                    await postAcknowledgment(context, message);
                }
            }
            
        } catch (error) {
            console.error("[unitTestMention] Error polling task status:", error);
            
            // Continue polling on transient errors
            if (attempts >= maxAttempts) {
                clearInterval(interval);
                setTaskActive(owner, repo, prNumber, false);
            }
        }
    }, 5000); // Poll every 5 seconds
}

/**
 * Register the unit test mention handler with Probot.
 */
export default (app: Probot) => {
    app.on("issue_comment.created", async (context) => {
        // Only process PR comments
        if (!context.payload.issue.pull_request) return;
        
        // Ignore bot comments
        const author = context.payload.comment.user.login;
        if (author.includes("[bot]") || author === "open-rabbit" || author === "openrabbit") {
            return;
        }
        
        const body = context.payload.comment.body;
        const { triggered, targetFiles } = detectUnitTestCommand(body);
        
        if (triggered) {
            await handleUnitTestMention(context, targetFiles);
        }
    });
    
    console.log("[unitTestMention] Unit test mention handler registered");
};

// Clean up old rate limit entries periodically (every hour)
setInterval(() => {
    const now = Date.now();
    let cleaned = 0;
    
    for (const [key, timestamp] of rateLimitStore.entries()) {
        if (now - timestamp > RATE_LIMIT_MS * 2) {
            rateLimitStore.delete(key);
            cleaned++;
        }
    }
    
    if (cleaned > 0) {
        console.log(`[unitTestMention] Cleaned up ${cleaned} old rate limit entries`);
    }
}, 60 * 60 * 1000);
