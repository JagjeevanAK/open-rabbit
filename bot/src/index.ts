import './observability/telemetry.js';
import { setupTelemetry } from './observability/telemetry.js';

setupTelemetry();

import { Probot } from "probot";
import manualTrigger from "./comment.js";
import enhancedPullRequest from "./enhancedPullRequest.js";
import newInstallation from "./newInstallation.js";
import unitTest from "./unitTest.js";

export default (app: Probot, options: any) => {
  // Load manual trigger routes for external API access
  manualTrigger(app, options);

  // Load enhanced PR handler with knowledge base integration
  enhancedPullRequest(app);

  // Load new installation handler
  newInstallation(app);

  // Load unit test generation handler
  unitTest(app);

  // For more information on building apps:
  // https://probot.github.io/docs/

  // To get your app running against GitHub, see:
  // https://probot.github.io/docs/development/
};
