"use client";

import { useState, useRef, useCallback } from "react";
import { toast } from "sonner";
import { Check, X, ExternalLink, ImageOff, Loader2, ClipboardList } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import Topbar from "@/components/Topbar";
import { usePendingPosts, useReviewPost, useSources } from "@/lib/hooks";
import { formatDate, truncate } from "@/lib/utils";
import type { ScrapedPost } from "@/types/post";

export default function ReviewPage() {
  const [activeSourceId, setActiveSourceId] = useState<number | undefined>();
  const [acting, setActing] = useState<Record<number, "approve" | "reject">>();

  const { data: sources } = useSources();
  const activeSource = sources?.find((s) => s.id === activeSourceId);

  const { data, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage, refetch } =
    usePendingPosts(activeSourceId);

  const reviewMutation = useReviewPost();

  const allPosts = data?.pages.flatMap((p) => p) ?? [];

  const observer = useRef<IntersectionObserver | null>(null);
  const sentinelRef = useCallback(
    (node: HTMLDivElement | null) => {
      if (isFetchingNextPage) return;
      if (observer.current) observer.current.disconnect();
      observer.current = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting && hasNextPage) fetchNextPage();
      });
      if (node) observer.current.observe(node);
    },
    [isFetchingNextPage, hasNextPage, fetchNextPage]
  );

  async function handleAction(post: ScrapedPost, action: "approve" | "reject") {
    setActing((prev) => ({ ...prev, [post.id]: action }));
    try {
      await reviewMutation.mutateAsync({ id: post.id, action });
      toast.success(action === "approve" ? "Post approved — AI processing started" : "Post rejected");
      refetch();
    } catch {
      toast.error(`Failed to ${action} post`);
    } finally {
      setActing((prev) => {
        const next = { ...prev };
        delete next?.[post.id];
        return next;
      });
    }
  }

  const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar activeSourceId={activeSourceId} onSourceSelect={setActiveSourceId} />

      <div className="flex-1 flex flex-col min-w-0">
        <Topbar
          title={activeSource ? activeSource.label ?? "Review Queue" : "Review Queue"}
          activeSourceId={activeSourceId}
          activeSourceLabel={activeSource?.label ?? undefined}
          onSourceDeselect={() => setActiveSourceId(undefined)}
        />

        <main className="flex-1 overflow-y-auto p-6">
          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <ReviewCardSkeleton key={i} />
              ))}
            </div>
          ) : allPosts.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 text-center">
              <ClipboardList size={36} className="text-zinc-700 mb-3" />
              <p className="text-sm font-medium text-zinc-400">Queue is clear</p>
              <p className="text-xs text-zinc-600 mt-1">
                No posts pending review. Scrape a source to populate the queue.
              </p>
            </div>
          ) : (
            <>
              <p className="text-xs text-zinc-600 mb-4">
                {allPosts.length} post{allPosts.length !== 1 ? "s" : ""} pending review
              </p>

              <div className="space-y-3">
                {allPosts.map((post) => {
                  const isActing = acting?.[post.id];
                  const imgPath = post.image_url;
                  const imgSrc = imgPath
                    ? imgPath.startsWith("http")
                      ? imgPath
                      : `${API_BASE}/images/${imgPath.split("/").pop()}`
                    : null;

                  return (
                    <div
                      key={post.id}
                      className="flex gap-4 bg-zinc-900 border border-zinc-800 rounded-xl p-4 hover:border-zinc-700 transition-colors"
                    >
                      {/* Image thumbnail */}
                      <div className="w-24 h-24 shrink-0 rounded-lg overflow-hidden bg-zinc-800 flex items-center justify-center">
                        {imgSrc ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={imgSrc}
                            alt=""
                            className="w-full h-full object-cover"
                            onError={(e) => ((e.target as HTMLImageElement).style.display = "none")}
                          />
                        ) : (
                          <ImageOff size={20} className="text-zinc-700" />
                        )}
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0 flex flex-col gap-1.5">
                        <p className="text-sm text-zinc-300 leading-relaxed line-clamp-3">
                          {truncate(post.post_text, 280) || (
                            <span className="text-zinc-600 italic">Image-only post (no text)</span>
                          )}
                        </p>

                        <div className="flex items-center gap-3 mt-auto">
                          {post.timestamp && (
                            <span className="text-[11px] text-zinc-600">
                              {formatDate(post.timestamp)}
                            </span>
                          )}
                          <a
                            href={post.post_link}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-1 text-[11px] text-zinc-600 hover:text-violet-400 transition-colors"
                          >
                            <ExternalLink size={10} />
                            View on LinkedIn
                          </a>
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex flex-col gap-2 shrink-0 justify-center">
                        <button
                          onClick={() => handleAction(post, "approve")}
                          disabled={!!isActing}
                          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-emerald-950 border border-emerald-800 text-emerald-400 hover:bg-emerald-900 hover:text-emerald-300 transition-colors disabled:opacity-50"
                        >
                          {isActing === "approve" ? (
                            <Loader2 size={12} className="animate-spin" />
                          ) : (
                            <Check size={12} />
                          )}
                          Approve
                        </button>
                        <button
                          onClick={() => handleAction(post, "reject")}
                          disabled={!!isActing}
                          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-zinc-900 border border-zinc-800 text-zinc-400 hover:bg-red-950 hover:border-red-900 hover:text-red-400 transition-colors disabled:opacity-50"
                        >
                          {isActing === "reject" ? (
                            <Loader2 size={12} className="animate-spin" />
                          ) : (
                            <X size={12} />
                          )}
                          Reject
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>

              <div ref={sentinelRef} className="h-8 mt-4 flex items-center justify-center">
                {isFetchingNextPage && (
                  <p className="text-xs text-zinc-600 animate-pulse">Loading more…</p>
                )}
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
}

function ReviewCardSkeleton() {
  return (
    <div className="flex gap-4 bg-zinc-900 border border-zinc-800 rounded-xl p-4 animate-pulse">
      <div className="w-24 h-24 shrink-0 rounded-lg bg-zinc-800" />
      <div className="flex-1 space-y-2">
        <div className="h-3 bg-zinc-800 rounded w-full" />
        <div className="h-3 bg-zinc-800 rounded w-5/6" />
        <div className="h-3 bg-zinc-800 rounded w-4/6" />
        <div className="h-3 bg-zinc-800 rounded w-24 mt-2" />
      </div>
      <div className="flex flex-col gap-2 justify-center">
        <div className="h-7 w-20 bg-zinc-800 rounded-md" />
        <div className="h-7 w-20 bg-zinc-800 rounded-md" />
      </div>
    </div>
  );
}
