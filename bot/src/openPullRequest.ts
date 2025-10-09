import { Probot } from "probot";
import { createBranchFromBase, createOrUpdateFile, createPullRequestFromBranch } from "./utils/pullRequestHelper.js";

export default (app: Probot) => {
    app.on("installation.created", async (context) => {
        const owner = context.payload.installation.account.login;
        const repo = "REPO_NAME"; 

        const baseBranch = "main";          
        const newBranch = "probot-new-pr";  

        const branchResult = await createBranchFromBase(context, owner, repo, baseBranch, newBranch);
        
        if (!branchResult.success) {
            console.error(`Failed to create branch: ${branchResult.error}`);
            return;
        }

        const fileResult = await createOrUpdateFile(
            context,
            owner,
            repo,
            "example.txt",
            "Hello from Probot!",
            "Add example.txt via Probot",
            newBranch
        );

        if (!fileResult.success) {
            console.error(`Failed to create file: ${fileResult.error}`);
            return;
        }

        const prResult = await createPullRequestFromBranch(context, {
            owner,
            repo,
            baseBranch,
            headBranch: newBranch,
            title: "Probot: Add example.txt",
            body: "This PR was automatically created by the Probot app.",
        });

        if (prResult.success) {
            console.log(`PR created successfully: ${prResult.pr?.html_url}`);
        } else {
            console.error(`Failed to create PR: ${prResult.error}`);
        }
    });
};
