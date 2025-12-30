import axios, { AxiosInstance } from 'axios';

export interface LearningSource {
  repo_name: string;
  pr_number: number;
  pr_title?: string;
  file_path: string;
  author: string;
  reviewer?: string;
  timestamp?: string;
}

export interface ReviewComment {
  comment_id: string;
  raw_comment: string;
  code_snippet?: string;
  language?: string;
  feedback_type?: 'accepted' | 'rejected' | 'modified' | 'thanked' | 'debated' | 'ignored';
  source: LearningSource;
}

export interface IngestionRequest {
  comment: ReviewComment;
  async_processing?: boolean;
}

export interface IngestionResponse {
  task_id: string | null;
  status: 'queued' | 'success' | 'skipped' | 'failed';
  learning_id: string | null;
}

export interface Learning {
  learning_id: string;
  learning_text: string;
  original_comment: string;
  code_context?: string;
  language?: string;
  confidence_score: number;
  feedback_type?: string;
}

export interface LearningSearchResponse {
  learnings: Learning[];
  total: number;
  query: string;
}

export class KnowledgeBaseService {
  private client: AxiosInstance;
  private enabled: boolean;

  constructor(baseURL?: string) {
    const apiURL = baseURL || process.env.KNOWLEDGE_BASE_URL || 'http://localhost:8000';
    
    this.client = axios.create({
      baseURL: apiURL,
      timeout: 10000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // KB_ENABLED=true to enable, anything else (or missing) disables
    this.enabled = process.env.KB_ENABLED === 'true';
  }

  async healthCheck(): Promise<boolean> {
    if (!this.enabled) return false;
    
    try {
      const response = await this.client.get('/health');
      return response.status === 200;
    } catch (error) {
      console.warn('Knowledge base health check failed:', error);
      return false;
    }
  }

  async ingestReviewComment(
    commentData: {
      commentId: string;
      comment: string;
      codeSnippet?: string;
      language?: string;
      repoName: string;
      prNumber: number;
      prTitle?: string;
      filePath: string;
      author: string;
      feedbackType?: 'accepted' | 'rejected' | 'modified' | 'thanked' | 'debated' | 'ignored';
      userResponse?: string;
      reviewer?: string;
    }
  ): Promise<IngestionResponse | null> {
    if (!this.enabled) return null;

    try {
      // Format payload to match KB service's LearningRequest schema
      const learningText = commentData.userResponse 
        ? `[${commentData.feedbackType || 'feedback'}] ${commentData.comment} | User response: ${commentData.userResponse}`
        : `[review] ${commentData.comment}`;
      
      const payload = {
        learning: learningText,
        learnt_from: commentData.reviewer || commentData.author,
        pr: `${commentData.repoName}#${commentData.prNumber}`,
        file: commentData.filePath,
        timestamp: new Date().toISOString(),
      };

      const response = await this.client.post<{ status: string; message: string; task_id: string }>(
        '/learnings',
        payload
      );

      console.log(`Ingested comment to KB: ${response.data.status} (feedback: ${commentData.feedbackType || 'none'})`);
      return {
        task_id: response.data.task_id,
        status: response.data.status as 'queued' | 'success' | 'skipped' | 'failed',
        learning_id: response.data.task_id, // Use task_id as learning_id
      };
    } catch (error) {
      console.error('Failed to ingest comment to knowledge base:', error);
      return null;
    }
  }

  async batchIngestComments(
    comments: Array<{
      commentId: string;
      comment: string;
      codeSnippet?: string;
      language?: string;
      repoName: string;
      prNumber: number;
      prTitle?: string;
      filePath: string;
      author: string;
      feedbackType?: 'accepted' | 'rejected' | 'modified' | 'thanked' | 'debated' | 'ignored';
      reviewer?: string;
    }>
  ): Promise<{ task_id: string; status: string; total_comments: number } | null> {
    if (!this.enabled || comments.length === 0) return null;

    try {
      // Format payload to match KB service's batch LearningRequest schema
      const learnings = comments.map(c => ({
        learning: `[${c.feedbackType || 'review'}] ${c.comment}`,
        learnt_from: c.reviewer || c.author,
        pr: `${c.repoName}#${c.prNumber}`,
        file: c.filePath,
        timestamp: new Date().toISOString(),
      }));

      await this.client.post('/learnings/batch', learnings);
      console.log(`Batch ingested ${comments.length} comments to KB`);
      return {
        task_id: 'batch',
        status: 'queued',
        total_comments: comments.length,
      };
    } catch (error) {
      console.error('Failed to batch ingest comments:', error);
      return null;
    }
  }

  async searchLearnings(
    query: string,
    options?: {
      k?: number;
      repo?: string;
      language?: string;
      minConfidence?: number;
    }
  ): Promise<Learning[]> {
    if (!this.enabled) return [];

    try {
      const params = new URLSearchParams({
        q: query,
        k: (options?.k || 5).toString(),
        ...(options?.repo && { repo: options.repo }),
        ...(options?.language && { language: options.language }),
        ...(options?.minConfidence !== undefined && {
          min_confidence: options.minConfidence.toString(),
        }),
      });

      const response = await this.client.get<LearningSearchResponse>(
        `/learnings/search?${params}`
      );

      return response.data.learnings || [];
    } catch (error) {
      console.error('Failed to search learnings:', error);
      return [];
    }
  }

  async getPRContextLearnings(
    prDescription: string,
    changedFiles: string[],
    repoName: string,
    k: number = 5
  ): Promise<Learning[]> {
    if (!this.enabled) return [];

    try {
      const response = await this.client.post<Learning[]>('/learnings/pr-context', {
        pr_description: prDescription,
        changed_files: changedFiles,
        repo_name: repoName,
        k,
      });

      console.log(`Retrieved ${response.data.length} contextual learnings for PR`);
      return response.data;
    } catch (error) {
      console.error('Failed to get PR context learnings:', error);
      return [];
    }
  }

  formatLearningsForComment(learnings: Learning[]): string {
    if (learnings.length === 0) return '';

    let formatted = '\n\n---\n### 📚 Relevant Project Learnings\n\n';
    formatted += 'Based on past code reviews in this repository:\n\n';

    learnings.forEach((learning, index) => {
      formatted += `${index + 1}. **${learning.learning_text}**\n`;
      if (learning.confidence_score) {
        formatted += `   _Confidence: ${(learning.confidence_score * 100).toFixed(0)}%_\n`;
      }
      formatted += '\n';
    });

    return formatted;
  }
}

export const knowledgeBaseService = new KnowledgeBaseService();
