"use client";

import { useState } from "react";
import { Plus, RefreshCw, Zap, Loader2, Trash2, AlertTriangle, Clock } from "lucide-react";
import { toast } from "sonner";
import { useScrapeNow, useProcessAll, useBackendHealth, useDeleteSource, useSchedulerStatus } from "@/lib/hooks";
import AddSourceModal from "./AddSourceModal";
import { cn } from "@/lib/utils";

interface TopbarProps {
  title: string;
  activeSourceId?: number;
  activeSourceLabel?: string;
  onSourceDeselect?: () => void;
}

function formatIST(isoString: string | null): string {
  if (!isoString) return "—";
  return new Date(isoString).toLocaleTimeString("en-IN", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  });
}

export default function Topbar({ title, activeSourceId, activeSourceLabel, onSourceDeselect }: TopbarProps) {
  const [addOpen, setAddOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const scrape = useScrapeNow();
  const processAllMutation = useProcessAll();
  const deleteSource = useDeleteSource();
  const { data: isHealthy, isLoading: healthLoading, isFetching: healthFetching } = useBackendHealth();
  const { data: schedulerData } = useSchedulerStatus();

  const scrapeJob = schedulerData?.jobs.find((j) => j.id === "scrape_all_sources");

  async function handleScrape() {
    try {
      const res = await scrape.mutateAsync(activeSourceId);
      toast.success(res.message ?? "Scrape started");
    } catch {
      toast.error("Scrape failed");
    }
  }

  async function handleProcessAll() {
    try {
      const res = await processAllMutation.mutateAsync();
      toast.success(res.message ?? `Processing ${res.triggered} post(s)`);
    } catch {
      toast.error("Process all failed");
    }
  }

  async function handleDeleteSource() {
    if (!activeSourceId) return;
    try {
      await deleteSource.mutateAsync(activeSourceId);
      toast.success(`Source "${activeSourceLabel ?? activeSourceId}" deleted. Processed posts retained.`);
      setConfirmDelete(false);
      onSourceDeselect?.();
    } catch {
      toast.error("Failed to delete source");
      setConfirmDelete(false);
    }
  }

  return (
    <>
      <header className="h-14 shrink-0 flex items-center justify-between px-6 border-b border-zinc-800 bg-zinc-950">
        <h1 className="text-sm font-semibold text-zinc-100">{title}</h1>

        <div className="flex items-center gap-2">
          {/* Scheduler next run */}
          {scrapeJob?.next_run && (
            <div
              title={`Last scrape: ${formatIST(scrapeJob.last_run)} IST\nNext scrape: ${formatIST(scrapeJob.next_run)} IST`}
              className="hidden sm:flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-zinc-900 border border-zinc-800 text-[11px] text-zinc-500"
            >
              <Clock size={11} className="text-zinc-600" />
              <span>
                {scrapeJob.last_run
                  ? `Last ${formatIST(scrapeJob.last_run)}`
                  : "Not run yet"}
                {" · "}
                Next {formatIST(scrapeJob.next_run)}
                {" IST"}
              </span>
            </div>
          )}

          {/* Backend health indicator */}
          <div
            title={
              healthLoading ? "Checking backend…" :
              isHealthy ? "Backend online" : "Backend offline"
            }
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-zinc-900 border border-zinc-800 text-xs"
          >
            <span
              className={cn(
                "w-1.5 h-1.5 rounded-full transition-colors",
                healthLoading || healthFetching
                  ? "bg-zinc-500 animate-pulse"
                  : isHealthy
                  ? "bg-emerald-500"
                  : "bg-red-500 animate-pulse"
              )}
            />
            <span className={cn(
              "text-[11px] font-medium",
              healthLoading ? "text-zinc-500" :
              isHealthy ? "text-emerald-400" : "text-red-400"
            )}>
              {healthLoading ? "Checking…" : isHealthy ? "Online" : "Offline"}
            </span>
          </div>

          <div className="w-px h-4 bg-zinc-800" />

          <button
            onClick={handleScrape}
            disabled={scrape.isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-zinc-800 text-zinc-300 hover:bg-zinc-700 hover:text-zinc-100 transition-colors disabled:opacity-50"
          >
            {scrape.isPending ? (
              <Loader2 size={13} className="animate-spin" />
            ) : (
              <RefreshCw size={13} />
            )}
            Scrape Now
          </button>

          <button
            onClick={handleProcessAll}
            disabled={processAllMutation.isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-zinc-800 text-zinc-300 hover:bg-zinc-700 hover:text-zinc-100 transition-colors disabled:opacity-50"
          >
            {processAllMutation.isPending ? (
              <Loader2 size={13} className="animate-spin" />
            ) : (
              <Zap size={13} />
            )}
            Process All
          </button>

          {/* Delete source — only shown when a source is active */}
          {activeSourceId && (
            confirmDelete ? (
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-red-950 border border-red-800">
                <AlertTriangle size={12} className="text-red-400" />
                <span className="text-[11px] text-red-300">Delete raw posts?</span>
                <button
                  onClick={handleDeleteSource}
                  disabled={deleteSource.isPending}
                  className="text-[11px] font-semibold text-red-300 hover:text-white ml-1 disabled:opacity-50"
                >
                  {deleteSource.isPending ? <Loader2 size={11} className="animate-spin" /> : "Yes"}
                </button>
                <span className="text-red-700">·</span>
                <button
                  onClick={() => setConfirmDelete(false)}
                  className="text-[11px] text-zinc-400 hover:text-zinc-200"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                onClick={() => setConfirmDelete(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-zinc-800 text-zinc-400 hover:bg-red-950 hover:border-red-900 hover:text-red-400 border border-zinc-700 transition-colors"
              >
                <Trash2 size={13} />
                Delete Source
              </button>
            )
          )}

          <button
            onClick={() => setAddOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-violet-600 text-white hover:bg-violet-500 transition-colors"
          >
            <Plus size={13} />
            Add Source
          </button>
        </div>
      </header>

      <AddSourceModal open={addOpen} onClose={() => setAddOpen(false)} />
    </>
  );
}
