import { Request, Response } from "express";
import { Probot, ApplicationFunctionOptions } from "probot";

export default (app: Probot, { getRouter }: ApplicationFunctionOptions) => {
    const router = getRouter?.() || getRouter!();

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

    router.get("/health", (_req: Request, res: Response) => {
        res.status(200).json({ 
            status: "ok", 
            service: "probot-manual-trigger",
            timestamp: new Date().toISOString()
        });
    });

    app.log.info("Manual trigger endpoints registered: POST /trigger-comment, GET /health");
};
