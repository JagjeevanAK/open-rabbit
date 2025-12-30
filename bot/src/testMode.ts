import { Request, Response } from "express";
import { Probot, ApplicationFunctionOptions } from "probot";
import { Octokit } from "@octokit/rest";
import axios from "axios";
import * as fs from "fs";
import * as path from "path";
import express from "express";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8080";
const GITHUB_PAT = process.env.GITHUB_PAT;
const TEST_MODE = process.env.TEST_MODE === "true";

// Output directory for test results
const OUTPUT_DIR = path.join(process.cwd(), "test-output");

/**
 * Review comment structure for inline PR comments
 */
interface ReviewComment {
    path: string;
    line: number;
    body: string;
    start_line?: number;
    side?: "LEFT" | "RIGHT";
    start_side?: "LEFT" | "RIGHT";
}

/**
 * Request body for /test/trigger-review endpoint
 */
interface TestTriggerReviewRequest {
    owner: string;
    repo: string;
    pull_number: number;
    body?: string;
    comments?: ReviewComment[];
    event?: "COMMENT" | "APPROVE" | "REQUEST_CHANGES";
    dry_run?: boolean;  // If true, save to file instead of posting
}

/**
 * Parse GitHub PR URL to extract owner, repo, and PR number
 */
function parsePrUrl(url: string): { owner: string; repo: string; pr_number: number } | null {
    // Match patterns like:
    // https://github.com/owner/repo/pull/123
    // github.com/owner/repo/pull/123
    const match = url.match(/github\.com\/([^\/]+)\/([^\/]+)\/pull\/(\d+)/);
    if (match) {
        return {
            owner: match[1],
            repo: match[2],
            pr_number: parseInt(match[3], 10),
        };
    }
    return null;
}

/**
 * Save review to file for inspection (dry run mode)
 */
function saveReviewToFile(
    owner: string,
    repo: string,
    prNumber: number,
    summary: string | undefined,
    comments: ReviewComment[]
): string {
    // Ensure output directory exists
    if (!fs.existsSync(OUTPUT_DIR)) {
        fs.mkdirSync(OUTPUT_DIR, { recursive: true });
    }

    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const filename = `review-${owner}-${repo}-${prNumber}-${timestamp}.md`;
    const filepath = path.join(OUTPUT_DIR, filename);

    let content = `# Code Review for ${owner}/${repo}#${prNumber}\n\n`;
    content += `**Generated:** ${new Date().toISOString()}\n\n`;
    content += `---\n\n`;

    // Summary section
    if (summary) {
        content += `## Summary\n\n${summary}\n\n`;
    }

    // Inline comments section
    if (comments && comments.length > 0) {
        content += `---\n\n## Inline Comments (${comments.length})\n\n`;
        
        // Group by file
        const commentsByFile: { [key: string]: ReviewComment[] } = {};
        for (const comment of comments) {
            if (!commentsByFile[comment.path]) {
                commentsByFile[comment.path] = [];
            }
            commentsByFile[comment.path].push(comment);
        }

        for (const [filePath, fileComments] of Object.entries(commentsByFile)) {
            content += `### \`${filePath}\`\n\n`;
            
            // Sort by line number
            fileComments.sort((a, b) => a.line - b.line);
            
            for (const comment of fileComments) {
                const lineInfo = comment.start_line 
                    ? `Lines ${comment.start_line}-${comment.line}`
                    : `Line ${comment.line}`;
                
                content += `#### ${lineInfo}\n\n`;
                content += `${comment.body}\n\n`;
                content += `---\n\n`;
            }
        }
    } else {
        content += `## Inline Comments\n\nNo inline comments generated.\n\n`;
    }

    fs.writeFileSync(filepath, content);
    return filepath;
}

/**
 * Test Mode Handler
 * 
 * Provides endpoints for testing the review flow without a GitHub App installation.
 * Uses Personal Access Token (PAT) for authentication.
 * 
 * Enable by setting TEST_MODE=true in environment.
 */
