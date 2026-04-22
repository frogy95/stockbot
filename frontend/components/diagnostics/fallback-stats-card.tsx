import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export function FallbackStatsCard() {
  return (
    <Card className="opacity-50">
      <CardHeader>
        <CardTitle>폴백 발동 통계</CardTitle>
        <CardDescription>Phase 8.5 Sprint 2에서 구현 예정</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex h-32 items-center justify-center text-xs font-mono text-muted-foreground">
          Coming Soon (Phase 8.5 Sprint 2)
        </div>
      </CardContent>
    </Card>
  );
}
