import { Context } from "probot";

export interface PullRequestOptions {
    owner: string;
    repo: string;
    baseBranch: string;
    headBranch: string;
    title: string;
    body: string;
}

export async function createPullRequestFromBranch(
    context: Context,
    options: PullRequestOptions
): Promise<{ success: boolean; pr?: any; error?: string }> {
    try {
        const { owner, repo, baseBranch, headBranch, title, body } = options;

        const { data: pr } = await context.octokit.pulls.create({
            owner,
            repo,
            title,
            head: headBranch,
            base: baseBranch,
            body,
        });

        return { success: true, pr };
    } catch (error) {
        console.error("Error creating pull request:", error);
        return {
            success: false,
            error: error instanceof Error ? error.message : "Unknown error",
        };
    }
}

export async function createBranchFromBase(
    context: Context,
    owner: string,
    repo: string,
    baseBranch: string,
    newBranch: string
): Promise<{ success: boolean; error?: string }> {
    try {
        const { data: refData } = await context.octokit.git.getRef({
            owner,
            repo,
            ref: `heads/${baseBranch}`,
        });

        await context.octokit.git.createRef({
            owner,
            repo,
            ref: `refs/heads/${newBranch}`,
            sha: refData.object.sha,
        });

        return { success: true };
    } catch (error) {
        console.error("Error creating branch:", error);
        return {
            success: false,
            error: error instanceof Error ? error.message : "Unknown error",
        };
    }
}

export async function checkBranchExists(
    context: Context,
    owner: string,
    repo: string,
    branch: string
): Promise<boolean> {
    try {
        await context.octokit.git.getRef({
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

export async function createOrUpdateFile(
    context: Context,
    owner: string,
    repo: string,
    path: string,
    content: string,
    message: string,
    branch: string
): Promise<{ success: boolean; error?: string }> {
    try {
        const encodedContent = Buffer.from(content).toString("base64");

        await context.octokit.repos.createOrUpdateFileContents({
            owner,
            repo,
            path,
            message,
            content: encodedContent,
            branch,
        });

        return { success: true };
    } catch (error) {
        console.error("Error creating/updating file:", error);
        return {
            success: false,
            error: error instanceof Error ? error.message : "Unknown error",
        };
    }
}
