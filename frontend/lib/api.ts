import axios from "axios";
import type { Source, SourceCreate } from "@/types/source";
import type { ScrapedPost, ProcessedPost, FullPost } from "@/types/post";

export const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1",
  headers: { "Content-Type": "application/json" },
});

// ── Sources ──────────────────────────────────────────────────────────────────

export async function getSources(): Promise<Source[]> {
  const { data } = await apiClient.get<Source[]>("/sources");
  return data;
}

export async function createSource(payload: SourceCreate): Promise<Source> {
  const { data } = await apiClient.post<Source>("/sources", payload);
  return data;
}

export async function deleteSource(id: number): Promise<void> {
  await apiClient.delete(`/sources/${id}`);
}

export async function getSchedulerStatus(): Promise<{
  jobs: { id: string; name: string; next_run: string | null; last_run: string | null }[];
}> {
  const { data } = await apiClient.get("/scheduler/status");
  return data;
}

// ── Scraped posts ─────────────────────────────────────────────────────────────

export async function getRawPosts(params?: {
  source_id?: number;
  approval_status?: string;
  offset?: number;
  limit?: number;
}): Promise<ScrapedPost[]> {
  const { data } = await apiClient.get<ScrapedPost[]>("/posts/raw", { params });
  return data;
}

export async function reviewPost(
  id: number,
  action: "approve" | "reject"
): Promise<void> {
  await apiClient.patch(`/posts/raw/${id}/review`, { action });
}

// ── Processed posts ───────────────────────────────────────────────────────────

export async function getProcessedPosts(params?: {
  source_id?: number;
  offset?: number;
  limit?: number;
}): Promise<ProcessedPost[]> {
  const { data } = await apiClient.get<ProcessedPost[]>("/posts/processed", { params });
  return data;
}

export async function getFullPost(id: number): Promise<FullPost> {
  const { data } = await apiClient.get<FullPost>(`/posts/${id}`);
  return data;
}

// ── Actions ───────────────────────────────────────────────────────────────────

export async function scrapeNow(sourceId?: number): Promise<{ message: string }> {
  const { data } = await apiClient.post("/scrape-now", sourceId ? { source_id: sourceId } : {});
  return data;
}

export async function processAll(): Promise<{ triggered: number; message: string }> {
  const { data } = await apiClient.post("/process-all");
  return data;
}

// ── Health ────────────────────────────────────────────────────────────────────

export async function checkHealth(): Promise<boolean> {
  await apiClient.get("/health", { timeout: 5000 });
  return true;
}
