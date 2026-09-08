import { apiDelete, apiGet, apiPatch, apiPost, apiPut } from "@/lib/api";

export type NotificationProviderType = "EMAIL" | "BITRIX";

export type NotificationEventType =
  | "JOB_FAILED"
  | "WORKFLOW_FAILED"
  | "JOB_STARTED"
  | "JOB_SUCCESS"
  | "JOB_RETRY"
  | "WORKFLOW_STARTED"
  | "WORKFLOW_SUCCESS"
  | "WORKFLOW_RETRY";

export type NotificationDeliveryStatus = "PENDING" | "SENDING" | "SENT" | "FAILED";

export const SECRET_MASK = "********";

export interface EmailConfig {
  host: string;
  port: number | null;
  username: string | null;
  from_email: string;
  from_name: string | null;
  use_tls: boolean;
  recipients: string[];
  cc: string[];
  bcc: string[];
}

export interface BitrixConfig {
  url: string;
  send_message_path: string | null;
  bot_id: string | null;
  dialog_id: string;
}

export interface NotificationProvider {
  id: string;
  name: string;
  description: string | null;
  provider_type: NotificationProviderType;
  enabled: boolean;
  configuration: Record<string, unknown>;
  has_password: boolean;
  has_credential: boolean;
  summary: string;
  created_at: string;
  updated_at: string;
}

export interface NotificationProviderInput {
  name: string;
  description: string | null;
  provider_type: NotificationProviderType;
  enabled: boolean;
  configuration: Record<string, unknown>;
  secret: string | null; // omit / "" / "********" = mantém o atual
}

export interface NotificationDelivery {
  id: string;
  notification_provider_id: string | null;
  provider_type: NotificationProviderType;
  event_type: NotificationEventType;
  workflow_id: string | null;
  job_id: string | null;
  execution_id: string | null;
  status: NotificationDeliveryStatus;
  attempt: number;
  max_attempts: number;
  error_message: string | null;
  recipient: string | null;
  created_at: string;
  sent_at: string | null;
  next_retry_at: string | null;
}

export interface NotificationDeliveryDetail extends NotificationDelivery {
  payload: Record<string, unknown>;
}

export interface NotificationDeliveryPage {
  items: NotificationDelivery[];
  total: number;
  limit: number;
  offset: number;
}

export interface NotificationTestResult {
  ok: boolean;
  detail: string;
  error: string | null;
}

export interface DeliveryFilters {
  provider?: string;
  status?: NotificationDeliveryStatus;
  event?: NotificationEventType;
  workflow?: string;
  job?: string;
  environment?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

// ─── providers ────────────────────────────────────────────────────────────
export const listProviders = (): Promise<NotificationProvider[]> =>
  apiGet("/notifications/providers");

export const getProvider = (id: string): Promise<NotificationProvider> =>
  apiGet(`/notifications/providers/${id}`);

export const createProvider = (
  body: NotificationProviderInput,
): Promise<NotificationProvider> => apiPost("/notifications/providers", body);

export const updateProvider = (
  id: string,
  body: Partial<NotificationProviderInput>,
): Promise<NotificationProvider> => apiPut(`/notifications/providers/${id}`, body);

export const deleteProvider = (id: string): Promise<void> =>
  apiDelete(`/notifications/providers/${id}`);

export const setProviderEnabled = (
  id: string,
  enabled: boolean,
): Promise<NotificationProvider> =>
  apiPatch(`/notifications/providers/${id}/enabled`, { enabled });

export const testProvider = (id: string): Promise<NotificationTestResult> =>
  apiPost(`/notifications/providers/${id}/test`);

// ─── deliveries ──────────────────────────────────────────────────────────
function qs(filters: DeliveryFilters): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(filters)) {
    if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

export const listDeliveries = (
  filters: DeliveryFilters = {},
): Promise<NotificationDeliveryPage> =>
  apiGet(`/notifications/deliveries${qs(filters)}`);

export const getDelivery = (id: string): Promise<NotificationDeliveryDetail> =>
  apiGet(`/notifications/deliveries/${id}`);

export const retryDelivery = (id: string): Promise<{ status: string }> =>
  apiPost(`/notifications/deliveries/${id}/retry`);
