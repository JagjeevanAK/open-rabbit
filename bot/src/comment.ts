import { Request, Response } from "express";
import { Probot, ApplicationFunctionOptions } from "probot";

/**
 * Review comment structure for inline PR comments
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
 * Request body for /trigger-review endpoint
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

export default (app: Probot, { getRouter }: ApplicationFunctionOptions) => {
    const router = getRouter?.() || getRouter!();

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
                "GET /health"
            ],
            timestamp: new Date().toISOString()
        });
    });

    app.log.info("Manual trigger endpoints registered: POST /trigger-comment, POST /trigger-review, GET /health");
};
