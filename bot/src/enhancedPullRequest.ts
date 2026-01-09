/**
 * Enhanced Pull Request Handler with Knowledge Base Integration
 * 
 * This module handles PR events and:
 * 1. Fetches relevant learnings from the knowledge base
 * 2. Creates contextual review comments
 * 3. Tracks user feedback on bot comments
 * 4. Ingests interactions as learnings for future PRs
 */

import { Probot, Context } from "probot";
import { knowledgeBaseService } from "./services/knowledgeBase.js";
import {
  InlineComment,
  ReviewPayload,
  buildReviewForGitHub,
  createSuggestionIssue,
  createInlineComment,
  buildCollapsible,
  calculateStats,
} from "./utils/commentBuilder.js";

// Store bot comment IDs to track user feedback
const botCommentTracker = new Map<string, {
  commentId: string;
  content: string;
  metadata: any;
  timestamp: Date;
}>();

export default (app: Probot) => {
  
  /**
   * Handler for new pull requests
   */
  app.on("pull_request.opened", async (context) => {
    try {
      const pr = context.payload.pull_request;
      const repoName = context.payload.repository.full_name;
      
      console.log(`Processing PR #${pr.number} in ${repoName}`);

      // Get PR files
      const files = await context.octokit.pulls.listFiles({
        owner: context.payload.repository.owner.login,
        repo: context.payload.repository.name,
        pull_number: pr.number,
      });

      const changedFiles = files.data.map(f => f.filename);
      
      // Fetch relevant learnings from knowledge base
      const learnings = await knowledgeBaseService.getPRContextLearnings(
        pr.title || "",
        changedFiles,
        repoName,
        5 // Get top 5 learnings
      );

      // Create initial comment with learnings
      let initialComment = "Thanks for opening this PR! 🎉\n\n";
      
      if (learnings.length > 0) {
        initialComment += "I found some relevant learnings from past reviews:\n\n";
        learnings.forEach((learning, idx) => {
          initialComment += `${idx + 1}. ${learning.learning_text}\n`;
        });
        initialComment += "\n---\n";
      }
      
      initialComment += "A bot will review your code shortly!";

      await context.octokit.issues.createComment(
        context.issue({ body: initialComment })
      );

      // Create a review with comments and suggestions
      await createEnhancedReview(context, learnings);

    } catch (error) {
      console.error("Error processing PR:", error);
      // Still post a basic comment even if KB fails
      await context.octokit.issues.createComment(
        context.issue({ body: "Thanks for opening this PR! A bot will review your code shortly!" })
      );
    }
  });

  /**
   * Handler for PR updates (new commits)
   */
  app.on("pull_request.synchronize", async (context) => {
    try {
      const pr = context.payload.pull_request;
      const repoName = context.payload.repository.full_name;

      // Get updated files
      const files = await context.octokit.pulls.listFiles({
        owner: context.payload.repository.owner.login,
        repo: context.payload.repository.name,
        pull_number: pr.number,
      });

      const changedFiles = files.data.map(f => f.filename);
      
      // Fetch fresh learnings for updated PR
      const learnings = await knowledgeBaseService.getPRContextLearnings(
        pr.title || "",
        changedFiles,
        repoName,
        3
      );

      let updateComment = "🔄 New commits detected! Re-checking your changes...\n";
      
      if (learnings.length > 0) {
        updateComment += "\n**Relevant reminders:**\n";
        learnings.slice(0, 2).forEach(l => {
          updateComment += `- ${l.learning_text}\n`;
        });
      }

      await context.octokit.issues.createComment(
        context.issue({ body: updateComment })
      );

    } catch (error) {
      console.error("Error processing PR sync:", error);
    }
  });

  /**
   * Handler for review comments (to capture feedback and ingest to KB)
   */
  app.on("pull_request_review.submitted", async (context) => {
    try {
      const review = context.payload.review;
      const pr = context.payload.pull_request;
      const repoName = context.payload.repository.full_name;

      // Only process approved or commented reviews (not just "changes requested")
      if (review.state === "approved" || review.state === "commented") {
        console.log(`Review submitted on PR #${pr.number}: ${review.state}`);
        
        // If the review has a body comment, ingest it
        if (review.body && review.body.trim()) {
          await knowledgeBaseService.ingestReviewComment({
            commentId: `review-${review.id}`,
            comment: review.body,
            repoName,
            prNumber: pr.number,
            prTitle: pr.title,
            filePath: "PR-level-comment",
            author: review.user.login,
          });
        }
      }
    } catch (error) {
      console.error("Error processing review:", error);
    }
  });

  /**
   * Handler for individual review comments on specific lines
   */
  app.on("pull_request_review_comment.created", async (context) => {
    try {
      const comment = context.payload.comment;
      const pr = context.payload.pull_request;
      const repoName = context.payload.repository.full_name;

      console.log(`Review comment created on PR #${pr.number}`);

      const filePath = comment.path;
      const language = getLanguageFromPath(filePath);

      // Check if this is a reply to a bot comment
      if (comment.in_reply_to_id) {
        const parentCommentKey = `${repoName}-${pr.number}-${comment.in_reply_to_id}`;
        const botCommentData = botCommentTracker.get(parentCommentKey);
        
        if (botCommentData) {
          console.log(`User responded to bot comment ${comment.in_reply_to_id}`);
          
          const feedbackType = determineFeedbackType(comment.body);
          
          await knowledgeBaseService.ingestReviewComment({
            commentId: botCommentData.commentId,
            comment: botCommentData.content,
            codeSnippet: botCommentData.metadata.codeSnippet,
            language: botCommentData.metadata.language,
            repoName,
            prNumber: pr.number,
            prTitle: pr.title,
            filePath: botCommentData.metadata.filePath,
            author: "open-rabbit-bot",
            feedbackType,
            userResponse: comment.body,
            reviewer: comment.user.login,
          });
          
          console.log(`✅ Learning ingested with ${feedbackType} feedback from ${comment.user.login}`);
        }
      } else {
        await knowledgeBaseService.ingestReviewComment({
          commentId: `comment-${comment.id}`,
          comment: comment.body,
          codeSnippet: comment.diff_hunk,
          language,
          repoName,
          prNumber: pr.number,
          prTitle: pr.title,
          filePath,
          author: comment.user.login,
        });
      }

    } catch (error) {
      console.error("Error processing review comment:", error);
    }
  });

  /**
   * Handler for issue comments (includes PR comments and replies)
   */
  app.on("issue_comment.created", async (context) => {
    try {
      if (!context.payload.issue.pull_request) return;

      const comment = context.payload.comment;
      const issue = context.payload.issue;
      const repoName = context.payload.repository.full_name;

      const prNumber = issue.number;
      const commentBody = comment.body.toLowerCase();

      for (const [key, botCommentData] of botCommentTracker.entries()) {
        if (key.startsWith(`${repoName}-${prNumber}-`)) {
          const feedbackType = determineFeedbackType(commentBody);
          
          if (feedbackType !== 'ignored') {
            await knowledgeBaseService.ingestReviewComment({
              commentId: botCommentData.commentId,
              comment: botCommentData.content,
              codeSnippet: botCommentData.metadata.codeSnippet,
              language: botCommentData.metadata.language,
              repoName,
              prNumber,
              prTitle: issue.title,
              filePath: botCommentData.metadata.filePath,
              author: "open-rabbit-bot",
              feedbackType,
              userResponse: comment.body,
              reviewer: comment.user.login,
            });
            
            console.log(`✅ Learning ingested from issue comment with ${feedbackType} feedback`);
          }
        }
      }
    } catch (error) {
      console.error("Error processing issue comment:", error);
    }
  });

  /**
   * Handler for reactions on comments (thumbs up/down, etc.)
   */
  app.on([
    "pull_request_review_comment.edited",
    "issue_comment.edited"
  ], async (_context) => {
    console.log("Comment edited - potential feedback signal");
  });

  setInterval(() => {
    const now = new Date();
    const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000);
    
    for (const [key, data] of botCommentTracker.entries()) {
      if (data.timestamp < oneHourAgo) {
        botCommentTracker.delete(key);
      }
    }
    
    if (botCommentTracker.size > 0) {
      console.log(`🧹 Cleaned up old bot comment trackers. Current size: ${botCommentTracker.size}`);
    }
  }, 30 * 60 * 1000);
};

