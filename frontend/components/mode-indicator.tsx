"use client";

import { Badge } from "@/components/ui/badge";
import { usePolling } from "@/lib/hooks/use-polling";

interface SettingResponse {
  key: string;
  value: string;
}

export function ModeIndicator() {
  const { data, isLoading } = usePolling<SettingResponse>(
    "/api/v1/settings/trading_mode",
    60_000
  );

  if (isLoading || !data) return null;

  const mode = data.value;

  if (mode === "auto") {
    return (
      <Badge
        variant="destructive"
        className="font-mono text-[10px] tracking-widest uppercase"
      >
        자동
      </Badge>
    );
  }

  if (mode === "semi-auto") {
    return (
      <Badge
        variant="outline"
        className="font-mono text-[10px] tracking-widest uppercase border-yellow-500 text-yellow-400 bg-yellow-500/10"
      >
        반자동
      </Badge>
    );
  }

  // manual (기본)
  return (
    <Badge
      variant="secondary"
      className="font-mono text-[10px] tracking-widest uppercase"
    >
      수동
    </Badge>
  );
}
