"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Building2,
  Globe,
  Activity,
  Lightbulb,
  Settings,
  Target,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface SidebarProps {
  competitorCount?: number;
}

const navItems = [
  {
    label: "Executive Summary",
    href: "/",
    icon: LayoutDashboard,
  },
  {
    label: "Competitors",
    href: "/competitors",
    icon: Building2,
    showCount: true,
  },
  {
    label: "Markets",
    href: "/markets",
    icon: Globe,
  },
  {
    label: "Change Feed",
    href: "/changes",
    icon: Activity,
  },
  {
    label: "AI Insights",
    href: "/insights",
    icon: Lightbulb,
  },
  { divider: true } as const,
  {
    label: "Our Data",
    href: "/pepperstone",
    icon: Target,
  },
  {
    label: "Admin",
    href: "/admin",
    icon: Settings,
  },
];

export function Sidebar({ competitorCount }: SidebarProps) {
  const pathname = usePathname();

  function isActive(href: string) {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  }

  return (
    <aside
      className="hidden md:flex flex-col w-64 min-h-screen border-r border-gray-200 bg-white"
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-6 py-5 border-b border-gray-200">
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center font-bold text-white text-sm shrink-0 bg-primary"
        >
          P
        </div>
        <div>
          <span className="text-gray-900 font-semibold text-sm block leading-tight">
            Pepperstone
          </span>
          <span className="text-gray-500 text-xs">Competitor Intel</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1" role="navigation" aria-label="Main navigation">
        {navItems.map((item, idx) => {
          if ("divider" in item) {
            return <div key={`div-${idx}`} className="my-3 border-t border-gray-100" />;
          }
          const Icon = item.icon;
          const active = isActive(item.href!);
          return (
            <Link
              key={item.href}
              href={item.href!}
              aria-current={active ? "page" : undefined}
              className={cn(
                "group flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 focus-visible:ring-offset-1",
                active
                  ? "bg-primary/10 text-primary"
                  : "text-gray-600 hover:text-gray-900 hover:bg-gray-100/80 active:bg-gray-200/60"
              )}
            >
              <Icon
                className={cn(
                  "w-[18px] h-[18px] shrink-0 transition-colors",
                  active ? "text-primary" : "text-gray-400 group-hover:text-gray-600"
                )}
              />
              <span className="flex-1">{item.label}</span>
              {"showCount" in item && item.showCount && competitorCount !== undefined && (
                <span
                  className={cn(
                    "text-xs font-semibold min-w-[20px] h-5 flex items-center justify-center rounded-md px-1.5 transition-colors",
                    active
                      ? "bg-primary/15 text-primary"
                      : "bg-gray-100 text-gray-500 group-hover:bg-gray-200/80 group-hover:text-gray-600"
                  )}
                >
                  {competitorCount}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-6 py-4 border-t border-gray-200">
        <p className="text-gray-500 text-xs font-medium">APAC Marketing Team</p>
        <p className="text-gray-400 text-xs mt-0.5">Internal Use Only</p>
      </div>
    </aside>
  );
}
