import { Probot } from "probot";

const authorizedOwners = ["jagjeevankashid", "mail-0-team"];

export default (app: Probot) => {
    app.on("pull_request.opened", async (context) => {
        const owner = context.payload.repository.owner.login;

        if (!authorizedOwners.includes(owner)) {
            console.log(`Unauthorized owner: ${owner}`);
            return;
        }

        // await context.octokit.issues.createComment({
        //     ...context.issue(),
        //     body: `Thanks ${owner}, you are verified! Your PR looks good.`,
        // });
    });
};
