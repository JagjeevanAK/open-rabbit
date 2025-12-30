import { Probot } from "probot";
import axios from "axios";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8080";

/**
 * Manual Review Handler
 * 
 * Triggered when a user comments `/review` on a pull request.
 * This allows users to manually request a code review at any time.
 */
export default (app: Probot) => {
    app.on("issue_comment.created", async (context) => {
        const comment = context.payload.comment.body.trim();
        
        // Only respond to /review command
        if (!comment.startsWith("/review")) {
            return;
        }

        // Must be on a pull request, not a regular issue
        if (!context.payload.issue.pull_request) {
            await context.octokit.issues.createComment({
                ...context.issue(),
                body: "The `/review` command can only be used on pull requests."
            });
            return;
        }

        const owner = context.payload.repository.owner.login;
        const repo = context.payload.repository.name;
        const prNumber = context.payload.issue.number;
        const installationId = context.payload.installation?.id;

        if (!installationId) {
            app.log.error(`No installation ID found for manual review on ${owner}/${repo}#${prNumber}`);
            return;
        }

        app.log.info(`Manual review requested for ${owner}/${repo}#${prNumber}`);

        // Post acknowledgment
        await context.octokit.issues.createComment({
            ...context.issue(),
            body: "🔍 Starting code review...\n\nI'll analyze your changes and post my findings shortly."
        });

        try {
            // Get PR details to find the branch
            const { data: pr } = await context.octokit.pulls.get({
                owner,
                repo,
                pull_number: prNumber,
            });

            // Get changed files
            const { data: files } = await context.octokit.pulls.listFiles({
                owner,
                repo,
                pull_number: prNumber,
            });

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

            if (changedFiles.length === 0) {
                await context.octokit.issues.createComment({
                    ...context.issue(),
                    body: "No reviewable code files found in this PR. I can review files with these extensions: " + 
                          reviewableExtensions.join(', ')
                });
                return;
            }

            // Call backend to trigger review
            const response = await axios.post(`${BACKEND_URL}/bot/review`, {
                owner,
                repo,
                pr_number: prNumber,
                branch: pr.head.ref,
                installation_id: installationId,
                changed_files: changedFiles,
            }, {
                timeout: 30000,
                headers: { 'Content-Type': 'application/json' },
            });

            const { task_id } = response.data;

            app.log.info(`Manual review task created: ${task_id} for ${owner}/${repo}#${prNumber}`);

            // Note: The backend will post the review directly via /trigger-review
            // We don't need to poll for status - the review will appear automatically

        } catch (error: any) {
            app.log.error(`Error triggering manual review: ${error.message}`);
            
            let errorMessage = "An unexpected error occurred.";
            if (axios.isAxiosError(error)) {
                errorMessage = error.response?.data?.detail || error.message;
            }

            await context.octokit.issues.createComment({
                ...context.issue(),
                body: `❌ Failed to start code review.\n\n**Error:** ${errorMessage}\n\nPlease try again or check the bot logs.`
            });
        }
    });
};
