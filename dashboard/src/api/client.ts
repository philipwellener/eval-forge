const BASE = "/api/v1";

export interface Run {
  id: string;
  policy_id: string;
  environment: string;
  num_runs: number;
  config: Record<string, unknown> | null;
  status: "pending" | "running" | "completed" | "failed";
  success_rate: number | null;
  avg_completion_time: number | null;
  submitted_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface EpisodeResult {
  id: string;
  run_id: string;
  episode_index: number;
  success: number;
  steps: number;
  wall_clock_time: number;
  inference_latency: number | null;
  peak_memory_mb: number | null;
  extra_metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface RunFilters {
  environment?: string;
  status?: string;
}

export interface CompareData {
  runs: Run[];
  results: Record<string, EpisodeResult[]>;
}

async function request<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${await res.text()}`);
  }
  return res.json();
}

export async function fetchRuns(filters?: RunFilters): Promise<Run[]> {
  const params = new URLSearchParams();
  if (filters?.environment) params.set("environment", filters.environment);
  if (filters?.status) params.set("status", filters.status);
  const qs = params.toString();
  return request<Run[]>(`/evaluations${qs ? `?${qs}` : ""}`);
}

export async function fetchRun(id: string): Promise<Run> {
  return request<Run>(`/evaluations/${id}`);
}

export async function fetchResults(runId: string): Promise<EpisodeResult[]> {
  return request<EpisodeResult[]>(`/evaluations/${runId}/results`);
}

export async function fetchCompare(runIds: string[]): Promise<CompareData> {
  const params = new URLSearchParams();
  runIds.forEach((id) => params.append("run_id", id));
  return request<CompareData>(`/compare?${params.toString()}`);
}
