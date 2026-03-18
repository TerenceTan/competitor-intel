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
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

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
      className="hidden md:flex flex-col w-64 min-h-screen border-r border-slate-200 bg-white"
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-6 py-5 border-b border-slate-200">
        <div
          className="w-8 h-8 rounded-md flex items-center justify-center font-bold text-white text-sm shrink-0"
          style={{ backgroundColor: "#0064FA" }}
        >
          P
        </div>
        <div>
          <span className="text-slate-900 font-semibold text-sm block leading-tight">
            Pepperstone
          </span>
          <span className="text-slate-500 text-xs">Competitor Intel</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                active
                  ? "text-white"
                  : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
              )}
              style={active ? { backgroundColor: "#0064FA" } : undefined}
            >
              <Icon
                className="w-4 h-4 shrink-0"
              />
              <span className="flex-1">{item.label}</span>
              {item.label === "Competitors" && competitorCount !== undefined && (
                <Badge
                  variant="outline"
                  className={cn(
                    "text-xs h-5",
                    active ? "border-blue-400 text-blue-100" : "border-slate-300 text-slate-500"
                  )}
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
  );
}