/**
 * Create an enhanced review with knowledge base context using professional formatting
 */
async function createEnhancedReview(
  context: Context<"pull_request.opened">,
  learnings: any[]
) {
  const pr = context.payload.pull_request;
  const repoName = context.payload.repository.full_name;
  
  const inlineComments: InlineComment[] = [];
  
  const files = await context.octokit.pulls.listFiles({
    owner: context.payload.repository.owner.login,
    repo: context.payload.repository.name,
    pull_number: pr.number,
  });

  for (const file of files.data.slice(0, 3)) { 
    if (!file.filename.match(/\.(js|ts|py|java|go|rb|php|cpp|c|h)$/)) {
      continue;
    }

    const language = getLanguageFromPath(file.filename);

    const relevantLearnings = learnings.filter(l => 
      !l.language || l.language === language
    );

    if (relevantLearnings.length > 0 && file.patch) {
      const learning = relevantLearnings[0];
      const lines = file.patch.split('\n');
      const addedLines = lines.filter(l => l.startsWith('+')).length;
      
      if (addedLines > 0) {
        // Find a valid line in the diff (prefer lines with actual code changes)
        let targetLine = 1;
        let lineCounter = 0;
        for (const line of lines) {
          if (line.startsWith('@@')) {
            // Parse the @@ -a,b +c,d @@ format to get the starting line
            const match = line.match(/@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
            if (match) {
              targetLine = parseInt(match[1], 10);
              lineCounter = 0;
            }
          } else if (!line.startsWith('-')) {
            lineCounter++;
            if (line.startsWith('+') && lineCounter <= 10) {
              targetLine = targetLine + lineCounter - 1;
              break;
            }
          }
        }

        // Create a structured issue using the new format
        const issue = createSuggestionIssue(
          'best-practice',
          'Project Learning',
          learning.learning_text,
          {
            details: learning.original_comment 
              ? `From a previous code review:\n\n> ${learning.original_comment.substring(0, 200)}${learning.original_comment.length > 200 ? '...' : ''}`
              : undefined,
            learnings: relevantLearnings.slice(1, 3).map((l: any) => l.learning_text),
          }
        );

        // Create the inline comment
        const comment = createInlineComment(
          file.filename,
          targetLine,
          issue,
          { side: 'RIGHT' }
        );

        inlineComments.push(comment);

        // Track for feedback collection
        const botCommentId = `bot-${Date.now()}-${file.filename}`;
        botCommentTracker.set(`${repoName}-${pr.number}-${botCommentId}`, {
          commentId: botCommentId,
          content: learning.learning_text,
          metadata: {
            codeSnippet: file.patch?.substring(0, 200),
            language,
            filePath: file.filename,
          },
          timestamp: new Date(),
        });
        
        console.log(`📚 Tracked bot comment ${botCommentId} for feedback collection`);
      }
    }
  }

  if (inlineComments.length > 0) {
    try {
      // Build learnings summary for the review body
      const usedLearningsText = learnings.slice(0, 3).map((l, idx) => {
        const source = l.source || {};
        return `**Learning ${idx + 1}:**\n` +
               `- From: ${source.author || 'unknown'} (PR #${source.pr_number || 'N/A'})\n` +
               `- File: ${source.file_path || 'N/A'}\n` +
               `- Context: ${l.learning_text}\n` +
               `- Confidence: ${(l.confidence_score * 100).toFixed(0)}%`;
      }).join('\n\n');

      const learningsCollapsible = buildCollapsible(
        '📚 Learnings used in this review',
        usedLearningsText,
        false
      );

      // Build the review payload
      const reviewPayload: ReviewPayload = {
        summary: `I've analyzed your changes with context from past code reviews.\n\n${learningsCollapsible}\n\n---\n\n💡 These suggestions are based on patterns and feedback from previous PRs in this repository.`,
        comments: inlineComments,
        event: 'COMMENT',
        stats: calculateStats(inlineComments),
      };

      // Format for GitHub API
      const formattedReview = buildReviewForGitHub(reviewPayload, console.warn);

      // Log any skipped comments
      if (formattedReview.skipped.length > 0) {
        console.warn(`Skipped ${formattedReview.skipped.length} invalid comments`);
      }

      // Only create review if we have valid comments
      if (formattedReview.comments.length > 0) {
        await context.octokit.pulls.createReview({
          owner: context.payload.repository.owner.login,
          repo: context.payload.repository.name,
          pull_number: pr.number,
          event: "COMMENT",
          body: formattedReview.body,
          comments: formattedReview.comments,
        });
        
        console.log(`✅ Created review with ${formattedReview.comments.length} comments using ${learnings.length} learnings`);
      } else {
        console.log(`⚠️ No valid comments to post after formatting`);
      }
    } catch (error) {
      console.error("Error creating review:", error);
    }
  }
}

function getLanguageFromPath(path: string): string {
  const ext = path.split('.').pop()?.toLowerCase();
  const langMap: { [key: string]: string } = {
    'js': 'javascript',
    'ts': 'typescript',
    'tsx': 'typescript',
    'jsx': 'javascript',
    'py': 'python',
    'java': 'java',
    'go': 'go',
    'rb': 'ruby',
    'php': 'php',
    'cpp': 'cpp',
    'c': 'c',
    'h': 'c',
    'cs': 'csharp',
    'rs': 'rust',
    'swift': 'swift',
    'kt': 'kotlin',
  };
  return langMap[ext || ''] || 'unknown';
}

function determineFeedbackType(userResponse: string): 'accepted' | 'rejected' | 'modified' | 'thanked' | 'debated' | 'ignored' {
  const lower = userResponse.toLowerCase();
  
  if (lower.match(/thank|thanks|good|great|helpful|perfect|exactly|agreed|correct|nice|👍|✅/)) {
    return 'thanked';
  }
  
  if (lower.match(/done|fixed|applied|committed|merged|updated|changed/)) {
    return 'accepted';
  }
  
  if (lower.match(/disagree|no|nope|wrong|incorrect|not sure|don't think|shouldn't|❌|👎/)) {
    return 'rejected';
  }
  
  if (lower.match(/but|however|what about|instead|alternatively|consider|modify/)) {
    return 'debated';
  }
  
  if (lower.match(/modified|adjusted|tweaked|adapted|different approach/)) {
    return 'modified';
  }
  
  return 'ignored';
}
