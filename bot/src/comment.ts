import express, { Request, Response } from "express";
import { Probot, ApplicationFunctionOptions } from "probot";
import {
    InlineComment,
    ReviewPayload,
    buildReviewForGitHub,
    calculateStats,
} from "./utils/commentBuilder.js";
import {
    createMultiFileCommit,
    FileToCommit,
} from "./utils/githubCommit.js";

/**
 * Review comment structure for inline PR comments (legacy format)
 */
interface ReviewComment {
    path: string;           // File path
    line: number;           // Line number (required)
    body: string;           // Comment body (markdown)
    start_line?: number;    // For multi-line comments
    side?: "LEFT" | "RIGHT"; // LEFT = old code, RIGHT = new code
    start_side?: "LEFT" | "RIGHT";
}

/**
 * Request body for /trigger-review endpoint (legacy format)
 */
interface TriggerReviewRequest {
    owner: string;
    repo: string;
    pull_number: number;
    installation_id: number;
    body?: string;              // Summary comment (optional)
    comments?: ReviewComment[]; // Inline comments (optional)
    event?: "COMMENT" | "APPROVE" | "REQUEST_CHANGES";
}

/**
 * Request body for /trigger-structured-review endpoint (new format)
 * Uses structured ReviewIssue types for professional formatting
 */
interface StructuredReviewRequest {
    owner: string;
    repo: string;
    pull_number: number;
    installation_id: number;
    summary: string;                    // Review summary text
    comments: InlineComment[];          // Structured inline comments
    event?: "COMMENT" | "APPROVE" | "REQUEST_CHANGES";
    auto_calculate_stats?: boolean;     // Auto-calculate stats from comments
}

/**
 * Request body for /commit-files endpoint
 * Used by backend to commit generated files (tests, etc.) to a branch
 */
interface CommitFilesRequest {
    owner: string;
    repo: string;
    branch: string;
    installation_id: number;
    files: FileToCommit[];              // Files to commit (path + content)
    message: string;                    // Commit message
}

