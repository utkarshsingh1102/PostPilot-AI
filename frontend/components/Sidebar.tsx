"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, ClipboardList, ExternalLink, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useSources } from "@/lib/hooks";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/review", label: "Review Queue", icon: ClipboardList },
];

interface SidebarProps {
  activeSourceId?: number;
  onSourceSelect: (id: number | undefined) => void;
}

export default function Sidebar({ activeSourceId, onSourceSelect }: SidebarProps) {
  const pathname = usePathname();
  const { data: sources, isLoading } = useSources();

  return (
    <aside className="w-60 shrink-0 flex flex-col h-screen bg-zinc-950 border-r border-zinc-800 overflow-y-auto">
      {/* Logo */}
      <div className="flex items-center gap-2 px-5 py-5 border-b border-zinc-800">
        <div className="w-7 h-7 rounded-md bg-violet-600 flex items-center justify-center text-xs font-bold text-white">
          P
        </div>
        <span className="font-semibold text-sm text-zinc-100 tracking-tight">PostPilot AI</span>
      </div>

      {/* Navigation */}
      <nav className="px-3 pt-4 space-y-0.5">
        {NAV.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            onClick={() => onSourceSelect(undefined)}
            className={cn(
              "flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors",
              pathname === href
                ? "bg-zinc-800 text-zinc-100"
                : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
            )}
          >
            <Icon size={15} />
            {label}
          </Link>
        ))}
      </nav>

      {/* Sources */}
      <div className="mt-6 px-3">
        <p className="px-3 mb-2 text-[11px] font-medium tracking-widest text-zinc-600 uppercase">
          Sources
        </p>
        {isLoading && (
          <div className="flex items-center gap-2 px-3 py-2 text-zinc-600 text-sm">
            <Loader2 size={13} className="animate-spin" /> Loading…
          </div>
        )}
        {sources?.map((source) => (
          <button
            key={source.id}
            onClick={() => onSourceSelect(activeSourceId === source.id ? undefined : source.id)}
            className={cn(
              "w-full text-left flex items-start gap-2 px-3 py-2 rounded-md text-sm transition-colors group",
              activeSourceId === source.id
                ? "bg-zinc-800 text-zinc-100"
                : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
            )}
          >
            <div className="flex-1 min-w-0">
              <p className="truncate font-medium">
                {source.label ?? "Untitled"}
              </p>
              <p className="truncate text-[11px] text-zinc-600 group-hover:text-zinc-500">
                {source.linkedin_url.replace("https://www.linkedin.com/", "")}
              </p>
            </div>
            <ExternalLink
              size={11}
              className="mt-0.5 shrink-0 opacity-0 group-hover:opacity-60 transition-opacity"
              onClick={(e) => {
                e.stopPropagation();
                window.open(source.linkedin_url, "_blank");
              }}
            />
          </button>
        ))}
        {sources?.length === 0 && (
          <p className="px-3 py-2 text-xs text-zinc-600">No sources yet.</p>
        )}
      </div>
    </aside>
  );
}
