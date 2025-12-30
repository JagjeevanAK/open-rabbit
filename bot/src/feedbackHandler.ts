/**
 * Feedback Handler
 * 
 * Handles user feedback on AI review comments:
 * - Reactions (thumbs up/down, etc.)
 * - Replies to bot comments
 * - Commands like @open-rabbit learn
 * 
 * Sends feedback to backend API for processing through FeedbackProcessor agent.
 */

import { Probot, Context } from "probot";
import axios from "axios";

// Backend API URL
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8080";

// Check if KB/feedback loop is enabled
const KB_ENABLED = process.env.KB_ENABLED === 'true';

// Reaction type mapping to match backend schema
export const REACTION_MAP: { [key: string]: string } = {
  "+1": "thumbs_up",
  "-1": "thumbs_down",
  "laugh": "laugh",
  "confused": "confused",
  "heart": "heart",
  "hooray": "hooray",
  "rocket": "rocket",
  "eyes": "eyes",
};

// Track bot comments for feedback attribution
interface BotComment {
  commentId: string;
  reviewSessionId?: string;
  owner: string;
  repo: string;
  prNumber: number;
  filePath?: string;
  lineNumber?: number;
  aiComment: string;
  timestamp: Date;
}

// In-memory store for bot comments (could be Redis in production)
const botCommentStore = new Map<string, BotComment>();

/**
 * Generate a unique key for tracking bot comments
 */
function getCommentKey(owner: string, repo: string, commentId: string | number): string {
  return `${owner}/${repo}:${commentId}`;
}

/**
 * Store a bot comment for feedback tracking
 */
export function trackBotComment(data: Omit<BotComment, 'timestamp'>): void {
  const key = getCommentKey(data.owner, data.repo, data.commentId);
  botCommentStore.set(key, {
    ...data,
    timestamp: new Date(),
  });
  console.log(`[FeedbackHandler] Tracking bot comment: ${key}`);
}

/**
 * Send feedback to backend API
 */
async function sendFeedbackToBackend(feedback: {
  comment_id: string;
  review_session_id?: string;
  owner: string;
  repo: string;
  pr_number: number;
  file_path?: string;
  line_number?: number;
  ai_comment: string;
  feedback_type: "reaction" | "reply" | "command";
  reaction_type?: string;
  user_feedback?: string;
  github_user: string;
}): Promise<boolean> {
  // Skip if KB is not enabled
  if (!KB_ENABLED) {
    console.log("[FeedbackHandler] KB not enabled, skipping feedback submission");
    return false;
  }
  
  try {
    const response = await axios.post(`${BACKEND_URL}/user-feedback/submit`, feedback, {
      headers: { "Content-Type": "application/json" },
      timeout: 10000,
    });
    
    console.log(`[FeedbackHandler] Feedback submitted: ${response.data?.id || 'success'}`);
    return true;
  } catch (error: any) {
    console.error("[FeedbackHandler] Failed to submit feedback:", error.message);
    if (error.response) {
      console.error("[FeedbackHandler] Response:", error.response.status, error.response.data);
    }
    return false;
  }
}

/**
 * Check if a comment is from our bot
 */
function isBotComment(authorLogin: string): boolean {
  const botNames = [
    "open-rabbit[bot]",
    "open-rabbit",
    "openrabbit[bot]",
    // Add your GitHub App name here
    process.env.BOT_NAME || "open-rabbit",
  ];
  return botNames.some(name => 
    authorLogin.toLowerCase().includes(name.toLowerCase())
  );
}

/**
 * Extract commands from comment body
 */
function extractCommands(body: string): string[] {
  const commandPattern = /@open-rabbit\s+(learn|ignore|explain|undo)/gi;
  const matches = body.match(commandPattern) || [];
  return matches.map(m => m.toLowerCase().replace("@open-rabbit", "").trim());
}

