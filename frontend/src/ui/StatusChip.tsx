import type { ComponentType } from "react";
import {
  CancelledIcon,
  CheckIcon,
  FailIcon,
  PauseIcon,
  QueuedIcon,
  RunningIcon,
  SkippedIcon,
  SuccessIcon,
  TimeoutIcon,
} from "@/ui/icons";

interface Spec {
  label: string;
  cls: string;
  Icon: ComponentType<{ className?: string }>;
  spin?: boolean;
}

const MAP: Record<string, Spec> = {
  // execuções / jobs / tasks
  SUCCESS: { label: "Success", cls: "bg-ok/15 text-ok", Icon: SuccessIcon },
  RUNNING: { label: "Running", cls: "bg-info/15 text-info", Icon: RunningIcon, spin: true },
  FAILED: { label: "Failed", cls: "bg-danger/15 text-danger", Icon: FailIcon },
  TIMEOUT: { label: "Timeout", cls: "bg-warn/15 text-warn", Icon: TimeoutIcon },
  QUEUED: { label: "Queued", cls: "bg-fg/10 text-fg-muted", Icon: QueuedIcon },
  PENDING: { label: "Pending", cls: "bg-fg/10 text-fg-muted", Icon: QueuedIcon },
  CANCELLED: { label: "Cancelled", cls: "bg-fg/10 text-fg-faint", Icon: CancelledIcon },
  CANCELLING: { label: "Cancelling", cls: "bg-fg/10 text-fg-faint", Icon: CancelledIcon },
  SKIPPED: { label: "Skipped", cls: "bg-warn/15 text-warn", Icon: SkippedIcon },
  // workflow
  DRAFT: { label: "Draft", cls: "bg-fg/10 text-fg-muted", Icon: QueuedIcon },
  ACTIVE: { label: "Active", cls: "bg-ok/15 text-ok", Icon: SuccessIcon },
  DISABLED: { label: "Disabled", cls: "bg-warn/15 text-warn", Icon: PauseIcon },
  ARCHIVED: { label: "Archived", cls: "bg-fg/10 text-fg-faint", Icon: CancelledIcon },
  // schedule
  SCHEDULED: { label: "Scheduled", cls: "bg-primary/15 text-primary", Icon: TimeoutIcon },
  ENABLED: { label: "Ativo", cls: "bg-ok/15 text-ok", Icon: CheckIcon },
  // notification deliveries
  SENT: { label: "Sent", cls: "bg-ok/15 text-ok", Icon: SuccessIcon },
  SENDING: { label: "Sending", cls: "bg-info/15 text-info", Icon: RunningIcon, spin: true },
};

const FALLBACK: Spec = { label: "—", cls: "bg-fg/10 text-fg-muted", Icon: QueuedIcon };

const TONE: Record<string, string> = {
  SUCCESS: "text-ok",
  ACTIVE: "text-ok",
  ENABLED: "text-ok",
  SENT: "text-ok",
  RUNNING: "text-info",
  SENDING: "text-info",
  FAILED: "text-danger",
  TIMEOUT: "text-warn",
  SKIPPED: "text-warn",
  DISABLED: "text-warn",
  SCHEDULED: "text-primary",
};

/** Só o ícone de status (para timelines/steppers), sem o rótulo/badge. */
export function StatusIcon({
  status,
  className = "h-4 w-4",
}: {
  status: string;
  className?: string;
}) {
  const spec = MAP[status] ?? FALLBACK;
  const { Icon } = spec;
  return (
    <Icon
      className={`${className} ${TONE[status] ?? "text-fg-faint"} ${spec.spin ? "animate-spin" : ""}`}
      aria-label={spec.label}
    />
  );
}

export function StatusChip({
  status,
  size = "md",
}: {
  status: string;
  size?: "sm" | "md";
}) {
  const spec = MAP[status] ?? { ...FALLBACK, label: status };
  const { Icon } = spec;
  const pad = size === "sm" ? "px-1.5 py-0.5 text-[11px]" : "px-2 py-0.5 text-xs";
  const dim = size === "sm" ? "h-3 w-3" : "h-3.5 w-3.5";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full font-medium ${pad} ${spec.cls}`}
    >
      <Icon className={`${dim} ${spec.spin ? "animate-spin" : ""}`} aria-hidden />
      {spec.label}
    </span>
  );
}
