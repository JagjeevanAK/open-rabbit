/**
 * Professional GitHub Comment Builder
 * 
 * This module provides types and utilities for building professional,
 * well-formatted GitHub PR review comments with:
 * - 5 severity levels (critical, warning, suggestion, nitpick, praise)
 * - Collapsible sections using <details><summary> tags
 * - GitHub suggestion blocks for auto-applicable fixes
 * - Diff preview blocks for before/after comparisons
 * - Multi-line comment support
 */

// =============================================================================
// TYPES
// =============================================================================

/**
 * Severity levels for review issues
 */
export type IssueSeverity = 'critical' | 'warning' | 'suggestion' | 'nitpick' | 'praise';

/**
 * Categories for classifying issues
 */
export type IssueCategory = 
  | 'security' 
  | 'performance' 
  | 'bug' 
  | 'style' 
  | 'refactor' 
  | 'docs' 
  | 'test'
  | 'best-practice';

/**
 * Core review issue structure
 */
export interface ReviewIssue {
  /** Severity level of the issue */
  severity: IssueSeverity;
  /** Category for classification */
  category: IssueCategory;
  /** Short title for the issue */
  title: string;
  /** Detailed description of the issue */
  description: string;
  /** Code for GitHub suggestion block (auto-applicable) */
  suggestion?: string;
  /** Diff preview showing before/after */
  diffPreview?: {
    before: string;
    after: string;
  };
  /** Additional details (shown in collapsible section) */
  details?: string;
  /** Related learnings from knowledge base */
  learnings?: string[];
  /** AI agent prompt (shown in collapsible section) */
  aiPrompt?: string;
}

/**
 * Inline comment structure for PR reviews
 * Note: No file-level comments - all comments must be on specific lines
 */
export interface InlineComment {
  /** File path relative to repo root */
  path: string;
  /** End line number (or single line for single-line comments) */
  line: number;
  /** Start line for multi-line comments */
  startLine?: number;
  /** Side of the diff: LEFT = old code, RIGHT = new code */
  side?: 'LEFT' | 'RIGHT';
  /** Side for start_line in multi-line comments */
  startSide?: 'LEFT' | 'RIGHT';
  /** The review issue to display */
  issue: ReviewIssue;
}

/**
 * Statistics for the review
 */
export interface ReviewStats {
  critical: number;
  warning: number;
  suggestion: number;
  nitpick: number;
  praise: number;
  filesReviewed: number;
}

/**
 * Full review payload
 */
export interface ReviewPayload {
  /** Summary text for the review body */
  summary: string;
  /** List of inline comments */
  comments: InlineComment[];
  /** Review event type */
  event: 'COMMENT' | 'APPROVE' | 'REQUEST_CHANGES';
  /** Optional statistics */
  stats?: ReviewStats;
}

/**
 * GitHub API comment format
 */
export interface GitHubReviewComment {
  path: string;
  body: string;
  line: number;
  side: 'LEFT' | 'RIGHT';
  start_line?: number;
  start_side?: 'LEFT' | 'RIGHT';
}

/**
 * Result of formatting comments for GitHub
 */
export interface FormattedReviewResult {
  /** Successfully formatted comments */
  comments: GitHubReviewComment[];
  /** Comments that failed validation (logged and skipped) */
  skipped: Array<{
    comment: InlineComment;
    reason: string;
  }>;
}

// =============================================================================
// CONSTANTS
// =============================================================================

/**
 * Icons for each severity level
 */
export const SEVERITY_ICONS: Record<IssueSeverity, string> = {
  critical: '🚨',
  warning: '⚠️',
  suggestion: '💡',
  nitpick: '📝',
  praise: '✨',
};

/**
 * Labels for each severity level
 */
export const SEVERITY_LABELS: Record<IssueSeverity, string> = {
  critical: 'Critical',
  warning: 'Warning',
  suggestion: 'Suggestion',
  nitpick: 'Nitpick',
  praise: 'Nice!',
};

/**
 * Icons for each category
 */
export const CATEGORY_ICONS: Record<IssueCategory, string> = {
  security: '🔒',
  performance: '⚡',
  bug: '🐛',
  style: '🎨',
  refactor: '♻️',
  docs: '📚',
  test: '🧪',
  'best-practice': '✅',
};

/**
 * Labels for each category
 */
export const CATEGORY_LABELS: Record<IssueCategory, string> = {
  security: 'Security',
  performance: 'Performance',
  bug: 'Bug',
  style: 'Code Style',
  refactor: 'Refactoring',
  docs: 'Documentation',
  test: 'Testing',
  'best-practice': 'Best Practice',
};

