"use client";

import { useState } from "react";
import { Copy, Download, ExternalLink, CheckCheck, ImageOff, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { cn, formatDate, truncate } from "@/lib/utils";
import type { ProcessedPost } from "@/types/post";

interface PostCardProps {
  post: ProcessedPost;
  onOpen: (id: number | null) => void;
}

export default function PostCard({ post, onOpen }: PostCardProps) {
  const [copied, setCopied] = useState(false);

  // Build a copy-ready text from the processed post
  const copyText = [
    post.rewritten_post,
    post.hashtags?.join(" "),
  ]
    .filter(Boolean)
    .join("\n\n");

  async function handleCopy(e: React.MouseEvent) {
    e.stopPropagation();
    if (!copyText) return;
    await navigator.clipboard.writeText(copyText);
    setCopied(true);
    toast.success("Copied to clipboard");
    setTimeout(() => setCopied(false), 2000);
  }

  function handleDownload(e: React.MouseEvent) {
    e.stopPropagation();
    if (!post.generated_image_url) return;
    // The generated_image_url is the local path; construct the download URL
    const filename = post.generated_image_url.split("/").pop();
    const downloadUrl = `${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}/images/${filename}`;
    const a = document.createElement("a");
    a.href = downloadUrl;
    a.download = filename ?? "image";
    a.click();
  }

  const isFailed = post.status === "failed";
  const isProcessing = post.status === "processing" || post.status === "pending";

  return (
    <article
      onClick={() => onOpen(post.scraped_post_id)}
      className={cn(
        "group relative flex flex-col bg-zinc-900 border rounded-xl overflow-hidden cursor-pointer transition-all duration-200",
        "hover:border-zinc-600 hover:shadow-lg hover:shadow-black/30 hover:-translate-y-0.5",
        isFailed ? "border-red-900/60" : "border-zinc-800"
      )}
    >
      {/* Image */}
      <div className="aspect-video bg-zinc-800 overflow-hidden">
        {post.generated_image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={`${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}/images/${post.generated_image_url.split("/").pop()}`}
            alt="Post image"
            className="w-full h-full object-cover group-hover:scale-[1.02] transition-transform duration-300"
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = "none";
            }}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-zinc-700">
            <ImageOff size={28} />
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex flex-col flex-1 p-4 gap-3">
        {/* Status badge */}
        {isFailed && (
          <div className="flex items-center gap-1.5 text-xs text-red-400">
            <AlertCircle size={12} />
            <span>AI processing failed</span>
          </div>
        )}
        {isProcessing && (
          <div className="flex items-center gap-1.5 text-xs text-amber-400">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
            Processing…
          </div>
        )}

        {/* Hook */}
        {post.hooks && (
          <p className="text-xs font-semibold text-violet-400 leading-snug line-clamp-2">
            {post.hooks}
          </p>
        )}

        {/* Body */}
        <p className="text-sm text-zinc-300 leading-relaxed line-clamp-4 flex-1">
          {truncate(post.rewritten_post, 200) || (
            <span className="text-zinc-600 italic">No content</span>
          )}
        </p>

        {/* Hashtags */}
        {post.hashtags && post.hashtags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {post.hashtags.slice(0, 5).map((tag) => (
              <span
                key={tag}
                className="px-2 py-0.5 text-[10px] font-medium rounded-full bg-zinc-800 text-zinc-400"
              >
                {tag}
              </span>
            ))}
            {post.hashtags.length > 5 && (
              <span className="px-2 py-0.5 text-[10px] text-zinc-600">
                +{post.hashtags.length - 5}
              </span>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between pt-1 border-t border-zinc-800">
          <span className="text-[11px] text-zinc-600">{formatDate(post.created_at)}</span>

          <div className="flex items-center gap-1">
            <button
              onClick={handleCopy}
              disabled={!copyText}
              title="Copy text"
              className="p-1.5 rounded-md text-zinc-600 hover:text-zinc-300 hover:bg-zinc-800 transition-colors disabled:opacity-30"
            >
              {copied ? <CheckCheck size={13} className="text-green-400" /> : <Copy size={13} />}
            </button>
            <button
              onClick={handleDownload}
              disabled={!post.generated_image_url}
              title="Download image"
              className="p-1.5 rounded-md text-zinc-600 hover:text-zinc-300 hover:bg-zinc-800 transition-colors disabled:opacity-30"
            >
              <Download size={13} />
            </button>
          </div>
        </div>
      </div>
    </article>
  );
}

// Skeleton loader
export function PostCardSkeleton() {
  return (
    <div className="flex flex-col bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden animate-pulse">
      <div className="aspect-video bg-zinc-800" />
      <div className="p-4 space-y-3">
        <div className="h-3 bg-zinc-800 rounded w-3/4" />
        <div className="space-y-2">
          <div className="h-3 bg-zinc-800 rounded" />
          <div className="h-3 bg-zinc-800 rounded" />
          <div className="h-3 bg-zinc-800 rounded w-5/6" />
        </div>
        <div className="flex gap-1.5">
          <div className="h-4 w-16 bg-zinc-800 rounded-full" />
          <div className="h-4 w-20 bg-zinc-800 rounded-full" />
          <div className="h-4 w-14 bg-zinc-800 rounded-full" />
        </div>
        <div className="h-px bg-zinc-800" />
        <div className="flex justify-between">
          <div className="h-3 w-20 bg-zinc-800 rounded" />
          <div className="flex gap-1">
            <div className="h-6 w-6 bg-zinc-800 rounded" />
            <div className="h-6 w-6 bg-zinc-800 rounded" />
          </div>
        </div>
      </div>
    </div>
  );
}
