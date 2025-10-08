import { Probot } from "probot";

export default (app: Probot) => {
    app.on("installation.created", async (context) => {
        const owner = context.payload.installation.account.login;
        const repo = "REPO_NAME"; 

        const baseBranch = "main";          
        const newBranch = "probot-new-pr";  

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

        const content = Buffer.from("Hello from Probot!").toString("base64");

        await context.octokit.repos.createOrUpdateFileContents({
            owner,
            repo,
            path: "example.txt",
            message: "Add example.txt via Probot",
            content,
            branch: newBranch,
        });

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
