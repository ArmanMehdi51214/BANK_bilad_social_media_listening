import { getAccessToken, setAccessToken } from "@/lib/auth";
import type { AiResultItem, AiSummary, CollectionJob, CurrentUser, LoginResponse, PaginatedResponse, SchedulerStatus } from "@/types/api";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000/api/v1";

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

type ApiOptions = RequestInit & {
  auth?: boolean;
};

export async function apiRequest<T>(
  path: string,
  options: ApiOptions = {}
): Promise<T> {
  const token = getAccessToken();

  const headers = new Headers(options.headers);

  if (!(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (options.auth !== false && token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  const text = await response.text();
  const data = text ? JSON.parse(text) : null;

  if (!response.ok) {
    const message =
      typeof data?.detail === "string"
        ? data.detail
        : `API request failed with status ${response.status}`;

    throw new ApiError(message, response.status, data);
  }

  return data as T;
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  const response = await apiRequest<LoginResponse>("/auth/login", {
    method: "POST",
    auth: false,
    body: JSON.stringify({ email, password }),
  });

  setAccessToken(response.access_token);
  return response;
}

export async function getCurrentUser(): Promise<CurrentUser> {
  return apiRequest<CurrentUser>("/auth/me");
}

export async function getAiSummary(): Promise<AiSummary> {
  return apiRequest<AiSummary>("/ai/summary");
}

export async function getSchedulerStatus(): Promise<SchedulerStatus> {
  return apiRequest<SchedulerStatus>("/scheduler/status");
}

export async function runSchedulerNow() {
  return apiRequest("/scheduler/run-now", {
    method: "POST",
  });
}

export async function getAiResults(params = "limit=5"): Promise<PaginatedResponse<AiResultItem>> {
  return apiRequest<PaginatedResponse<AiResultItem>>(`/ai/results?${params}`);
}

export async function getCollectionJobs(params = "limit=5"): Promise<PaginatedResponse<CollectionJob>> {
  return apiRequest<PaginatedResponse<CollectionJob>>(`/collection/jobs?${params}`);
}