export default (app: Probot) => {
  
  /**
   * Handle reactions on PR review comments
   */
  app.on("pull_request_review_comment.created", async (context) => {
    try {
      const comment = context.payload.comment;
      const pr = context.payload.pull_request;
      const owner = context.payload.repository.owner.login;
      const repo = context.payload.repository.name;
      
      // Check if this is a reply to a bot comment
      if (comment.in_reply_to_id) {
        const parentKey = getCommentKey(owner, repo, comment.in_reply_to_id);
        const botComment = botCommentStore.get(parentKey);
        
        if (botComment || await checkIfBotComment(context, comment.in_reply_to_id)) {
          // This is a reply to our bot's comment
          const commands = extractCommands(comment.body);
          const feedbackType = commands.length > 0 ? "command" : "reply";
          
          await sendFeedbackToBackend({
            comment_id: String(comment.in_reply_to_id),
            review_session_id: botComment?.reviewSessionId,
            owner,
            repo,
            pr_number: pr.number,
            file_path: comment.path,
            line_number: comment.line || comment.original_line,
            ai_comment: botComment?.aiComment || "Unknown bot comment",
            feedback_type: feedbackType,
            user_feedback: comment.body,
            github_user: comment.user.login,
          });
          
          console.log(`[FeedbackHandler] Processed reply to bot comment from ${comment.user.login}`);
        }
      }
    } catch (error) {
      console.error("[FeedbackHandler] Error processing review comment:", error);
    }
  });
  
  /**
   * Handle reactions on issue comments (PR comments that aren't on specific lines)
   */
  app.on("issue_comment.created", async (context) => {
    try {
      // Only process PR comments
      if (!context.payload.issue.pull_request) return;
      
      const comment = context.payload.comment;
      const issue = context.payload.issue;
      const owner = context.payload.repository.owner.login;
      const repo = context.payload.repository.name;
      
      // Check if this mentions @open-rabbit with a command
      const commands = extractCommands(comment.body);
      
      if (commands.length > 0) {
        // Find the most recent bot comment in this PR
        const botComment = findLatestBotCommentForPR(owner, repo, issue.number);
        
        if (botComment) {
          await sendFeedbackToBackend({
            comment_id: botComment.commentId,
            review_session_id: botComment.reviewSessionId,
            owner,
            repo,
            pr_number: issue.number,
            file_path: botComment.filePath,
            line_number: botComment.lineNumber,
            ai_comment: botComment.aiComment,
            feedback_type: "command",
            user_feedback: comment.body,
            github_user: comment.user.login,
          });
          
          console.log(`[FeedbackHandler] Processed command from ${comment.user.login}: ${commands.join(", ")}`);
        }
      }
      
      // Also check if this is a reply to a bot comment
      // Issue comments don't have in_reply_to_id, so we check context
      if (isMentioningBot(comment.body)) {
        const botComment = findLatestBotCommentForPR(owner, repo, issue.number);
        
        if (botComment) {
          await sendFeedbackToBackend({
            comment_id: botComment.commentId,
            review_session_id: botComment.reviewSessionId,
            owner,
            repo,
            pr_number: issue.number,
            ai_comment: botComment.aiComment,
            feedback_type: "reply",
            user_feedback: comment.body,
            github_user: comment.user.login,
          });
        }
      }
    } catch (error) {
      console.error("[FeedbackHandler] Error processing issue comment:", error);
    }
  });
  
  /**
   * Handle reaction events on PR review comments
   * Note: This requires the 'pull_request_review_comment' event permission
   */
  app.on("pull_request_review_comment.edited", async (context) => {
    // Reactions are delivered as part of comment events in some cases
    // Handle them here if needed
    const comment = context.payload.comment;
    
    if (comment.reactions) {
      console.log(`[FeedbackHandler] Comment ${comment.id} has reactions:`, comment.reactions);
    }
  });
  
  /**
   * Cleanup old tracked comments (run periodically)
   */
  setInterval(() => {
    const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000);
    let cleaned = 0;
    
    for (const [key, data] of botCommentStore.entries()) {
      if (data.timestamp < oneHourAgo) {
        botCommentStore.delete(key);
        cleaned++;
      }
    }
    
    if (cleaned > 0) {
      console.log(`[FeedbackHandler] Cleaned up ${cleaned} old tracked comments`);
    }
  }, 30 * 60 * 1000); // Every 30 minutes
  
  console.log("[FeedbackHandler] Feedback handler registered");
};

/**
 * Check if a comment mentions the bot
 */
function isMentioningBot(body: string): boolean {
  const botMentions = ["@open-rabbit", "@openrabbit"];
  return botMentions.some(mention => body.toLowerCase().includes(mention.toLowerCase()));
}

/**
 * Find the latest bot comment for a PR
 */
function findLatestBotCommentForPR(owner: string, repo: string, prNumber: number): BotComment | undefined {
  let latest: BotComment | undefined;
  
  for (const [_key, data] of botCommentStore.entries()) {
    if (data.owner === owner && data.repo === repo && data.prNumber === prNumber) {
      if (!latest || data.timestamp > latest.timestamp) {
        latest = data;
      }
    }
  }
  
  return latest;
}

/**
 * Check if a comment ID belongs to our bot by fetching it from GitHub
 */
async function checkIfBotComment(
  context: Context<"pull_request_review_comment.created">,
  commentId: number
): Promise<boolean> {
  try {
    const response = await context.octokit.pulls.getReviewComment({
      owner: context.payload.repository.owner.login,
      repo: context.payload.repository.name,
      comment_id: commentId,
    });
    
    return isBotComment(response.data.user?.login || "");
  } catch (error) {
    console.error("[FeedbackHandler] Error fetching parent comment:", error);
    return false;
  }
}

/**
 * Export helper to register bot comments from other modules
 */
export const registerBotComment = (
  owner: string,
  repo: string,
  prNumber: number,
  commentId: string,
  aiComment: string,
  filePath?: string,
  lineNumber?: number,
  reviewSessionId?: string
): void => {
  trackBotComment({
    commentId,
    reviewSessionId,
    owner,
    repo,
    prNumber,
    filePath,
    lineNumber,
    aiComment,
  });
};
