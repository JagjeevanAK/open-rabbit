/**
 * Enhanced Pull Request Handler with Knowledge Base Integration
 * 
 * This module handles PR events and:
 * 1. Fetches relevant learnings from the knowledge base
 * 2. Creates contextual review comments
 * 3. Ingests review feedback back into the knowledge base
 */

import { Probot, Context } from "probot";
import { knowledgeBaseService } from "./services/knowledgeBase.js";

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

      // Extract language from file extension
      const filePath = comment.path;
      const language = getLanguageFromPath(filePath);

      // Ingest the comment to knowledge base
      await knowledgeBaseService.ingestReviewComment({
        commentId: `comment-${comment.id}`,
        comment: comment.body,
        codeSnippet: comment.diff_hunk, // Contains code context
        language,
        repoName,
        prNumber: pr.number,
        prTitle: pr.title,
        filePath,
        author: comment.user.login,
      });

    } catch (error) {
      console.error("Error processing review comment:", error);
    }
  });
};

/**
 * Create an enhanced review with knowledge base context
 */
async function createEnhancedReview(
  context: Context<"pull_request.opened">,
  learnings: any[]
) {
  const pr = context.payload.pull_request;
  const repoName = context.payload.repository.full_name;
  
  // Example review comments - in production, these would come from your AI analysis
  const reviewComments = [];
  
  // Check for common issues based on learnings
  const files = await context.octokit.pulls.listFiles({
    owner: context.payload.repository.owner.login,
    repo: context.payload.repository.name,
    pull_number: pr.number,
  });

  for (const file of files.data.slice(0, 3)) { // Limit to first 3 files for demo
    // Skip binary files
    if (!file.filename.match(/\.(js|ts|py|java|go|rb|php|cpp|c|h)$/)) {
      continue;
    }

    const language = getLanguageFromPath(file.filename);

    // Analyze file and create suggestion based on learnings
    const relevantLearnings = learnings.filter(l => 
      !l.language || l.language === language
    );

    if (relevantLearnings.length > 0 && file.patch) {
      // Create a comment applying the learning
      const learning = relevantLearnings[0];
      const lines = file.patch.split('\n');
      const addedLines = lines.filter(l => l.startsWith('+')).length;
      
      if (addedLines > 0) {
        // Find a position in the patch (simplified - in production, use more sophisticated logic)
        const position = Math.min(5, lines.length - 1);
        
        reviewComments.push({
          path: file.filename,
          position,
          body: `💡 **Based on project learnings:** ${learning.learning_text}\n\n_This suggestion is based on past code reviews in this repository._`,
        });

        // Ingest this bot comment to KB for future reference
        await knowledgeBaseService.ingestReviewComment({
          commentId: `bot-${Date.now()}-${file.filename}`,
          comment: learning.learning_text,
          codeSnippet: file.patch?.substring(0, 200),
          language,
          repoName,
          prNumber: pr.number,
          prTitle: pr.title,
          filePath: file.filename,
          author: "open-rabbit-bot",
        });
      }
    }
  }

  // Create the review if we have comments
  if (reviewComments.length > 0) {
    try {
      await context.octokit.pulls.createReview({
        owner: context.payload.repository.owner.login,
        repo: context.payload.repository.name,
        pull_number: pr.number,
        event: "COMMENT",
        body: "🤖 **AI-Powered Review with Project Context**\n\nI've analyzed your changes with context from past code reviews:",
        comments: reviewComments,
      });
    } catch (error) {
      console.error("Error creating review:", error);
    }
  }
}

/**
 * Get programming language from file path
 */
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
