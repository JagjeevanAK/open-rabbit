import { Learning } from "../services/knowledgeBase.js";

// Re-export all types and functions from commentBuilder for convenience
export * from "./commentBuilder.js";

export function formatLearningsAsComment(
  learnings: Learning[],
  options?: {
    title?: string;
    maxLearnings?: number;
    includeConfidence?: boolean;
    includeSource?: boolean;
  }
): string {
  if (learnings.length === 0) {
    return "";
  }

  const {
    title = "Relevant Project Learnings",
    maxLearnings = 5,
    includeConfidence = true,
    includeSource = false,
  } = options || {};

  const limitedLearnings = learnings.slice(0, maxLearnings);

  let comment = `\n\n---\n\n### ${title}\n\n`;
  comment += "*Based on past code reviews in this repository:*\n\n";

  limitedLearnings.forEach((learning, index) => {
    comment += `${index + 1}. **${learning.learning_text}**\n`;

    if (includeConfidence && learning.confidence_score) {
      const confidencePercent = (learning.confidence_score * 100).toFixed(0);
      const emoji = learning.confidence_score >= 0.8 ? "✅" : "ℹ️";
      comment += `   ${emoji} *Confidence: ${confidencePercent}%*\n`;
    }

    if (includeSource && learning.original_comment) {
      const preview =
        learning.original_comment.length > 100
          ? learning.original_comment.substring(0, 97) + "..."
          : learning.original_comment;
      comment += `   > ${preview}\n`;
    }

    comment += "\n";
  });

  if (learnings.length > maxLearnings) {
    comment += `*... and ${learnings.length - maxLearnings} more learnings*\n`;
  }

  return comment;
}

export function formatLearningsAsReviewComments(
  learnings: Learning[]
): string {
  if (learnings.length === 0) {
    return "";
  }

  let comment = "💡 **Relevant Learning:**\n\n";
  const topLearning = learnings[0];

  comment += `${topLearning.learning_text}\n\n`;

  if (topLearning.code_context) {
    comment += "**Example:**\n```";
    if (topLearning.language) {
      comment += topLearning.language;
    }
    comment += `\n${topLearning.code_context}\n\`\`\`\n\n`;
  }

  comment += "*This suggestion is based on past code reviews in this repository.*";

  return comment;
}

export function createSuggestionComment(
  learning: Learning,
  originalCode: string,
  suggestedCode: string
): string {
  let comment = `💡 **${learning.learning_text}**\n\n`;

  comment += "**Current:**\n```";
  if (learning.language) {
    comment += learning.language;
  }
  comment += `\n${originalCode}\n\`\`\`\n\n`;

  comment += "**Suggested:**\n\`\`\`suggestion\n";
  comment += `${suggestedCode}\n\`\`\`\n\n`;

  comment += "*Based on past code reviews*";

  return comment;
}

export function extractCodeSnippetFromPatch(
  patch: string,
  maxLines: number = 10
): string {
  const lines = patch.split("\n");
  const codeLines = lines
    .filter((line) => line.startsWith("+") && !line.startsWith("+++"))
    .map((line) => line.substring(1))
    .slice(0, maxLines);

  return codeLines.join("\n");
}

export function parseSuggestionFromComment(comment: string): {
  hasSuggestion: boolean;
  originalText?: string;
  suggestedText?: string;
} {
  const suggestionMatch = comment.match(/```suggestion\n([\s\S]*?)\n```/);

  if (suggestionMatch) {
    return {
      hasSuggestion: true,
      suggestedText: suggestionMatch[1],
    };
  }

  return { hasSuggestion: false };
}

export function categorizeLearning(learning: Learning): string {
  const text = learning.learning_text.toLowerCase();

  if (text.includes("test") || text.includes("testing")) {
    return "testing";
  } else if (text.includes("security") || text.includes("vulnerability")) {
    return "security";
  } else if (
    text.includes("performance") ||
    text.includes("optimization") ||
    text.includes("efficient")
  ) {
    return "performance";
  } else if (
    text.includes("style") ||
    text.includes("format") ||
    text.includes("convention")
  ) {
    return "style";
  } else if (text.includes("error") || text.includes("exception")) {
    return "error-handling";
  } else if (text.includes("document") || text.includes("comment")) {
    return "documentation";
  } else if (text.includes("refactor") || text.includes("clean")) {
    return "refactoring";
  } else {
    return "best-practice";
  }
}

