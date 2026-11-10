import type { ReactNode } from "react";
import s from "./States.module.css";

/** Loading placeholder shaped like the content it stands in for (no layout shift). */
export function Skeleton({ height = 160, label }: { height?: number; label: string }) {
  return (
    <div className={s.skeleton} style={{ height }} role="status" aria-live="polite">
      <span className={s.skeletonLabel}>{label}</span>
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : "Something went wrong.";
  return (
    <div className={s.error} role="alert">
      <p>{message}</p>
      {onRetry && (
        <button type="button" className={s.retry} onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className={s.empty}>{children}</div>;
}

export function Note({ tone = "info", children }: { tone?: "info" | "warn"; children: ReactNode }) {
  return (
    <p className={`${s.note} ${tone === "warn" ? s.warn : ""}`} role={tone === "warn" ? "alert" : undefined}>
      {children}
    </p>
  );
}
