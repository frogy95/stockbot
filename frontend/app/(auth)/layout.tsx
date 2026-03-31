export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background relative overflow-hidden">
      {/* 배경 격자 텍스처 */}
      <div
        className="absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage:
            "linear-gradient(to right, #fff 1px, transparent 1px), linear-gradient(to bottom, #fff 1px, transparent 1px)",
          backgroundSize: "40px 40px",
        }}
      />
      {/* 중앙 그라디언트 빛 */}
      <div className="absolute inset-0 bg-radial-[ellipse_at_center] from-red-950/20 via-transparent to-transparent" />
      <div className="relative z-10 w-full max-w-sm px-4">{children}</div>
    </div>
  );
}