// =============================================================================
// BUILDER FUNCTIONS
// =============================================================================

/**
 * Build a collapsible section using HTML details/summary tags
 * 
 * @param title - The summary/title shown when collapsed
 * @param content - The content shown when expanded
 * @param open - Whether to show expanded by default (default: false)
 * @returns Formatted collapsible section
 */
export function buildCollapsible(
  title: string,
  content: string,
  open: boolean = false
): string {
  const openAttr = open ? ' open' : '';
  return `<details${openAttr}>
<summary>${title}</summary>

${content}

</details>`;
}

/**
 * Build a GitHub suggestion block (auto-applicable fix)
 * 
 * @param code - The suggested replacement code
 * @param language - Optional language hint (usually not needed for suggestions)
 * @returns Formatted suggestion block
 */
export function buildSuggestionBlock(code: string, _language?: string): string {
  // GitHub suggestion blocks don't typically use language hints
  // but we support it for flexibility (parameter kept for API compatibility)
  return `\`\`\`suggestion
${code}
\`\`\``;
}

/**
 * Build a diff preview block showing before/after
 * 
 * @param before - The original code
 * @param after - The suggested replacement
 * @returns Formatted diff block
 */
export function buildDiffBlock(before: string, after: string): string {
  const beforeLines = before.split('\n').map(line => `- ${line}`).join('\n');
  const afterLines = after.split('\n').map(line => `+ ${line}`).join('\n');
  
  return `\`\`\`diff
${beforeLines}
${afterLines}
\`\`\``;
}

/**
 * Build a code block with optional language
 * 
 * @param code - The code content
 * @param language - Optional language for syntax highlighting
 * @returns Formatted code block
 */
export function buildCodeBlock(code: string, language?: string): string {
  const lang = language || '';
  return `\`\`\`${lang}
${code}
\`\`\``;
}

/**
 * Build the header for an inline comment based on severity and category
 * 
 * @param issue - The review issue
 * @returns Formatted header string
 */
export function buildCommentHeader(issue: ReviewIssue): string {
  const severityIcon = SEVERITY_ICONS[issue.severity];
  const severityLabel = SEVERITY_LABELS[issue.severity];
  const categoryIcon = CATEGORY_ICONS[issue.category];
  const categoryLabel = CATEGORY_LABELS[issue.category];
  
  return `**${severityIcon} ${severityLabel}** | ${categoryIcon} ${categoryLabel}`;
}

/**
 * Build a complete inline comment body from a ReviewIssue
 * 
 * @param issue - The review issue to format
 * @returns Formatted comment body ready for GitHub
 */
export function buildInlineComment(issue: ReviewIssue): string {
  const parts: string[] = [];
  
  // Header with severity and category
  parts.push(buildCommentHeader(issue));
  parts.push('');
  
  // Title (bold)
  parts.push(`**${issue.title}**`);
  parts.push('');
  
  // Description
  parts.push(issue.description);
  
  // Suggestion block (if provided)
  if (issue.suggestion) {
    parts.push('');
    parts.push(buildSuggestionBlock(issue.suggestion));
  }
  
  // Diff preview (if provided and no suggestion)
  if (issue.diffPreview && !issue.suggestion) {
    parts.push('');
    parts.push(buildDiffBlock(issue.diffPreview.before, issue.diffPreview.after));
  }
  
  // Details section (collapsible, closed by default)
  if (issue.details) {
    parts.push('');
    parts.push(buildCollapsible('More details', issue.details, false));
  }
  
  // Learnings section (collapsible, closed by default)
  if (issue.learnings && issue.learnings.length > 0) {
    const learningsContent = issue.learnings
      .map((learning, idx) => `${idx + 1}. ${learning}`)
      .join('\n');
    parts.push('');
    parts.push(buildCollapsible(
      '📚 Related learnings from this project',
      learningsContent,
      false
    ));
  }
  
  // AI prompt section (collapsible, closed by default)
  if (issue.aiPrompt) {
    parts.push('');
    parts.push(buildCollapsible(
      '🤖 Prompt for AI Agents',
      buildCodeBlock(issue.aiPrompt),
      false
    ));
  }
  
  return parts.join('\n');
}

/**
 * Validate an inline comment before formatting
 * 
 * @param comment - The inline comment to validate
 * @returns Validation result with success status and optional error message
 */
