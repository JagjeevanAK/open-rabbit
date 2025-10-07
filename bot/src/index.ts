import { Probot } from "probot";
import manualTrigger from "./manualComment.js";
import enhancedPullRequest from "./enhancedPullRequest.js";

export default (app: Probot, options: any) => {
  // Load manual trigger routes for external API access
  manualTrigger(app, options);

  // Load enhanced PR handler with knowledge base integration
  enhancedPullRequest(app);

  // For more information on building apps:
  // https://probot.github.io/docs/

  // To get your app running against GitHub, see:
  // https://probot.github.io/docs/development/
};
