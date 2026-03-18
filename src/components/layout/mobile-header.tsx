"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, X, LayoutDashboard, Building2, Globe, Activity, Lightbulb, Settings } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

const navItems = [
  { label: "Executive Summary", href: "/", icon: LayoutDashboard },
  { label: "Competitors", href: "/competitors", icon: Building2 },
  { label: "Markets", href: "/markets", icon: Globe },
  { label: "Change Feed", href: "/changes", icon: Activity },
  { label: "AI Insights", href: "/insights", icon: Lightbulb },
  { label: "Admin", href: "/admin", icon: Settings },
];

export function MobileHeader({ competitorCount }: { competitorCount?: number }) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  function isActive(href: string) {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  }

  return (
    <>
      {/* Hamburger button — only visible on mobile */}
      <button
        className="md:hidden p-2 rounded-lg text-slate-600 hover:bg-slate-100"
        onClick={() => setOpen(true)}
        aria-label="Open menu"
      >
        <Menu className="w-5 h-5" />
      </button>

      {/* Mobile drawer overlay */}
      {open && (
        <div className="fixed inset-0 z-50 md:hidden">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => setOpen(false)}
          />
          {/* Drawer */}
          <aside className="absolute left-0 top-0 h-full w-72 bg-white shadow-xl flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-5 border-b border-slate-200">
              <div className="flex items-center gap-3">
                <div
                  className="w-8 h-8 rounded-md flex items-center justify-center font-bold text-white text-sm shrink-0"
                  style={{ backgroundColor: "#0064FA" }}
                >
                  P
                </div>
                <div>
                  <span className="text-slate-900 font-semibold text-sm block leading-tight">Pepperstone</span>
                  <span className="text-slate-500 text-xs">Competitor Intel</span>
                </div>
              </div>
              <button
                className="p-2 rounded-lg text-slate-500 hover:bg-slate-100"
                onClick={() => setOpen(false)}
                aria-label="Close menu"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            {/* Nav */}
            <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
              {navItems.map((item) => {
                const Icon = item.icon;
                const active = isActive(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setOpen(false)}
                    className={cn(
                      "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                      active ? "text-white" : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
                    )}
                    style={active ? { backgroundColor: "#0064FA" } : undefined}
                  >
                    <Icon className="w-4 h-4 shrink-0" />
                    <span className="flex-1">{item.label}</span>
                    {item.label === "Competitors" && competitorCount !== undefined && (
                      <Badge
                        variant="outline"
                        className={cn("text-xs h-5", active ? "border-blue-400 text-blue-100" : "border-slate-300 text-slate-500")}
                      >
                        {competitorCount}
                      </Badge>
                    )}
                  </Link>
                );
              })}
            </nav>
            {/* Footer */}
            <div className="px-6 py-4 border-t border-slate-200">
              <p className="text-slate-500 text-xs">APAC Marketing Team</p>
              <p className="text-slate-400 text-xs mt-0.5">Internal Use Only</p>
            </div>
          </aside>
        </div>
      )}
    </>
  );
}
