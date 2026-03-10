"use client";

import {
  X, ExternalLink, Copy, Download, ImageOff, Loader2, CheckCheck,
  AlertCircle, Sparkles, ChevronLeft, ChevronRight,
} from "lucide-react";
import { useState, useEffect, useRef } from "react";
import { toast } from "sonner";
import { useFullPost, useReimaginePost } from "@/lib/hooks";
import { cn, formatDate } from "@/lib/utils";

interface PostDetailDrawerProps {
  postId: number | null;
  onClose: () => void;
}

export default function PostDetailDrawer({ postId, onClose }: PostDetailDrawerProps) {
  const { data: post, isLoading, refetch, dataUpdatedAt } = useFullPost(postId);
  const reimagine = useReimaginePost();
  const [copied, setCopied] = useState(false);
  const [imageIndex, setImageIndex] = useState(0);
  // Local optimistic flag so the button disables instantly
  const [localReimaging, setLocalReimaging] = useState(false);
  // Track when reimagine was triggered — used to detect fresh data even when
  // reimagine_status goes idle→idle (fast completion / Gemini skip).
  const reimagineStartedRef = useRef<number | null>(null);
  // Stable ref to refetch so the polling interval doesn't recreate on each render.
  const refetchRef = useRef(refetch);
  useEffect(() => { refetchRef.current = refetch; }, [refetch]);

  const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

  // All image versions; fall back to single generated_image_url for old posts
  const allImages: string[] = post?.image_versions?.length
    ? post.image_versions.map((v) => v.image_path)
    : post?.generated_image_url
    ? [post.generated_image_url]
    : [];

  // Reset everything when a new post is opened.
  // We also zero the ref so the "jump to latest" effect fires correctly when data loads.
  const prevCountRef = useRef(0);
  useEffect(() => {
    setImageIndex(0);
    setLocalReimaging(false);
    reimagineStartedRef.current = null;
    prevCountRef.current = 0;
  }, [postId]);

  // Auto-jump to the newest image whenever the version list grows
  // (covers both initial load and incoming reimagine results).
  useEffect(() => {
    if (allImages.length > prevCountRef.current) {
      setImageIndex(allImages.length - 1);
    }
    prevCountRef.current = allImages.length;
  }, [allImages.length]);

  // Poll while reimagining so the new image appears automatically.
  // Uses a ref for refetch so the interval isn't recreated when refetch changes.
  const isReimaging = localReimaging || post?.reimagine_status === "generating";
  useEffect(() => {
    if (!isReimaging) return;
    refetchRef.current(); // fetch immediately — don't wait 2 s for first update
    const id = setInterval(() => refetchRef.current(), 2000);
    return () => clearInterval(id);
  }, [isReimaging]);

  // Clear local flag when fresh data arrives with status=idle.
  // Uses dataUpdatedAt (TanStack Query's fetch timestamp) so the effect fires
  // even when reimagine_status stays "idle"→"idle" (fast completion / Gemini skip).
  useEffect(() => {
    if (
      reimagineStartedRef.current !== null &&
      post?.reimagine_status === "idle" &&
      dataUpdatedAt > reimagineStartedRef.current
    ) {
      reimagineStartedRef.current = null;
      setLocalReimaging(false);
    }
  }, [dataUpdatedAt, post?.reimagine_status]);

  function imageUrl(path: string | null | undefined) {
    if (!path) return null;
    if (path.startsWith("http")) return path;
    const filename = path.split("/").pop();
    return `${API_BASE}/images/${filename}`;
  }

  async function handleCopy() {
    if (!post?.copy_ready_text) return;
    await navigator.clipboard.writeText(post.copy_ready_text);
    setCopied(true);
    toast.success("Copied to clipboard");
    setTimeout(() => setCopied(false), 2000);
  }

  function handleDownload() {
    const currentPath = allImages[imageIndex] ?? post?.generated_image_url;
    const url = imageUrl(currentPath);
    if (!url) return;
    const a = document.createElement("a");
    a.href = url;
    a.download = url.split("/").pop() ?? "image";
    a.click();
  }

  async function handleReimagine() {
    if (!post?.processed_post_id) return;
    setLocalReimaging(true);
    reimagineStartedRef.current = Date.now();
    try {
      await reimagine.mutateAsync(post.processed_post_id);
      toast.success("Reimagining… new image will appear shortly");
    } catch {
      reimagineStartedRef.current = null;
      setLocalReimaging(false);
      toast.error("Reimagine failed");
    }
  }

  const open = postId !== null;
  const currentImagePath = allImages[imageIndex] ?? null;
  const currentImageSrc = imageUrl(currentImagePath);

  return (
    <>
      {/* Backdrop */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
          onClick={onClose}
        />
      )}

      {/* Drawer */}
      <div
        className={cn(
          "fixed top-0 right-0 z-50 h-full w-full max-w-3xl bg-zinc-950 border-l border-zinc-800 shadow-2xl transition-transform duration-300 ease-in-out overflow-y-auto",
          open ? "translate-x-0" : "translate-x-full"
        )}
      >
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-center justify-between px-6 py-4 bg-zinc-950 border-b border-zinc-800">
          <h2 className="text-sm font-semibold text-zinc-100">Post Detail</h2>
          <div className="flex items-center gap-2">
            {post?.post_link && (
              <a
                href={post.post_link}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-zinc-800 text-zinc-300 hover:bg-zinc-700 hover:text-zinc-100 transition-colors"
              >
                <ExternalLink size={12} />
                View Original
              </a>
            )}
            <button
              onClick={onClose}
              className="p-1.5 text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900 rounded-md transition-colors"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Body */}
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 size={24} className="animate-spin text-zinc-600" />
          </div>
        ) : post ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-0 divide-y md:divide-y-0 md:divide-x divide-zinc-800">
            {/* Left – Original */}
            <div className="p-6 space-y-4">
              <div>
                <p className="text-[11px] font-semibold tracking-widest text-zinc-600 uppercase mb-3">
                  Original Post
                </p>
                {post.original_image_url && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={imageUrl(post.original_image_url) ?? ""}
                    alt="Original"
                    className="w-full rounded-lg object-cover mb-4 border border-zinc-800"
                    onError={(e) => ((e.target as HTMLImageElement).style.display = "none")}
                  />
                )}
                <p className="text-sm text-zinc-400 leading-relaxed whitespace-pre-line">
                  {post.original_text ?? (
                    <span className="text-zinc-600 italic">No original text available</span>
                  )}
                </p>
              </div>

              {post.post_timestamp && (
                <p className="text-xs text-zinc-600">
                  Posted: {formatDate(post.post_timestamp)}
                </p>
              )}
            </div>

            {/* Right – AI rewritten */}
            <div className="p-6 space-y-4">
              <div className="flex items-center justify-between mb-3">
                <p className="text-[11px] font-semibold tracking-widest text-zinc-600 uppercase">
                  AI Rewritten
                </p>
                <div className="flex items-center gap-1.5">
                  {post.status === "completed" && (
                    <>
                      {/* Reimagine button */}
                      {post.generated_image_url && (
                        <button
                          onClick={handleReimagine}
                          disabled={isReimaging}
                          className={cn(
                            "flex items-center gap-1 px-2.5 py-1 text-xs rounded-md transition-colors disabled:opacity-40 disabled:cursor-not-allowed",
                            isReimaging
                              ? "bg-violet-950/60 border border-violet-800/60 text-violet-400"
                              : "bg-zinc-800 text-zinc-300 hover:bg-violet-900/40 hover:text-violet-300 hover:border-violet-800 border border-transparent"
                          )}
                        >
                          {isReimaging ? (
                            <Loader2 size={12} className="animate-spin" />
                          ) : (
                            <Sparkles size={12} />
                          )}
                          {isReimaging ? "Generating…" : "Reimagine"}
                        </button>
                      )}
                      <button
                        onClick={handleCopy}
                        disabled={!post.copy_ready_text}
                        className="flex items-center gap-1 px-2.5 py-1 text-xs rounded-md bg-zinc-800 text-zinc-300 hover:bg-zinc-700 transition-colors disabled:opacity-40"
                      >
                        {copied ? <CheckCheck size={12} className="text-green-400" /> : <Copy size={12} />}
                        Copy
                      </button>
                      {currentImageSrc && (
                        <button
                          onClick={handleDownload}
                          className="flex items-center gap-1 px-2.5 py-1 text-xs rounded-md bg-zinc-800 text-zinc-300 hover:bg-zinc-700 transition-colors"
                        >
                          <Download size={12} />
                          Image
                        </button>
                      )}
                    </>
                  )}
                </div>
              </div>

              {/* Status */}
              {post.status === "failed" && (
                <div className="flex items-start gap-2 p-3 rounded-lg bg-red-950/40 border border-red-900/50">
                  <AlertCircle size={14} className="text-red-400 mt-0.5 shrink-0" />
                  <div>
                    <p className="text-xs font-medium text-red-400">Processing failed</p>
                    <p className="text-xs text-red-500/70 mt-0.5">{post.status}</p>
                  </div>
                </div>
              )}

              {post.status === "processing" || post.status === "pending" ? (
                <div className="flex items-center gap-2 text-sm text-amber-400">
                  <Loader2 size={14} className="animate-spin" />
                  AI is processing this post…
                </div>
              ) : (
                <>
                  {/* ── Image Carousel ── */}
                  <div className="relative">
                    {/* Image or placeholder */}
                    {currentImageSrc ? (
                      <div className="relative">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={currentImageSrc}
                          alt={`Version ${imageIndex + 1}`}
                          className="w-full rounded-lg object-cover border border-zinc-800"
                          onError={(e) => ((e.target as HTMLImageElement).style.display = "none")}
                        />
                        {/* Reimagining overlay */}
                        {isReimaging && (
                          <div className="absolute inset-0 rounded-lg bg-black/60 flex flex-col items-center justify-center gap-2">
                            <Loader2 size={20} className="animate-spin text-violet-400" />
                            <span className="text-xs text-violet-300 font-medium">Generating new version…</span>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="aspect-video bg-zinc-900 border border-zinc-800 rounded-lg flex items-center justify-center text-zinc-700">
                        <ImageOff size={24} />
                      </div>
                    )}

                    {/* Carousel navigation — only shown when there are multiple versions */}
                    {allImages.length > 1 && (
                      <>
                        <button
                          onClick={() => setImageIndex((i) => Math.max(0, i - 1))}
                          disabled={imageIndex === 0}
                          className="absolute left-2 top-1/2 -translate-y-1/2 p-1 rounded-full bg-black/60 text-white hover:bg-black/80 transition-colors disabled:opacity-20 disabled:cursor-not-allowed"
                        >
                          <ChevronLeft size={16} />
                        </button>
                        <button
                          onClick={() => setImageIndex((i) => Math.min(allImages.length - 1, i + 1))}
                          disabled={imageIndex === allImages.length - 1}
                          className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded-full bg-black/60 text-white hover:bg-black/80 transition-colors disabled:opacity-20 disabled:cursor-not-allowed"
                        >
                          <ChevronRight size={16} />
                        </button>
                      </>
                    )}
                  </div>

                  {/* Version indicator + dots */}
                  {allImages.length > 1 && (
                    <div className="flex flex-col items-center gap-2">
                      <div className="flex items-center gap-1.5">
                        {allImages.map((_, i) => (
                          <button
                            key={i}
                            onClick={() => setImageIndex(i)}
                            className={cn(
                              "rounded-full transition-all",
                              i === imageIndex
                                ? "w-4 h-1.5 bg-violet-500"
                                : "w-1.5 h-1.5 bg-zinc-600 hover:bg-zinc-400"
                            )}
                          />
                        ))}
                      </div>
                      <p className="text-[10px] text-zinc-600">
                        Version {imageIndex + 1} of {allImages.length}
                        {imageIndex === allImages.length - 1 && allImages.length > 1 && (
                          <span className="ml-1.5 text-violet-500">• Latest</span>
                        )}
                      </p>
                    </div>
                  )}

                  {/* Hook */}
                  {post.hooks && (
                    <div className="p-3 rounded-lg bg-violet-950/30 border border-violet-900/40">
                      <p className="text-[10px] font-semibold text-violet-500 uppercase tracking-widest mb-1.5">
                        Hook
                      </p>
                      <p className="text-sm text-violet-300 leading-relaxed">{post.hooks}</p>
                    </div>
                  )}

                  {/* Rewritten post */}
                  <p className="text-sm text-zinc-300 leading-relaxed whitespace-pre-line">
                    {post.rewritten_post ?? (
                      <span className="text-zinc-600 italic">Not yet generated</span>
                    )}
                  </p>

                  {/* Hashtags */}
                  {post.hashtags && post.hashtags.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {post.hashtags.map((tag) => (
                        <span
                          key={tag}
                          className="px-2.5 py-1 text-xs rounded-full bg-zinc-800 text-zinc-400"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        ) : null}
      </div>
    </>
  );
}