export default (app: Probot, { getRouter }: ApplicationFunctionOptions) => {
    const router = getRouter?.() || getRouter!();
    
    // Add JSON body parser middleware
    router.use(express.json());

    /**
     * POST /trigger-comment
     * Legacy endpoint - posts a single comment to a PR
     */
    router.post("/trigger-comment", async (req: Request, res: Response) => {
        try {
            const { owner, repo, pull_number, body, installation_id } = req.body;
        
            if (!owner || !repo || !pull_number || !body || !installation_id) {
                return res.status(400).json({ 
                    error: "Missing required fields",
                    required: ["owner", "repo", "pull_number", "body", "installation_id"]
                });
            }

            app.log.info(`Manual trigger: ${owner}/${repo}#${pull_number}`);

            // Authenticate using the installation ID
            const octokit = await app.auth(Number(installation_id));
            
            // Post the comment as a PR review
            await octokit.rest.pulls.createReview({
                owner,
                repo,
                pull_number: Number(pull_number),
                event: "COMMENT",
                body,
            });

            app.log.info(`Comment posted successfully to ${owner}/${repo}#${pull_number}`);
            
            return res.status(200).json({ 
                success: true,
                message: "Comment posted successfully" 
            });
        } catch (err: any) {
            app.log.error("Error posting comment:", err);
            return res.status(500).json({ 
                error: err.message,
                details: err.response?.data || "Internal server error"
            });
        }
    });

    /**
     * POST /trigger-review
     * New endpoint - posts a full PR review with summary and inline comments
     * 
     * This endpoint supports:
     * - Summary body comment
     * - Inline comments on specific lines
     * - Multi-line comments (start_line + line)
     * - Different review events (COMMENT, APPROVE, REQUEST_CHANGES)
     */
    router.post("/trigger-review", async (req: Request, res: Response) => {
        try {
            const { 
                owner, 
                repo, 
                pull_number, 
                installation_id,
                body,
                comments,
                event = "COMMENT"
            } = req.body as TriggerReviewRequest;
        
            // Validate required fields
            if (!owner || !repo || !pull_number || !installation_id) {
                return res.status(400).json({ 
                    error: "Missing required fields",
                    required: ["owner", "repo", "pull_number", "installation_id"],
                    optional: ["body", "comments", "event"]
                });
            }

            // Must have either body or comments
            if (!body && (!comments || comments.length === 0)) {
                return res.status(400).json({ 
                    error: "Must provide either 'body' or 'comments' (or both)",
                });
            }

            app.log.info(`Creating review for ${owner}/${repo}#${pull_number} with ${comments?.length || 0} inline comments`);

            // Authenticate using the installation ID
            const octokit = await app.auth(Number(installation_id));

            // Get the PR to find the latest commit SHA (required for review comments)
            const pr = await octokit.rest.pulls.get({
                owner,
                repo,
                pull_number: Number(pull_number),
            });
            const commitId = pr.data.head.sha;

            // Format comments for GitHub API
            // GitHub requires 'position' for diff-based comments or 'line' for file-based
            const formattedComments = comments?.map(comment => {
                const formatted: any = {
                    path: comment.path,
                    body: comment.body,
                    line: comment.line,
                };
                
                // Add multi-line support
                if (comment.start_line && comment.start_line < comment.line) {
                    formatted.start_line = comment.start_line;
                    formatted.start_side = comment.start_side || "RIGHT";
                }
                
                // Default to RIGHT side (new code)
                formatted.side = comment.side || "RIGHT";
                
                return formatted;
            }) || [];

            // Create the review
            const reviewPayload: any = {
                owner,
                repo,
                pull_number: Number(pull_number),
                commit_id: commitId,
                event: event as "COMMENT" | "APPROVE" | "REQUEST_CHANGES",
            };

            // Add body if provided
            if (body) {
                reviewPayload.body = body;
            }

            // Add comments if provided
            if (formattedComments.length > 0) {
                reviewPayload.comments = formattedComments;
            }

            app.log.info(`Review payload: ${JSON.stringify({
                ...reviewPayload,
                body: body ? `${body.substring(0, 100)}...` : undefined,
                comments: `${formattedComments.length} comments`
            })}`);

            const response = await octokit.rest.pulls.createReview(reviewPayload);

            app.log.info(`Review created successfully for ${owner}/${repo}#${pull_number} (review ID: ${response.data.id})`);
            
            return res.status(200).json({ 
                success: true,
                message: "Review created successfully",
                review_id: response.data.id,
                comments_posted: formattedComments.length,
                html_url: response.data.html_url
            });
        } catch (err: any) {
            app.log.error("Error creating review:", err);
            
            // Provide more detailed error info
            const errorDetails = {
                message: err.message,
                status: err.status,
                response: err.response?.data,
            };
            
            // Common error: comment position is invalid
            if (err.status === 422) {
                app.log.error("422 Error - likely invalid line numbers. Check that lines exist in the PR diff.");
            }
            
            return res.status(err.status || 500).json({ 
                error: err.message,
                details: errorDetails,
            });
        }
    });

    /**
     * GET /health
     * Health check endpoint
     */
    router.get("/health", (_req: Request, res: Response) => {
        res.status(200).json({ 
            status: "ok", 
            service: "open-rabbit-bot",
            endpoints: [
                "POST /trigger-comment",
                "POST /trigger-review",
                "POST /trigger-structured-review",
                "POST /commit-files",
                "GET /health"
            ],
            timestamp: new Date().toISOString()
        });
    });

    /**
     * POST /commit-files
     * Commit multiple files atomically to a branch
     * 
     * This endpoint is used by the backend to commit generated files
     * (like unit tests) directly to a PR branch.
     * 
     * Uses GitHub's Git Data API for atomic multi-file commits:
     * - All files are committed in a single operation
     * - If any file fails, the entire commit is rolled back
     * - Only one commit appears in history
     */
    router.post("/commit-files", async (req: Request, res: Response) => {
        try {
            const {
                owner,
                repo,
                branch,
                installation_id,
                files,
                message,
            } = req.body as CommitFilesRequest;

            // Validate required fields
            if (!owner || !repo || !branch || !installation_id || !files || !message) {
                return res.status(400).json({
                    error: "Missing required fields",
                    required: ["owner", "repo", "branch", "installation_id", "files", "message"],
                });
            }

            if (!Array.isArray(files) || files.length === 0) {
                return res.status(400).json({
                    error: "Files must be a non-empty array",
                });
            }

            // Validate file structure
            for (const file of files) {
                if (!file.path || typeof file.content !== "string") {
                    return res.status(400).json({
                        error: "Each file must have 'path' (string) and 'content' (string)",
                        invalidFile: file,
                    });
                }
            }

            app.log.info(`Committing ${files.length} files to ${owner}/${repo}@${branch}`);

            // Authenticate using the installation ID
            const octokit = await app.auth(Number(installation_id));

            // Create the atomic multi-file commit
            const result = await createMultiFileCommit(octokit, {
                owner,
                repo,
                branch,
                files,
                message,
            });

            if (result.success) {
                app.log.info(`Files committed successfully: ${result.sha}`);
                
                return res.status(200).json({
                    success: true,
                    sha: result.sha,
                    commitUrl: result.commitUrl,
                    filesCommitted: files.length,
                    message: `Successfully committed ${files.length} file(s)`,
                });
            } else {
                app.log.error(`Failed to commit files: ${result.error}`);
                
                return res.status(500).json({
                    success: false,
                    error: result.error,
                });
            }
        } catch (err: any) {
            app.log.error("Error committing files:", err);
            
            return res.status(err.status || 500).json({
                success: false,
                error: err.message,
                details: err.response?.data || "Internal server error",
            });
        }
    });

    /**
     * POST /trigger-structured-review
     * Professional code review endpoint with structured issue types
     * 
     * This endpoint supports:
     * - 5 severity levels: critical, warning, suggestion, nitpick, praise
     * - Collapsible sections for details, learnings, AI prompts
     * - GitHub suggestion blocks for auto-applicable fixes
     * - Diff preview blocks
     * - Multi-line comments
     * - Auto-calculated statistics
     * 
     * Invalid comments are logged and skipped (not failing the request)
     */
    router.post("/trigger-structured-review", async (req: Request, res: Response) => {
        try {
            const { 
                owner, 
                repo, 
                pull_number, 
                installation_id,
                summary,
                comments,
                event = "COMMENT",
                auto_calculate_stats = true,
            } = req.body as StructuredReviewRequest;
        
            // Validate required fields
            if (!owner || !repo || !pull_number || !installation_id) {
                return res.status(400).json({ 
                    error: "Missing required fields",
                    required: ["owner", "repo", "pull_number", "installation_id", "summary"],
                    optional: ["comments", "event", "auto_calculate_stats"]
                });
            }

            if (!summary) {
                return res.status(400).json({ 
                    error: "Missing required field: summary",
                });
            }

            app.log.info(`Creating structured review for ${owner}/${repo}#${pull_number} with ${comments?.length || 0} inline comments`);

            // Build the review payload
            const reviewPayload: ReviewPayload = {
                summary,
                comments: comments || [],
                event: event as "COMMENT" | "APPROVE" | "REQUEST_CHANGES",
                stats: auto_calculate_stats && comments?.length > 0 
                    ? calculateStats(comments) 
                    : undefined,
            };

            // Format for GitHub API using our builder
            const logger = (msg: string) => app.log.warn(msg);
            const formattedReview = buildReviewForGitHub(reviewPayload, logger);

            // Log skipped comments (but don't fail)
            if (formattedReview.skipped.length > 0) {
                app.log.warn(`Skipped ${formattedReview.skipped.length} invalid comments:`);
                formattedReview.skipped.forEach(({ comment, reason }) => {
                    app.log.warn(`  - ${comment.path}:${comment.line} - ${reason}`);
                });
            }

            // Authenticate using the installation ID
            const octokit = await app.auth(Number(installation_id));

            // Get the PR to find the latest commit SHA (required for review comments)
            const pr = await octokit.rest.pulls.get({
                owner,
                repo,
                pull_number: Number(pull_number),
            });
            const commitId = pr.data.head.sha;

            // Create the review
            const githubPayload: any = {
                owner,
                repo,
                pull_number: Number(pull_number),
                commit_id: commitId,
                event: formattedReview.event,
                body: formattedReview.body,
            };

            // Add comments if any valid ones exist
            if (formattedReview.comments.length > 0) {
                githubPayload.comments = formattedReview.comments;
            }

            app.log.info(`Structured review payload: ${JSON.stringify({
                owner,
                repo,
                pull_number,
                event: formattedReview.event,
                body_length: formattedReview.body.length,
                valid_comments: formattedReview.comments.length,
                skipped_comments: formattedReview.skipped.length,
            })}`);

            const response = await octokit.rest.pulls.createReview(githubPayload);

            app.log.info(`Structured review created successfully for ${owner}/${repo}#${pull_number} (review ID: ${response.data.id})`);
            
            return res.status(200).json({ 
                success: true,
                message: "Structured review created successfully",
                review_id: response.data.id,
                comments_posted: formattedReview.comments.length,
                comments_skipped: formattedReview.skipped.length,
                skipped_details: formattedReview.skipped.map(s => ({
                    path: s.comment.path,
                    line: s.comment.line,
                    reason: s.reason,
                })),
                html_url: response.data.html_url,
                stats: reviewPayload.stats,
            });
        } catch (err: any) {
            app.log.error("Error creating structured review:", err);
            
            // Provide more detailed error info
            const errorDetails = {
                message: err.message,
                status: err.status,
                response: err.response?.data,
            };
            
            // Common error: comment position is invalid
            if (err.status === 422) {
                app.log.error("422 Error - likely invalid line numbers. Check that lines exist in the PR diff.");
            }
            
            return res.status(err.status || 500).json({ 
                error: err.message,
                details: errorDetails,
            });
        }
    });

    app.log.info("Manual trigger endpoints registered: POST /trigger-comment, POST /trigger-review, POST /trigger-structured-review, POST /commit-files, GET /health");
};
