import { useQuery, useMutation, useQueryClient, useInfiniteQuery } from "@tanstack/react-query";
import {
  getSources,
  createSource,
  deleteSource,
  getRawPosts,
  reviewPost,
  getProcessedPosts,
  getFullPost,
  scrapeNow,
  processAll,
  checkHealth,
  getSchedulerStatus,
  getScrapingStatus,
  reimaginePost,
} from "./api";
import type { SourceCreate } from "@/types/source";

const PAGE_SIZE = 12;

// ── Health ────────────────────────────────────────────────────────────────────

export function useBackendHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: checkHealth,
    refetchInterval: 30_000,   // poll every 30 s
    retry: 1,
    retryDelay: 2000,
  });
}

// ── Sources ───────────────────────────────────────────────────────────────────

export function useSources() {
  return useQuery({ queryKey: ["sources"], queryFn: getSources });
}

export function useCreateSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: SourceCreate) => createSource(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sources"] }),
  });
}

export function useDeleteSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteSource(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sources"] });
      qc.invalidateQueries({ queryKey: ["posts"] });
    },
  });
}

export function useSchedulerStatus() {
  return useQuery({
    queryKey: ["scheduler", "status"],
    queryFn: getSchedulerStatus,
    refetchInterval: 60_000,
    retry: 1,
  });
}

export function useScrapingStatus(enabled: boolean) {
  return useQuery({
    queryKey: ["scraping", "status"],
    queryFn: getScrapingStatus,
    // Poll aggressively only while we believe scraping is active
    refetchInterval: enabled ? 3_000 : false,
    retry: 0,
  });
}

export function usePendingCount(sourceId?: number) {
  return useQuery({
    queryKey: ["posts", "pendingCount", sourceId],
    queryFn: () => getRawPosts({ approval_status: "pending_review", source_id: sourceId, limit: 1, offset: 0 }),
    select: (data) => data.length > 0,  // true = has pending posts
    enabled: sourceId !== undefined,
    staleTime: 10_000,
  });
}

// ── Review queue ──────────────────────────────────────────────────────────────

export function usePendingPosts(sourceId?: number) {
  return useInfiniteQuery({
    queryKey: ["posts", "pending", sourceId],
    queryFn: ({ pageParam = 0 }) =>
      getRawPosts({
        approval_status: "pending_review",
        source_id: sourceId,
        offset: pageParam as number,
        limit: PAGE_SIZE,
      }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) =>
      lastPage.length === PAGE_SIZE ? allPages.length * PAGE_SIZE : undefined,
  });
}

export function useReviewPost() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action }: { id: number; action: "approve" | "reject" }) =>
      reviewPost(id, action),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["posts", "pending"] });
      qc.invalidateQueries({ queryKey: ["posts", "processed"] });
    },
  });
}

// ── Processed posts ───────────────────────────────────────────────────────────

export function useProcessedPosts(sourceId?: number) {
  return useInfiniteQuery({
    queryKey: ["posts", "processed", sourceId],
    queryFn: ({ pageParam = 0 }) =>
      getProcessedPosts({
        source_id: sourceId,
        offset: pageParam as number,
        limit: PAGE_SIZE,
      }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) =>
      lastPage.length === PAGE_SIZE ? allPages.length * PAGE_SIZE : undefined,
  });
}

export function useFullPost(id: number | null) {
  return useQuery({
    queryKey: ["post", id],
    queryFn: () => getFullPost(id!),
    enabled: id !== null,
  });
}

// ── Actions ───────────────────────────────────────────────────────────────────

export function useScrapeNow() {
  return useMutation({
    mutationFn: (sourceId?: number) => scrapeNow(sourceId),
    // Don't invalidate posts here — scraping is async in the backend.
    // Topbar polls /scraping/status and invalidates when it detects completion.
  });
}

export function useProcessAll() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => processAll(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["posts"] }),
  });
}

export function useReimaginePost() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (processedPostId: number) => reimaginePost(processedPostId),
    onSuccess: () => {
      // Refresh the processed list so reimagine_status shows "generating"
      qc.invalidateQueries({ queryKey: ["posts", "processed"] });
      // Also refresh any open full-post drawer so it picks up the new status immediately
      qc.invalidateQueries({ queryKey: ["post"] });
    },
  });
}
