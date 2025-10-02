import { Probot } from "probot";

export default (app: Probot) => {
    app.on("issue_comment.created", async (context) => {
        const comment = context.payload.comment.body;
    
        if (comment.startsWith("/create-unit-test")) {
            await context.octokit.issues.createComment({
                ...context.issue(),
                body: "Creating Unit Test's in upcomming pull request"
            });
    
            // Your custom task logic here
        }
    });
}

