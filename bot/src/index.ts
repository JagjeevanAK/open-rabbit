import './observability/telemetry.js';
import { setupTelemetry } from './observability/telemetry.js';

setupTelemetry();

import { Probot } from "probot";
import manualTrigger from "./comment.js";
import newInstallation from "./newInstallation.js";
import unitTest from "./unitTest.js";
import unitTestMention from "./unitTestMention.js";
import feedbackHandler from "./feedbackHandler.js";
import autoReview from "./autoReview.js";
import manualReview from "./manualReview.js";
import testMode from "./testMode.js";

export default (app: Probot, options: any) => {
  // Load manual trigger routes (HTTP endpoints for backend to post reviews)
  manualTrigger(app, options);

  // Load new installation handler
  newInstallation(app);

  // Load unit test generation handler (/create-unit-test command)
  unitTest(app);

  // Load @openrabbit unit-test mention handler (commits tests to PR branch)
  unitTestMention(app);

  // Load feedback handler for KB learning loop
  feedbackHandler(app);

  // Load auto review handler (triggers on PR open/sync)
  autoReview(app);

  // Load manual review handler (/review command)
  manualReview(app);

  // Load test mode handler (for testing without GitHub App installation)
  // Enable with TEST_MODE=true and GITHUB_PAT env vars
  testMode(app, options);

  app.log.info("Open Rabbit bot initialized with handlers: autoReview, manualReview, unitTest, unitTestMention, feedbackHandler, testMode");
};