export function groupLearningsByCategory(learnings: Learning[]): {
  [category: string]: Learning[];
} {
  return learnings.reduce(
    (groups, learning) => {
      const category = categorizeLearning(learning);
      if (!groups[category]) {
        groups[category] = [];
      }
      groups[category].push(learning);
      return groups;
    },
    {} as { [category: string]: Learning[] }
  );
}

export function formatGroupedLearnings(
  learnings: Learning[],
  maxPerCategory: number = 3
): string {
  const grouped = groupLearningsByCategory(learnings);
  const categoryEmojis: { [key: string]: string } = {
    testing: "🧪",
    security: "🔒",
    performance: "⚡",
    style: "🎨",
    "error-handling": "🚨",
    documentation: "📝",
    refactoring: "♻️",
    "best-practice": "✨",
  };

  const categoryNames: { [key: string]: string } = {
    testing: "Testing",
    security: "Security",
    performance: "Performance",
    style: "Code Style",
    "error-handling": "Error Handling",
    documentation: "Documentation",
    refactoring: "Refactoring",
    "best-practice": "Best Practices",
  };

  let comment = "\n\n---\n\n### 📚 Project Knowledge Base\n\n";
  comment += "*Here are relevant learnings from past code reviews:*\n\n";

  Object.entries(grouped).forEach(([category, categoryLearnings]) => {
    const emoji = categoryEmojis[category] || "💡";
    const name = categoryNames[category] || category;

    comment += `#### ${emoji} ${name}\n\n`;

    categoryLearnings.slice(0, maxPerCategory).forEach((learning) => {
      comment += `- ${learning.learning_text}\n`;
    });

    comment += "\n";
  });

  return comment;
}

export function createLearningSummary(learnings: Learning[]): string {
  if (learnings.length === 0) {
    return "No relevant learnings found for this PR.";
  }

  const grouped = groupLearningsByCategory(learnings);
  const categories = Object.keys(grouped);

  let summary = `Found ${learnings.length} relevant learning(s) `;
  summary += `across ${categories.length} category(ies): `;
  summary += categories.join(", ");

  return summary;
}

export function isActionableComment(comment: string): boolean {
  const actionableKeywords = [
    "please",
    "should",
    "must",
    "need to",
    "consider",
    "suggest",
    "recommend",
    "fix",
    "update",
    "change",
    "add",
    "remove",
  ];

  const lowerComment = comment.toLowerCase();
  return actionableKeywords.some((keyword) => lowerComment.includes(keyword));
}

export function extractSentiment(
  comment: string
): "positive" | "neutral" | "negative" {
  const positiveKeywords = [
    "great",
    "good",
    "excellent",
    "nice",
    "well done",
    "perfect",
    "thanks",
    "appreciate",
  ];
  const negativeKeywords = [
    "issue",
    "problem",
    "error",
    "bug",
    "wrong",
    "incorrect",
    "bad",
    "poor",
  ];

  const lowerComment = comment.toLowerCase();

  const positiveScore = positiveKeywords.filter((kw) =>
    lowerComment.includes(kw)
  ).length;
  const negativeScore = negativeKeywords.filter((kw) =>
    lowerComment.includes(kw)
  ).length;

  if (positiveScore > negativeScore) {
    return "positive";
  } else if (negativeScore > positiveScore) {
    return "negative";
  }
  return "neutral";
}

export function formatResponseWithLearnings(
  question: string,
  answer: string,
  relevantLearnings: Learning[]
): string {
  let response = `**Q: ${question}**\n\n`;
  response += `${answer}\n\n`;

  if (relevantLearnings.length > 0) {
    response += "**Related learnings from this project:**\n\n";
    relevantLearnings.forEach((learning, idx) => {
      response += `${idx + 1}. ${learning.learning_text}\n`;
    });
  }

  return response;
}
