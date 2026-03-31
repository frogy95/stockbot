"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { Badge } from "@/components/ui/badge";
import { LIVE_BANNER_BG, PAPER_BANNER_BG } from "@/lib/colors";
import {
  LayoutDashboard,
  Briefcase,
  ClipboardList,
  Zap,
  ScanSearch,
  History,
  BarChart3,
  Settings,
  ChevronLeft,
  ChevronRight,
  LogOut,
} from "@/components/ui/icons";

const NAV_ITEMS = [
  { href: "/", icon: LayoutDashboard, label: "대시보드" },
  { href: "/positions", icon: Briefcase, label: "포지션" },
  { href: "/orders", icon: ClipboardList, label: "주문 현황" },
  { href: "/signals", icon: Zap, label: "매매 신호" },
  { href: "/screening", icon: ScanSearch, label: "스크리닝" },
  { href: "/history", icon: History, label: "매매 이력" },
  { href: "/analytics", icon: BarChart3, label: "성과 분석" },
  { href: "/settings", icon: Settings, label: "설정" },
] as const;

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const isLive = user?.trading_env === "live";

  return (
    <aside
      className={cn(
        "flex flex-col shrink-0 h-full border-r border-border/50 bg-card/50 transition-all duration-200",
        collapsed ? "w-14" : "w-52"
      )}
    >
      {/* 헤더 + 접기 버튼 */}
      <div className="flex items-center justify-between h-12 px-3 border-b border-border/30">
        {!collapsed && (
          <span className="text-xs font-mono font-semibold tracking-[0.15em] text-muted-foreground uppercase">
            StockBot
          </span>
        )}
        <button
          onClick={() => setCollapsed((v) => !v)}
          className={cn(
            "p-1 rounded text-muted-foreground hover:text-foreground hover:bg-accent transition-colors",
            collapsed && "mx-auto"
          )}
          aria-label={collapsed ? "사이드바 펼치기" : "사이드바 접기"}
        >
          {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
        </button>
      </div>

      {/* 네비게이션 */}
      <nav className="flex-1 py-2 overflow-y-auto overflow-x-hidden">
        {NAV_ITEMS.map(({ href, icon: Icon, label }) => {
          const isActive =
            href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 h-9 px-3 mx-1 rounded text-sm font-mono transition-colors",
                "hover:bg-accent hover:text-accent-foreground",
                isActive
                  ? "bg-accent text-accent-foreground font-medium border-l-2 border-primary"
                  : "text-muted-foreground border-l-2 border-transparent"
              )}
              title={collapsed ? label : undefined}
            >
              <Icon size={15} className="shrink-0" />
              {!collapsed && (
                <span className="truncate text-xs tracking-wide">{label}</span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* 하단: 모드 배지 + 로그아웃 */}
      <div className="border-t border-border/30 p-2 space-y-1">
        {!collapsed && (
          <div className="flex items-center gap-2 px-2 py-1">
            <Badge
              className="text-[10px] font-mono px-1.5 py-0 text-white border-0"
              style={{ backgroundColor: isLive ? LIVE_BANNER_BG : PAPER_BANNER_BG }}
            >
              {isLive ? "LIVE" : "PAPER"}
            </Badge>
            <span className="text-[10px] font-mono text-muted-foreground truncate">
              {user?.username ?? "admin"}
            </span>
          </div>
        )}
        <button
          onClick={logout}
          className={cn(
            "flex items-center gap-3 h-9 px-3 w-full rounded text-xs font-mono",
            "text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors",
            collapsed && "justify-center"
          )}
          title={collapsed ? "로그아웃" : undefined}
        >
          <LogOut size={14} className="shrink-0" />
          {!collapsed && "로그아웃"}
        </button>
      </div>
    </aside>
  );
}
