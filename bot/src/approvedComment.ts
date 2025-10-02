import { Probot } from "probot";

export default (app: Probot) => {
    app.on("pull_request.opened", async (context) => {
        await context.octokit.pulls.createReview({
            ...context.pullRequest(),
            event: "APPROVE", 
            body: "Thanks for the contribution! It looks good."
        });
    });
};
