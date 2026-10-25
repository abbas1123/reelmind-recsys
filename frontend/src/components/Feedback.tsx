import { Button, Spinner } from "@heroui/react";
import { AlertTriangle, Info } from "lucide-react";
import type { ReactNode } from "react";

export function ErrorAlert({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : String(error);
  return (
    <div role="alert" className="flex items-start gap-3 rounded-2xl bg-[#ff5a6e]/10 px-4 py-3 ring-1 ring-[#ff5a6e]/30">
      <AlertTriangle className="mt-0.5 size-5 shrink-0 text-[#ff5a6e]" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold">Something went wrong</p>
        <p className="mt-0.5 text-sm text-text-2">{message}</p>
      </div>
      {onRetry && (
        <Button size="sm" variant="secondary" onPress={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}

export function Notice({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex items-start gap-3 rounded-2xl bg-surface-2 px-4 py-3 ring-1 ring-line">
      <Info className="mt-0.5 size-5 shrink-0 text-brand" aria-hidden />
      <div>
        <p className="text-sm font-semibold">{title}</p>
        <div className="mt-0.5 text-sm text-text-2">{children}</div>
      </div>
    </div>
  );
}

export function CenterSpinner({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex min-h-56 items-center justify-center gap-3 text-text-3" role="status">
      <Spinner size="md" color="current" />
      <span className="text-sm">{label}…</span>
    </div>
  );
}
