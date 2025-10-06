import { Probot } from "probot";
import manualTrigger from "./manualTrigger.js";

export default (app: Probot, options: any) => {
  // Load manual trigger routes for external API access
  manualTrigger(app, options);

  app.on("pull_request.opened", async (context) => {
    const issueComment = context.issue({
      body: "Thanks for opening this PR! A bot will review your code shortly!",
    });
    await context.octokit.issues.createComment(issueComment);
  });

  app.on("pull_request.synchronize", async (context) => {
    const prComment = context.issue({
      body: " New commits detected! The bot will re-check your changes.",
    });

    await context.octokit.issues.createComment(prComment);
  });

  // For more information on building apps:
  // https://probot.github.io/docs/

  // To get your app running against GitHub, see:
  // https://probot.github.io/docs/development/
};
