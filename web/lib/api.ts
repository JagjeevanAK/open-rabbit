const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

interface ApiResponse<T> {
    data?: T;
    error?: string;
    status: string;
}

interface User {
    name: string;
    email: string;
    org: string;
    sub: boolean;
}

interface SignupData {
    name: string;
    email: string;
    org: string;
    sub?: boolean;
}

interface SigninData {
    name: string;
    email: string;
    org: string;
    sub?: boolean;
}

interface ReviewTask {
    task_id: string;
    status: string;
    created_at: string;
    completed_at?: string;
    result?: Record<string, unknown>;
}

interface ReviewsListResponse {
    total: number;
    tasks: ReviewTask[];
}

class ApiClient {
    private baseUrl: string;

    constructor(baseUrl: string = API_BASE_URL) {
        this.baseUrl = baseUrl;
    }

    private async request<T>(
        endpoint: string,
        options: RequestInit = {}
    ): Promise<ApiResponse<T>> {
        try {
            const url = `${this.baseUrl}${endpoint}`;
            const response = await fetch(url, {
                ...options,
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers,
                },
            });

            const data = await response.json();

            if (!response.ok) {
                return {
                    status: 'error',
                    error: data.detail || data.message || 'An error occurred',
                };
            }

            return {
                status: 'success',
                data,
            };
        } catch (error) {
            return {
                status: 'error',
                error: error instanceof Error ? error.message : 'Network error',
            };
        }
    }

    // Auth endpoints
    async signup(userData: SignupData): Promise<ApiResponse<User>> {
        return this.request<User>('/users/signup', {
            method: 'POST',
            body: JSON.stringify({ ...userData, sub: userData.sub ?? false }),
        });
    }

    async signin(userData: SigninData): Promise<ApiResponse<{ status: string }>> {
        return this.request<{ status: string }>('/users/signin', {
            method: 'POST',
            body: JSON.stringify({ ...userData, sub: userData.sub ?? false }),
        });
    }

    async checkOwner(ownerName: string): Promise<ApiResponse<{ owner: string; authorized: boolean }>> {
        return this.request<{ owner: string; authorized: boolean }>(`/users/check-owner/${ownerName}`);
    }

    // Review endpoints
    async getReviewTasks(): Promise<ApiResponse<ReviewsListResponse>> {
        return this.request<ReviewsListResponse>('/feedback/review/tasks');
    }

    async getReviewStatus(taskId: string): Promise<ApiResponse<ReviewTask>> {
        return this.request<ReviewTask>(`/feedback/review/status/${taskId}`);
    }

    async getReviewResult(taskId: string): Promise<ApiResponse<Record<string, unknown>>> {
        return this.request<Record<string, unknown>>(`/feedback/review/result/${taskId}`);
    }
}

export const api = new ApiClient();
export type { User, SignupData, SigninData, ReviewTask, ReviewsListResponse, ApiResponse };
