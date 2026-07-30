import { ReactNode } from "react";

/** 品牌标识：§ + 法智 */
export function Logo({ dark = false, size = "md" }: { dark?: boolean; size?: "sm" | "md" | "lg" }) {
  const dims = { sm: "text-xl", md: "text-2xl", lg: "text-3xl" }[size];
  return (
    <div className="flex items-center gap-2 select-none">
      <span className={`font-serif font-bold text-vermilion ${dims}`}>§</span>
      <span
        className={`font-serif font-bold tracking-tight ${dims} ${
          dark ? "text-white" : "text-ink"
        }`}
      >
        法智
      </span>
    </div>
  );
}

/** 旋转加载指示 */
export function Spinner({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent align-middle ${className}`}
      aria-label="加载中"
    />
  );
}

/** 徽章 */
export function Badge({
  kind = "neutral",
  children,
}: {
  kind?: "success" | "error" | "neutral" | "accent";
  children: ReactNode;
}) {
  return <span className={`badge badge-${kind}`}>{children}</span>;
}

/** 统计卡片（数字用衬线体，左侧红竖线） */
export function StatCard({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="stat-card page-enter">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

/** 空状态（大号装饰 §） */
export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="relative flex flex-col items-center justify-center py-20 text-center overflow-hidden">
      <span className="section-mark absolute -top-6 text-[11rem]">§</span>
      <p className="relative font-serif text-xl font-semibold text-ink">{title}</p>
      {hint && <p className="relative mt-2 text-sm text-slate">{hint}</p>}
    </div>
  );
}

/** 区块标题（衬线） */
export function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <h2 className="font-serif text-[1.375rem] font-semibold leading-snug tracking-[-0.01em] text-ink">
      {children}
    </h2>
  );
}
