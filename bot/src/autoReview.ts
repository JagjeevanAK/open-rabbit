import axios from "axios";
import { Probot, Context } from "probot";
import { isAuthorized, postUnauthorizedComment } from "./auth.js";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8080";

/**
 * Auto Review Handler
 * 
 * Automatically triggered when a PR is opened or synchronized (new commits pushed).
 * Reviews only changed code files and posts feedback via inline comments.
 * 
 * For manual reviews triggered by `/review` command, see manualReview.ts
 */

interface ReviewRequestBody {
    owner: string;
    repo: string;
    pr_number: number;
    branch: string;
    base_branch: string;
    installation_id: number;
    changed_files: string[];
}

export default (app: Probot) => {
    app.on(["pull_request.opened", "pull_request.synchronize"], async (context: Context<"pull_request">) => {
        const pr = context.payload.pull_request;
        const { owner, repo } = context.repo();
        const installationId = context.payload.installation?.id;

        if (!installationId) {
            app.log.error(`No installation ID found for PR ${owner}/${repo}#${pr.number}`);
            return;
        }

        // Check authorization if AUTH_ENABLED=true
        const prOwner = context.payload.repository.owner.login;
        if (!await isAuthorized(prOwner, app)) {
            await postUnauthorizedComment(context, prOwner);
            return;
        }

        app.log.info(`Processing PR ${owner}/${repo}#${pr.number} (installation: ${installationId})`);

        try {
            // Get list of changed files
            const { data: files } = await context.octokit.pulls.listFiles({
                owner,
                repo,
                pull_number: pr.number,
            });

            app.log.info(`Found ${files.length} changed files in PR #${pr.number}`);

            // Filter to only reviewable code files (skip deleted, binary, etc.)
            const reviewableExtensions = [
                '.ts', '.tsx', '.js', '.jsx', '.py', '.java', '.go',
                '.rs', '.rb', '.php', '.cs', '.cpp', '.c', '.h', '.hpp',
                '.swift', '.kt', '.scala', '.vue', '.svelte'
            ];

            const changedFiles = files
                .filter(file => {
                    // Skip deleted files
                    if (file.status === 'removed') return false;

                    // Only review code files
                    return reviewableExtensions.some(ext =>
                        file.filename.toLowerCase().endsWith(ext)
                    );
                })
                .map(file => file.filename);

            app.log.info(`${changedFiles.length} reviewable files after filtering`);

            if (changedFiles.length === 0) {
                app.log.info(`No reviewable files in PR #${pr.number}, skipping review`);
                return;
            }

            // Send to backend for review (backend will clone repo and read files)
            const requestBody: ReviewRequestBody = {
                owner,
                repo,
                pr_number: pr.number,
                branch: pr.head.ref,
                base_branch: pr.base.ref,  // Pass base branch for diff comparison
                installation_id: installationId,
                changed_files: changedFiles,
            };

            const backendUrl = `${BACKEND_URL}/bot/review`;
            app.log.info(`Sending review request to ${backendUrl} for ${changedFiles.length} files`);

            const response = await axios.post(backendUrl, requestBody, {
                timeout: 30000,
                headers: { 'Content-Type': 'application/json' },
            });

            app.log.info(`Review task created: ${JSON.stringify(response.data)}`);

        } catch (err: any) {
            app.log.error(`Error processing PR ${owner}/${repo}#${pr.number}: ${err.message}`);

            if (axios.isAxiosError(err)) {
                app.log.error(`Backend error: ${JSON.stringify(err.response?.data || 'No response')}`);
            }
        }
    });
};
