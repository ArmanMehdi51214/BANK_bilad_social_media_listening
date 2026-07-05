export type LoginResponse = {
  access_token: string;
  token_type: string;
};

export type CurrentUser = {
  id: string;
  email: string;
  full_name?: string | null;
  role?: string;
  is_active?: boolean;
};

export type AiSummary = {
  platform: string;
  total_posts: number;
  posts_with_clean_text: number;
  analyzed_posts: number;
  complaint_count: number;
  complaint_rate: number;
  sentiment_distribution: { sentiment_label: string; count: number }[];
  topic_distribution: { slug: string; name: string; count: number }[];
  entity_distribution: { entity_type: string; count: number }[];
  latest_analysis_at: string | null;
};

export type SchedulerStatus = {
  enabled: boolean;
  running: boolean;
  timezone: string;
  started_at: string | null;
  stopped_at: string | null;
  job_count: number;
  jobs: {
    id: string;
    name: string;
    next_run_time: string | null;
    trigger: string;
  }[];
  runtime_state?: Record<string, unknown>;
};

export type AiResultItem = {
  post: {
    id: string;
    platform: string;
    external_post_id: string;
    language: string | null;
    raw_text: string | null;
    clean_text: string | null;
    published_at: string | null;
    collected_at: string | null;
  };
  analysis: {
    sentiment_label: string | null;
    sentiment_score: number | null;
    sentiment_confidence: number | null;
    is_complaint: boolean | null;
    complaint_confidence: number | null;
  } | null;
  topics: { slug: string; name: string; confidence: number; is_primary: boolean }[];
  entities: { entity_type: string; value: string; confidence: number }[];
};

export type CollectionJob = {
  id: string;
  platform: string;
  job_type: string;
  status: string;
  query_value: string;
  started_at: string | null;
  finished_at: string | null;
  total_fetched: number;
  total_inserted: number;
  total_duplicates: number;
  total_errors: number;
  error_message: string | null;
};

export type PaginatedResponse<T> = {
  total: number;
  limit: number;
  offset: number;
  items: T[];
};
