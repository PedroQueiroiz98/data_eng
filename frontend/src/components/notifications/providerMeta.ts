import type { ComponentType } from "react";
import { ChatIcon, MailIcon } from "@/ui/icons";
import type { NotificationProviderType } from "@/lib/notificationProviders";

export const PROVIDER_META: Record<
  NotificationProviderType,
  { label: string; Icon: ComponentType<{ className?: string }>; hint: string }
> = {
  EMAIL: { label: "Email", Icon: MailIcon, hint: "Enviar notificações por e-mail" },
  BITRIX: { label: "Bitrix", Icon: ChatIcon, hint: "Enviar notificações via Bitrix" },
};

export const EVENT_LABEL: Record<string, string> = {
  JOB_FAILED: "Job falhou",
  WORKFLOW_FAILED: "Workflow falhou",
  JOB_STARTED: "Job iniciado",
  JOB_SUCCESS: "Job concluído",
  JOB_RETRY: "Job em retry",
  WORKFLOW_STARTED: "Workflow iniciado",
  WORKFLOW_SUCCESS: "Workflow concluído",
  WORKFLOW_RETRY: "Workflow em retry",
};

export const linesToList = (s: string): string[] =>
  s
    .split(/[\n,;]/)
    .map((x) => x.trim())
    .filter(Boolean);
