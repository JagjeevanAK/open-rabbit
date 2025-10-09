import { Probot } from "probot";
import axios from "axios";
import { createPullRequestFromBranch, checkBranchExists } from "./utils/pullRequestHelper.js";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8080";

export default (app: Probot) => {
    app.on("issue_comment.created", async (context) => {
        const comment = context.payload.comment.body;
    
        if (comment.startsWith("/create-unit-test")) {
            const owner = context.payload.repository.owner.login;
            const repo = context.payload.repository.name;
            const issueNumber = context.payload.issue.number;
            const installationId = context.payload.installation?.id;

            await context.octokit.issues.createComment({
                ...context.issue(),
                body: "Starting unit test generation...\n\nI'll create tests on a new branch and open a pull request shortly."
            });

            try {
                const response = await axios.post(`${BACKEND_URL}/bot/create-unit-tests`, {
                    owner,
                    repo,
                    issue_number: issueNumber,
                    branch: context.payload.issue.pull_request ? null : "main",
                    installation_id: installationId,
                    comment_id: context.payload.comment.id
                });

                const { task_id, test_branch } = response.data;

                await context.octokit.issues.createComment({
                    ...context.issue(),
                    body: `Unit test generation started!\n\n**Task ID:** \`${task_id}\`\n**Branch:** \`${test_branch}\`\n\nI'll notify you when the tests are ready and create a pull request.`
                });

                pollTaskStatus(context, task_id, owner, repo, issueNumber, test_branch);

            } catch (error) {
                console.error("Error triggering unit test generation:", error);
                await context.octokit.issues.createComment({
                    ...context.issue(),
                    body: `Failed to start unit test generation.\n\n**Error:** ${error instanceof Error ? error.message : 'Unknown error'}`
                });
            }
        }
    });
}

async function pollTaskStatus(
    context: any,
    taskId: string,
    owner: string,
    repo: string,
    issueNumber: number,
    testBranch: string
) {
    const maxAttempts = 60;
    let attempts = 0;

    const interval = setInterval(async () => {
        attempts++;

        try {
            const response = await axios.get(`${BACKEND_URL}/bot/task-status/${taskId}`);
            const { status, result, error } = response.data;

            if (status === "completed") {
                clearInterval(interval);

                const unitTests = result?.unit_tests || {};
                const filesGenerated = unitTests.files_generated || [];
                const testCount = unitTests.test_count || 0;

                await context.octokit.issues.createComment({
                    owner,
                    repo,
                    issue_number: issueNumber,
                    body: `✅ Unit tests generated successfully!\n\n**Tests Created:** ${testCount}\n**Files Generated:**\n${filesGenerated.map((f: string) => `- \`${f}\`\n`).join('')}\n**Branch:** \`${testBranch}\`\n\nCreating pull request now...`
                });

                createPullRequest(context, owner, repo, testBranch, issueNumber, filesGenerated, testCount);

            } else if (status === "failed") {
                clearInterval(interval);

                await context.octokit.issues.createComment({
                    owner,
                    repo,
                    issue_number: issueNumber,
                    body: `❌ Unit test generation failed.\n\n**Error:** ${error || 'Unknown error occurred'}`
                });
            } else if (attempts >= maxAttempts) {
                clearInterval(interval);

                await context.octokit.issues.createComment({
                    owner,
                    repo,
                    issue_number: issueNumber,
                    body: `⏱️ Unit test generation timed out after ${maxAttempts * 5} seconds.\n\nPlease check the task status manually: \`${taskId}\``
                });
            }
        } catch (error) {
            console.error("Error polling task status:", error);
        }
    }, 5000);
}

async function createPullRequest(
    context: any,
    owner: string,
    repo: string,
    testBranch: string,
    issueNumber: number,
    filesGenerated: string[],
    testCount: number
) {
    try {
        const baseBranch = "main";

        const branchExists = await checkBranchExists(context, owner, repo, testBranch);
        
        if (!branchExists) {
            await context.octokit.issues.createComment({
                owner,
                repo,
                issue_number: issueNumber,
                body: `⚠️ Branch \`${testBranch}\` does not exist yet.\n\nThe backend agent should have created and pushed this branch. Please check the backend logs or wait for the push to complete.`
            });
            return;
        }

        const prTitle = `🧪 Add Unit Tests (Issue #${issueNumber})`;
        const prBody = `## Unit Tests Generated by Open Rabbit\n\nThis PR adds comprehensive unit tests generated automatically.\n\n### 📊 Summary\n- **Tests Created:** ${testCount}\n- **Files Generated:** ${filesGenerated.length}\n\n### 📁 Files\n${filesGenerated.map(f => `- \`${f}\``).join('\n')}\n\n### 🔗 Related\nCloses #${issueNumber}\n\n---\n*Generated automatically by [Open Rabbit](https://github.com/open-rabbit)*`;

        const result = await createPullRequestFromBranch(context, {
            owner,
            repo,
            baseBranch,
            headBranch: testBranch,
            title: prTitle,
            body: prBody,
        });

        if (result.success && result.pr) {
            await context.octokit.issues.createComment({
                owner,
                repo,
                issue_number: issueNumber,
                body: `🎉 Pull request created!\n\n**PR #${result.pr.number}:** ${result.pr.html_url}\n\nPlease review the generated tests and merge when ready.`
            });
        } else {
            await context.octokit.issues.createComment({
                owner,
                repo,
                issue_number: issueNumber,
                body: `⚠️ Tests generated successfully but failed to create pull request.\n\n**Branch:** \`${testBranch}\`\n**Error:** ${result.error}\n\nPlease create the PR manually from this branch.`
            });
        }

    } catch (error) {
        console.error("Error creating pull request:", error);
        await context.octokit.issues.createComment({
            owner,
            repo,
            issue_number: issueNumber,
            body: `⚠️ Tests generated successfully but failed to create pull request.\n\n**Branch:** \`${testBranch}\`\n**Error:** ${error instanceof Error ? error.message : 'Unknown error'}\n\nPlease create the PR manually from this branch.`
        });
    }
}