export default (app: Probot, { getRouter }: ApplicationFunctionOptions) => {
    if (!TEST_MODE) {
        app.log.info("Test mode is disabled. Set TEST_MODE=true to enable.");
        return;
    }

    if (!GITHUB_PAT) {
        app.log.warn("Test mode enabled but GITHUB_PAT not set. Test endpoints will fail.");
    }

    const router = getRouter?.() || getRouter!();
    
    // Add JSON body parser for test routes
    router.use(express.json());

    /**
     * POST /test/review
     * Trigger a review from a PR URL
     * 
     * Body: { pr_url: string, dry_run?: boolean }
     * - pr_url: Full GitHub PR URL (e.g., https://github.com/owner/repo/pull/123)
     * - dry_run: If true, save results to file instead of posting to GitHub
     */
    router.post("/test/review", async (req: Request, res: Response) => {
        try {
            const { pr_url, dry_run = true } = req.body;

            if (!pr_url) {
                return res.status(400).json({ error: "Missing pr_url in request body" });
            }

            if (!GITHUB_PAT) {
                return res.status(500).json({ error: "GITHUB_PAT not configured" });
            }

            // Parse PR URL
            const prInfo = parsePrUrl(pr_url);
            if (!prInfo) {
                return res.status(400).json({ 
                    error: "Invalid PR URL format",
                    expected: "https://github.com/owner/repo/pull/123"
                });
            }

            const { owner, repo, pr_number } = prInfo;
            app.log.info(`[Test Mode] Processing PR: ${owner}/${repo}#${pr_number}`);

            // Create Octokit instance with PAT
            const octokit = new Octokit({ auth: GITHUB_PAT });

            // Get PR details
            const { data: pr } = await octokit.pulls.get({
                owner,
                repo,
                pull_number: pr_number,
            });

            app.log.info(`[Test Mode] PR Title: ${pr.title}`);
            app.log.info(`[Test Mode] Branch: ${pr.head.ref}`);

            // Get changed files
            const { data: files } = await octokit.pulls.listFiles({
                owner,
                repo,
                pull_number: pr_number,
            });

            app.log.info(`[Test Mode] Found ${files.length} changed files`);

            // Filter to reviewable code files
            const reviewableExtensions = [
                '.ts', '.tsx', '.js', '.jsx', '.py', '.java', '.go',
                '.rs', '.rb', '.php', '.cs', '.cpp', '.c', '.h', '.hpp',
                '.swift', '.kt', '.scala', '.vue', '.svelte'
            ];

            const changedFiles = files
                .filter(file => {
                    if (file.status === 'removed') return false;
                    return reviewableExtensions.some(ext =>
                        file.filename.toLowerCase().endsWith(ext)
                    );
                })
                .map(file => file.filename);

            app.log.info(`[Test Mode] ${changedFiles.length} reviewable files after filtering`);

            if (changedFiles.length === 0) {
                return res.status(200).json({
                    success: true,
                    message: "No reviewable code files found in PR",
                    pr_url,
                    files_found: files.length,
                    reviewable_files: 0
                });
            }

            // Call backend to trigger review
            const requestBody = {
                owner,
                repo,
                pr_number,
                branch: pr.head.ref,
                installation_id: 0,  // Not used in test mode
                changed_files: changedFiles,
                test_mode: true,
                dry_run,
            };

            app.log.info(`[Test Mode] Calling backend at ${BACKEND_URL}/bot/review`);

            const response = await axios.post(`${BACKEND_URL}/bot/review`, requestBody, {
                timeout: 300000,  // 5 minute timeout for review
                headers: { 'Content-Type': 'application/json' },
            });

            app.log.info(`[Test Mode] Backend response: ${JSON.stringify(response.data)}`);

            return res.status(200).json({
                success: true,
                message: "Review triggered successfully",
                pr_url,
                owner,
                repo,
                pr_number,
                branch: pr.head.ref,
                files_to_review: changedFiles,
                task_id: response.data.task_id,
                dry_run,
            });

        } catch (err: any) {
            app.log.error("[Test Mode] Error:", err.message);

            if (axios.isAxiosError(err)) {
                return res.status(err.response?.status || 500).json({
                    error: err.message,
                    details: err.response?.data,
                });
            }

            return res.status(500).json({
                error: err.message,
            });
        }
    });

    /**
     * POST /test/trigger-review
     * Post a review to GitHub using PAT authentication
     * Called by backend after review is complete
     * 
     * Body: TestTriggerReviewRequest
     */
    router.post("/test/trigger-review", async (req: Request, res: Response) => {
        try {
            const {
                owner,
                repo,
                pull_number,
                body,
                comments,
                event = "COMMENT",
                dry_run = true,
            } = req.body as TestTriggerReviewRequest;

            // Validate required fields
            if (!owner || !repo || !pull_number) {
                return res.status(400).json({
                    error: "Missing required fields",
                    required: ["owner", "repo", "pull_number"],
                });
            }

            // Must have either body or comments
            if (!body && (!comments || comments.length === 0)) {
                return res.status(400).json({
                    error: "Must provide either 'body' or 'comments' (or both)",
                });
            }

            app.log.info(`[Test Mode] Posting review for ${owner}/${repo}#${pull_number}`);
            app.log.info(`[Test Mode] Summary: ${body ? 'Yes' : 'No'}, Comments: ${comments?.length || 0}, Dry Run: ${dry_run}`);

            // If dry_run, save to file instead of posting
            if (dry_run) {
                const filepath = saveReviewToFile(owner, repo, pull_number, body, comments || []);
                app.log.info(`[Test Mode] Review saved to: ${filepath}`);

                return res.status(200).json({
                    success: true,
                    message: "Review saved to file (dry run mode)",
                    dry_run: true,
                    output_file: filepath,
                    summary_length: body?.length || 0,
                    comments_count: comments?.length || 0,
                });
            }

            // Otherwise, post to GitHub using PAT
            if (!GITHUB_PAT) {
                return res.status(500).json({ error: "GITHUB_PAT not configured" });
            }

            const octokit = new Octokit({ auth: GITHUB_PAT });

            // Get the PR to find the latest commit SHA
            const { data: pr } = await octokit.pulls.get({
                owner,
                repo,
                pull_number,
            });
            const commitId = pr.head.sha;

            // Format comments for GitHub API
            const formattedComments = comments?.map(comment => {
                const formatted: any = {
                    path: comment.path,
                    body: comment.body,
                    line: comment.line,
                };

                if (comment.start_line && comment.start_line < comment.line) {
                    formatted.start_line = comment.start_line;
                    formatted.start_side = comment.start_side || "RIGHT";
                }

                formatted.side = comment.side || "RIGHT";
                return formatted;
            }) || [];

            // Create the review
            const reviewPayload: any = {
                owner,
                repo,
                pull_number,
                commit_id: commitId,
                event: event as "COMMENT" | "APPROVE" | "REQUEST_CHANGES",
            };

            if (body) {
                reviewPayload.body = body;
            }

            if (formattedComments.length > 0) {
                reviewPayload.comments = formattedComments;
            }

            const response = await octokit.pulls.createReview(reviewPayload);

            app.log.info(`[Test Mode] Review posted successfully (ID: ${response.data.id})`);

            return res.status(200).json({
                success: true,
                message: "Review posted to GitHub",
                dry_run: false,
                review_id: response.data.id,
                html_url: response.data.html_url,
                comments_posted: formattedComments.length,
            });

        } catch (err: any) {
            app.log.error("[Test Mode] Error posting review:", err.message);

            if (err.status === 422) {
                app.log.error("[Test Mode] 422 Error - likely invalid line numbers in comments");
            }

            return res.status(err.status || 500).json({
                error: err.message,
                details: err.response?.data,
            });
        }
    });

    /**
     * GET /test/status
     * Check test mode status and configuration
     */
    router.get("/test/status", (_req: Request, res: Response) => {
        res.status(200).json({
            test_mode: TEST_MODE,
            github_pat_configured: !!GITHUB_PAT,
            backend_url: BACKEND_URL,
            output_dir: OUTPUT_DIR,
            endpoints: [
                "POST /test/review - Trigger review from PR URL",
                "POST /test/trigger-review - Post review results",
                "GET /test/status - This endpoint",
            ],
        });
    });

    app.log.info("[Test Mode] Enabled! Endpoints: POST /test/review, POST /test/trigger-review, GET /test/status");
};
