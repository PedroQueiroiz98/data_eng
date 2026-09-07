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
  SUCCESS: { label: "Success", cls: "bg-green-100 text-green-700", Icon: SuccessIcon },
  RUNNING: { label: "Running", cls: "bg-blue-100 text-blue-700", Icon: RunningIcon, spin: true },
  FAILED: { label: "Failed", cls: "bg-red-100 text-red-700", Icon: FailIcon },
  TIMEOUT: { label: "Timeout", cls: "bg-amber-100 text-amber-800", Icon: TimeoutIcon },
  QUEUED: { label: "Queued", cls: "bg-slate-100 text-slate-600", Icon: QueuedIcon },
  PENDING: { label: "Pending", cls: "bg-slate-100 text-slate-500", Icon: QueuedIcon },
  CANCELLED: { label: "Cancelled", cls: "bg-slate-200 text-slate-600", Icon: CancelledIcon },
  CANCELLING: { label: "Cancelling", cls: "bg-slate-200 text-slate-600", Icon: CancelledIcon },
  SKIPPED: { label: "Skipped", cls: "bg-amber-50 text-amber-700", Icon: SkippedIcon },
  // workflow
  DRAFT: { label: "Draft", cls: "bg-slate-100 text-slate-600", Icon: QueuedIcon },
  ACTIVE: { label: "Active", cls: "bg-green-100 text-green-700", Icon: SuccessIcon },
  DISABLED: { label: "Disabled", cls: "bg-amber-100 text-amber-800", Icon: PauseIcon },
  ARCHIVED: { label: "Archived", cls: "bg-slate-200 text-slate-500", Icon: CancelledIcon },
  // schedule
  SCHEDULED: { label: "Scheduled", cls: "bg-indigo-100 text-indigo-700", Icon: TimeoutIcon },
  ENABLED: { label: "Ativo", cls: "bg-green-100 text-green-700", Icon: CheckIcon },
};

const FALLBACK: Spec = { label: "—", cls: "bg-slate-100 text-slate-600", Icon: QueuedIcon };

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
