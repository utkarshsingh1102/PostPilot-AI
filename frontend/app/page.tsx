"use client";

import { useState, useRef, useCallback, useMemo } from "react";
import Sidebar from "@/components/Sidebar";
import Topbar from "@/components/Topbar";
import PostCard, { PostCardSkeleton } from "@/components/PostCard";
import PostDetailDrawer from "@/components/PostDetailDrawer";
import { useProcessedPosts, useSources } from "@/lib/hooks";
import { LayoutDashboard } from "lucide-react";
import type { ProcessedPost } from "@/types/post";

export default function DashboardPage() {
  const [activeSourceId, setActiveSourceId] = useState<number | undefined>();
  const [drawerPostId, setDrawerPostId] = useState<number | null>(null);

  const { data: sources } = useSources();
  const activeSource = sources?.find((s) => s.id === activeSourceId);

  const { data, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useProcessedPosts(activeSourceId);

  const allPosts = data?.pages.flatMap((p) => p) ?? [];

  // Group posts by source when no source filter is active
  const groupedPosts = useMemo(() => {
    if (activeSourceId) return null; // flat view when filtered
    const map = new Map<string, { label: string; posts: ProcessedPost[] }>();
    for (const post of allPosts) {
      const key = post.source_label ?? `Source ${post.source_id ?? "?"}`;
      if (!map.has(key)) map.set(key, { label: key, posts: [] });
      map.get(key)!.posts.push(post);
    }
    return Array.from(map.values());
  }, [allPosts, activeSourceId]);

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

  function openDrawer(scraped_post_id: number | null) {
    if (scraped_post_id !== null) setDrawerPostId(scraped_post_id);
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar activeSourceId={activeSourceId} onSourceSelect={setActiveSourceId} />

      <div className="flex-1 flex flex-col min-w-0">
        <Topbar
          title={activeSource ? activeSource.label ?? activeSource.linkedin_url : "Dashboard"}
          activeSourceId={activeSourceId}
          activeSourceLabel={activeSource?.label ?? undefined}
          onSourceDeselect={() => setActiveSourceId(undefined)}
        />

        <main className="flex-1 overflow-y-auto p-6">
          {isLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <PostCardSkeleton key={i} />
              ))}
            </div>
          ) : allPosts.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 text-center">
              <LayoutDashboard size={36} className="text-zinc-700 mb-3" />
              <p className="text-sm font-medium text-zinc-400">No processed posts yet</p>
              <p className="text-xs text-zinc-600 mt-1">
                Add a source, scrape, and approve posts to see them here.
              </p>
            </div>
          ) : activeSourceId || !groupedPosts ? (
            // Flat view for single source
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                {allPosts.map((post) => (
                  <PostCard key={post.id} post={post} onOpen={openDrawer} />
                ))}
              </div>
              <div ref={sentinelRef} className="h-8 mt-4 flex items-center justify-center">
                {isFetchingNextPage && (
                  <p className="text-xs text-zinc-600 animate-pulse">Loading more…</p>
                )}
              </div>
            </>
          ) : (
            // Grouped view — one section per source
            <>
              {groupedPosts.map((group) => (
                <section key={group.label} className="mb-8">
                  <div className="flex items-center gap-2 mb-4">
                    <div className="w-2 h-2 rounded-full bg-violet-500" />
                    <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-widest">
                      {group.label}
                    </h2>
                    <span className="text-xs text-zinc-600">({group.posts.length})</span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                    {group.posts.map((post) => (
                      <PostCard key={post.id} post={post} onOpen={openDrawer} />
                    ))}
                  </div>
                </section>
              ))}
              <div ref={sentinelRef} className="h-8 mt-4" />
            </>
          )}
        </main>
      </div>

      <PostDetailDrawer postId={drawerPostId} onClose={() => setDrawerPostId(null)} />
    </div>
  );
}
