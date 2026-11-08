import type { ReactNode } from "react";
import { LoadError } from "../api/client";
import { space } from "../../theme/tokens";

export function Skeleton({ lines = 6 }: { lines?: number }) {
  return (
    <div role="status" aria-live="polite" className="skeleton-stack">
      <span className="visually-hidden">Loading the results</span>
      <div className="skeleton" style={{ width: "60%", height: space[7] }} />
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} className="skeleton" style={{ width: `${92 - i * 9}%`, height: space[4] }} />
      ))}
      <div className="skeleton" style={{ width: "100%", height: space[8] * 3 }} />
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: Error; onRetry: () => void }) {
  const retryable = !(error instanceof LoadError) || error.retryable;
  return (
    <div className="state" role="alert">
      <p className="state__title">The results did not load.</p>
      <p className="state__body">{error.message}</p>
      {retryable && (
        <button className="button" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="state">
      <p className="state__title">{title}</p>
      {children && <p className="state__body">{children}</p>}
    </div>
  );
}

export function Section({ id, title, lead, children }: { id: string; title: string; lead?: ReactNode; children: ReactNode }) {
  return (
    <section className="section" aria-labelledby={id}>
      <h2 id={id}>{title}</h2>
      {lead && <p className="section__lead">{lead}</p>}
      {children}
    </section>
  );
}
