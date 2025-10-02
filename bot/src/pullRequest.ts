import { Probot } from "probot";

export default (app: Probot) => {
    // You can trigger this on any event, for example app installation
    app.on("installation.created", async (context) => {
        const owner = context.payload.installation.account.login;
        const repo = "REPO_NAME"; // replace with your repository name

        const baseBranch = "main";          // branch to merge into
        const newBranch = "probot-new-pr";  // branch with changes

        // 1. Create a new branch from the base branch
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

        // 2. Add a new file (or update an existing file)
        const content = Buffer.from("Hello from Probot!").toString("base64");

        await context.octokit.repos.createOrUpdateFileContents({
            owner,
            repo,
            path: "example.txt",
            message: "Add example.txt via Probot",
            content,
            branch: newBranch,
        });

        // 3. Create the pull request
        await context.octokit.pulls.create({
            owner,
            repo,
            title: "Probot: Add example.txt",
            head: newBranch,
            base: baseBranch,
            body: "This PR was automatically created by the Probot app.",
        });
    });
};
