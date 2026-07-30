import { ReactNode } from "react";

/** 品牌标识：印章方块 § + 法智 */
export function Logo({ dark = false, size = "md" }: { dark?: boolean; size?: "sm" | "md" | "lg" }) {
  const seal = { sm: "h-7 w-7 text-base", md: "h-8 w-8 text-lg", lg: "h-11 w-11 text-2xl" }[size];
  const word = { sm: "text-lg", md: "text-xl", lg: "text-2xl" }[size];
  return (
    <div className="flex items-center gap-2.5 select-none">
      <span className={`logo-seal ${seal}`}>§</span>
      <span className={`font-serif font-bold tracking-tight ${word} ${dark ? "text-white" : "text-ink"}`}>
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
      role="status"
      aria-label="加载中"
    />
  );
}

/** 徽章（可选 status 圆点） */
export function Badge({
  kind = "neutral",
  dot = false,
  children,
}: {
  kind?: "success" | "error" | "neutral" | "accent";
  dot?: boolean;
  children: ReactNode;
}) {
  return (
    <span className={`badge badge-${kind}`}>
      {dot && <span className="inline-block h-1.5 w-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}

/** 统计卡片（数字用衬线体，左侧红竖线，悬停上浮） */
export function StatCard({ label, value, icon }: { label: string; value: ReactNode; icon?: ReactNode }) {
  return (
    <div className="stat-card page-enter flex items-start justify-between gap-3">
      <div>
        <div className="stat-value">{value}</div>
        <div className="stat-label">{label}</div>
      </div>
      {icon && (
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[rgba(2,132,199,0.10)] text-accent">
          {icon}
        </span>
      )}
    </div>
  );
}

/** 空状态（大号装饰 §） */
export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="relative flex flex-col items-center justify-center overflow-hidden py-20 text-center">
      <span className="section-mark absolute -top-6 text-[11rem]">§</span>
      <p className="relative font-serif text-xl font-semibold text-ink">{title}</p>
      {hint && <p className="relative mt-2 max-w-sm text-sm leading-relaxed text-slate">{hint}</p>}
    </div>
  );
}

/** 区块标题（衬线 + 朱红短杠） */
export function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <h2 className="flex items-center gap-3 font-serif text-[1.375rem] font-semibold leading-snug tracking-[-0.01em] text-ink">
      <span className="inline-block h-5 w-1 rounded-full bg-accent" />
      {children}
    </h2>
  );
}

/** 骨架屏块 */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
}
