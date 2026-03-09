"use client";

import { X, ExternalLink, Copy, Download, ImageOff, Loader2, CheckCheck, AlertCircle } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { useFullPost } from "@/lib/hooks";
import { cn, formatDate } from "@/lib/utils";

interface PostDetailDrawerProps {
  postId: number | null;
  onClose: () => void;
}

export default function PostDetailDrawer({ postId, onClose }: PostDetailDrawerProps) {
  const { data: post, isLoading } = useFullPost(postId);
  const [copied, setCopied] = useState(false);

  const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

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
    const url = post?.download_image_url ?? imageUrl(post?.generated_image_url);
    if (!url) return;
    const a = document.createElement("a");
    a.href = url;
    a.download = url.split("/").pop() ?? "image";
    a.click();
  }

  const open = postId !== null;

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
                      <button
                        onClick={handleCopy}
                        disabled={!post.copy_ready_text}
                        className="flex items-center gap-1 px-2.5 py-1 text-xs rounded-md bg-zinc-800 text-zinc-300 hover:bg-zinc-700 transition-colors disabled:opacity-40"
                      >
                        {copied ? <CheckCheck size={12} className="text-green-400" /> : <Copy size={12} />}
                        Copy
                      </button>
                      {(post.download_image_url ?? post.generated_image_url) && (
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
                  {/* Generated image */}
                  {post.generated_image_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={imageUrl(post.generated_image_url) ?? ""}
                      alt="Generated"
                      className="w-full rounded-lg object-cover border border-zinc-800"
                      onError={(e) => ((e.target as HTMLImageElement).style.display = "none")}
                    />
                  ) : (
                    <div className="aspect-video bg-zinc-900 border border-zinc-800 rounded-lg flex items-center justify-center text-zinc-700">
                      <ImageOff size={24} />
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