export function validateInlineComment(comment: InlineComment): { 
  valid: boolean; 
  error?: string;
} {
  // Path is required
  if (!comment.path || comment.path.trim() === '') {
    return { valid: false, error: 'Missing file path' };
  }
  
  // Line is required and must be positive
  if (!comment.line || comment.line < 1) {
    return { valid: false, error: 'Invalid line number (must be >= 1)' };
  }
  
  // If startLine is provided, it must be less than line
  if (comment.startLine !== undefined) {
    if (comment.startLine < 1) {
      return { valid: false, error: 'Invalid start_line (must be >= 1)' };
    }
    if (comment.startLine >= comment.line) {
      return { valid: false, error: 'start_line must be less than line' };
    }
  }
  
  // Issue is required
  if (!comment.issue) {
    return { valid: false, error: 'Missing issue data' };
  }
  
  // Issue must have required fields
  if (!comment.issue.title || !comment.issue.description) {
    return { valid: false, error: 'Issue missing title or description' };
  }
  
  return { valid: true };
}

/**
 * Format a single InlineComment for the GitHub API
 * 
 * @param comment - The inline comment to format
 * @returns GitHub API comment format or null if invalid
 */
export function formatCommentForGitHub(comment: InlineComment): GitHubReviewComment | null {
  const validation = validateInlineComment(comment);
  if (!validation.valid) {
    return null;
  }
  
  const formatted: GitHubReviewComment = {
    path: comment.path,
    body: buildInlineComment(comment.issue),
    line: comment.line,
    side: comment.side || 'RIGHT',
  };
  
  // Add multi-line support
  if (comment.startLine && comment.startLine < comment.line) {
    formatted.start_line = comment.startLine;
    formatted.start_side = comment.startSide || 'RIGHT';
  }
  
  return formatted;
}

/**
 * Format multiple InlineComments for the GitHub API
 * Invalid comments are logged and skipped (not included in result)
 * 
 * @param comments - Array of inline comments to format
 * @param logger - Optional logger function for skipped comments
 * @returns Formatted comments and list of skipped comments
 */
export function formatCommentsForGitHub(
  comments: InlineComment[],
  logger?: (message: string) => void
): FormattedReviewResult {
  const result: FormattedReviewResult = {
    comments: [],
    skipped: [],
  };
  
  for (const comment of comments) {
    const validation = validateInlineComment(comment);
    
    if (!validation.valid) {
      const skipInfo = {
        comment,
        reason: validation.error || 'Unknown validation error',
      };
      result.skipped.push(skipInfo);
      
      if (logger) {
        logger(`Skipping invalid comment on ${comment.path}:${comment.line} - ${validation.error}`);
      }
      continue;
    }
    
    const formatted = formatCommentForGitHub(comment);
    if (formatted) {
      result.comments.push(formatted);
    }
  }
  
  return result;
}

/**
 * Build a statistics table for the review summary
 * 
 * @param stats - Review statistics
 * @returns Formatted markdown table
 */
export function buildStatsTable(stats: ReviewStats): string {
  const rows = [
    `| ${SEVERITY_ICONS.critical} Critical | ${stats.critical} |`,
    `| ${SEVERITY_ICONS.warning} Warning | ${stats.warning} |`,
    `| ${SEVERITY_ICONS.suggestion} Suggestion | ${stats.suggestion} |`,
    `| ${SEVERITY_ICONS.nitpick} Nitpick | ${stats.nitpick} |`,
    `| ${SEVERITY_ICONS.praise} Praise | ${stats.praise} |`,
  ];
  
  return `| Type | Count |
|------|-------|
${rows.join('\n')}

**Files reviewed:** ${stats.filesReviewed}`;
}

/**
 * Calculate statistics from a list of inline comments
 * 
 * @param comments - Array of inline comments
 * @returns Calculated statistics
 */
export function calculateStats(comments: InlineComment[]): ReviewStats {
  const stats: ReviewStats = {
    critical: 0,
    warning: 0,
    suggestion: 0,
    nitpick: 0,
    praise: 0,
    filesReviewed: 0,
  };
  
  const files = new Set<string>();
  
  for (const comment of comments) {
    stats[comment.issue.severity]++;
    files.add(comment.path);
  }
  
  stats.filesReviewed = files.size;
  
  return stats;
}

/**
 * Determine the appropriate review event based on issues found
 * 
 * @param stats - Review statistics
 * @returns Recommended review event
 */
