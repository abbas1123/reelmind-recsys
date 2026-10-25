import { Button, Spinner } from "@heroui/react";

export function ErrorAlert({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : String(error);
  return (
    <div role="alert" className="flex items-start justify-between gap-4 border-l-2 border-signal bg-ink-raised px-4 py-3">
      <div>
        <p className="kicker !text-signal">Error</p>
        <p className="mt-1 text-sm text-paper-2">{message}</p>
      </div>
      {onRetry && (
        <Button size="sm" variant="outline" onPress={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}

export function Notice({ title, children, tone = "amber" }: { title: string; children: React.ReactNode; tone?: "amber" | "signal" }) {
  return (
    <div className={`border-l-2 ${tone === "amber" ? "border-amber" : "border-signal"} bg-ink-raised px-4 py-3`}>
      <p className={`kicker ${tone === "amber" ? "!text-amber" : "!text-signal"}`}>{title}</p>
      <div className="mt-1 text-sm text-paper-2">{children}</div>
    </div>
  );
}

export function CenterSpinner({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex min-h-48 items-center justify-center gap-3 text-paper-3" role="status">
      <Spinner size="sm" color="current" />
      <span className="kicker">{label}…</span>
    </div>
  );
}
