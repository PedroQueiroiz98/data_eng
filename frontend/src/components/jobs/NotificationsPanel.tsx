import { useJobNotifications, useRetryNotification } from "@/hooks/useNotifications";
import type { NotificationRecord } from "@/lib/notifications";
import { Button, StatusIcon } from "@/ui";
import { ChatIcon, MailIcon } from "@/ui/icons";

const CHANNEL_ICON = { EMAIL: MailIcon, BITRIX: ChatIcon } as const;
const STATUS_TONE: Record<string, string> = {
  SENT: "text-ok",
  FAILED: "text-danger",
  SENDING: "text-info",
  PENDING: "text-fg-muted",
};

function clock(iso: string | null): string {
  return iso ? new Date(iso).toLocaleTimeString() : "";
}

export function NotificationsPanel({ jobId }: { jobId: string }) {
  const { data, isLoading } = useJobNotifications(jobId);
  const retry = useRetryNotification(jobId);

  if (isLoading) {
    return <p className="text-sm text-fg-faint">Carregando…</p>;
  }
  if (!data || data.length === 0) {
    return (
      <p className="text-sm text-fg-faint">
        Nenhum canal de notificação configurado para este pipeline.
      </p>
    );
  }

  return (
    <ul className="divide-y divide-surface-border">
      {data.map((n: NotificationRecord) => {
        const Icon = CHANNEL_ICON[n.channel] ?? MailIcon;
        const failed = n.status === "FAILED";
        return (
          <li key={n.id} className="flex flex-wrap items-start gap-3 py-3">
            <Icon className="mt-0.5 h-4 w-4 shrink-0 text-fg-muted" />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 text-sm">
                <span className="font-medium text-fg">{n.channel}</span>
                <span
                  className={`inline-flex items-center gap-1 text-xs ${
                    STATUS_TONE[n.status] ?? "text-fg-muted"
                  }`}
                >
                  <StatusIcon
                    status={n.status === "SENT" ? "SUCCESS" : n.status === "FAILED" ? "FAILED" : "RUNNING"}
                    className="h-3.5 w-3.5"
                  />
                  {n.status}
                </span>
                {n.attempt > 0 && (
                  <span className="text-xs text-fg-faint">
                    tentativa {n.attempt}/{n.max_attempts}
                  </span>
                )}
              </div>
              {n.recipient && (
                <div className="truncate text-xs text-fg-muted">{n.recipient}</div>
              )}
              <div className="text-xs text-fg-faint">
                {n.status === "SENT" && n.sent_at
                  ? `enviado ${clock(n.sent_at)}`
                  : `criado ${clock(n.created_at)}`}
              </div>
              {failed && n.error_message && (
                <pre className="mt-1 overflow-x-auto whitespace-pre-wrap rounded bg-danger/5 px-2 py-1 text-xs text-danger">
                  {n.error_message}
                </pre>
              )}
            </div>
            {failed && (
              <Button
                size="sm"
                variant="outlined"
                loading={retry.isPending}
                onClick={() => retry.mutate(n.id)}
              >
                Retry Notification
              </Button>
            )}
          </li>
        );
      })}
    </ul>
  );
}