export function determineReviewEvent(stats: ReviewStats): 'COMMENT' | 'APPROVE' | 'REQUEST_CHANGES' {
  // If there are critical issues, request changes
  if (stats.critical > 0) {
    return 'REQUEST_CHANGES';
  }
  
  // If there are only praises (or nothing), approve
  if (stats.warning === 0 && stats.suggestion === 0 && stats.nitpick === 0) {
    return 'APPROVE';
  }
  
  // Otherwise, just comment
  return 'COMMENT';
}

/**
 * Build the complete review summary body
 * 
 * @param payload - The review payload
 * @returns Formatted summary body
 */
export function buildReviewSummary(payload: ReviewPayload): string {
  const parts: string[] = [];
  
  // Main summary
  parts.push('## Code Review Summary');
  parts.push('');
  parts.push(payload.summary);
  
  // Statistics table (if available)
  if (payload.stats) {
    parts.push('');
    parts.push('### Overview');
    parts.push('');
    parts.push(buildStatsTable(payload.stats));
  }
  
  // If there are comments, mention them
  if (payload.comments.length > 0) {
    parts.push('');
    parts.push(`*${payload.comments.length} inline comment(s) below.*`);
  }
  
  return parts.join('\n');
}

/**
 * Build a complete review ready for the GitHub API
 * 
 * @param payload - The review payload
 * @param logger - Optional logger for skipped comments
 * @returns Object ready for octokit.pulls.createReview
 */
export function buildReviewForGitHub(
  payload: ReviewPayload,
  logger?: (message: string) => void
): {
  body: string;
  event: 'COMMENT' | 'APPROVE' | 'REQUEST_CHANGES';
  comments: GitHubReviewComment[];
  skipped: Array<{ comment: InlineComment; reason: string }>;
} {
  // Format all comments
  const formattedResult = formatCommentsForGitHub(payload.comments, logger);
  
  // Calculate stats if not provided
  const stats = payload.stats || calculateStats(payload.comments);
  
  // Build summary with stats
  const payloadWithStats = { ...payload, stats };
  const body = buildReviewSummary(payloadWithStats);
  
  return {
    body,
    event: payload.event,
    comments: formattedResult.comments,
    skipped: formattedResult.skipped,
  };
}

// =============================================================================
// HELPER FACTORIES
// =============================================================================

/**
 * Create a critical issue
 */
export function createCriticalIssue(
  category: IssueCategory,
  title: string,
  description: string,
  options?: Partial<Omit<ReviewIssue, 'severity' | 'category' | 'title' | 'description'>>
): ReviewIssue {
  return {
    severity: 'critical',
    category,
    title,
    description,
    ...options,
  };
}

/**
 * Create a warning issue
 */
export function createWarningIssue(
  category: IssueCategory,
  title: string,
  description: string,
  options?: Partial<Omit<ReviewIssue, 'severity' | 'category' | 'title' | 'description'>>
): ReviewIssue {
  return {
    severity: 'warning',
    category,
    title,
    description,
    ...options,
  };
}

/**
 * Create a suggestion issue
 */
export function createSuggestionIssue(
  category: IssueCategory,
  title: string,
  description: string,
  options?: Partial<Omit<ReviewIssue, 'severity' | 'category' | 'title' | 'description'>>
): ReviewIssue {
  return {
    severity: 'suggestion',
    category,
    title,
    description,
    ...options,
  };
}

/**
 * Create a nitpick issue
 */
export function createNitpickIssue(
  category: IssueCategory,
  title: string,
  description: string,
  options?: Partial<Omit<ReviewIssue, 'severity' | 'category' | 'title' | 'description'>>
): ReviewIssue {
  return {
    severity: 'nitpick',
    category,
    title,
    description,
    ...options,
  };
}

/**
 * Create a praise issue
 */
export function createPraiseIssue(
  category: IssueCategory,
  title: string,
  description: string,
  options?: Partial<Omit<ReviewIssue, 'severity' | 'category' | 'title' | 'description'>>
): ReviewIssue {
  return {
    severity: 'praise',
    category,
    title,
    description,
    ...options,
  };
}

/**
 * Create an inline comment with multi-line support
 */
export function createInlineComment(
  path: string,
  line: number,
  issue: ReviewIssue,
  options?: {
    startLine?: number;
    side?: 'LEFT' | 'RIGHT';
    startSide?: 'LEFT' | 'RIGHT';
  }
): InlineComment {
  return {
    path,
    line,
    issue,
    startLine: options?.startLine,
    side: options?.side || 'RIGHT',
    startSide: options?.startSide || 'RIGHT',
  };
}
