import { apiGet, apiPost, apiPut } from "@/lib/api";

export type NotificationChannel = "EMAIL" | "BITRIX";
export type NotificationEventType =
  | "JOB_FAILED"
  | "JOB_SUCCESS"
  | "JOB_RETRY"
  | "JOB_CANCELLED"
  | "JOB_STARTED";
export type NotificationStatus = "PENDING" | "SENDING" | "SENT" | "FAILED";

export interface NotificationConfig {
  workflow_id: string;
  on_failure: boolean;
  on_success: boolean;
  on_retry: boolean;
  on_cancelled: boolean;
  on_started: boolean;
  email_enabled: boolean;
  email_recipients: string[];
  email_cc: string[];
  email_bcc: string[];
  email_subject: string | null;
  bitrix_enabled: boolean;
  bitrix_dialog_id: string | null;
}

export type NotificationConfigInput = Omit<NotificationConfig, "workflow_id">;

export interface NotificationSettings {
  email_enabled: boolean;
  smtp_host: string | null;
  smtp_port: number | null;
  smtp_username: string | null;
  smtp_from: string | null;
  smtp_use_tls: boolean;
  smtp_password_masked: string;
  bitrix_enabled: boolean;
  bitrix_url: string | null;
  bitrix_send_message_path: string | null;
  bitrix_bot_id: string | null;
  bitrix_bot_token_masked: string;
  default_on_failure: boolean;
  default_email_recipients: string[];
  default_bitrix_dialog_id: string | null;
}

export interface NotificationSettingsInput {
  email_enabled: boolean;
  smtp_host: string | null;
  smtp_port: number | null;
  smtp_username: string | null;
  smtp_from: string | null;
  smtp_use_tls: boolean;
  smtp_password: string | null;
  bitrix_enabled: boolean;
  bitrix_url: string | null;
  bitrix_send_message_path: string | null;
  bitrix_bot_id: string | null;
  bitrix_bot_token: string | null;
  default_on_failure: boolean;
  default_email_recipients: string[];
  default_bitrix_dialog_id: string | null;
}

export interface NotificationRecord {
  id: string;
  job_id: string;
  execution_id: string | null;
  channel: NotificationChannel;
  event_type: NotificationEventType;
  status: NotificationStatus;
  recipient: string | null;
  attempt: number;
  max_attempts: number;
  error_message: string | null;
  created_at: string;
  sent_at: string | null;
  next_retry_at: string | null;
}

export const SECRET_MASK = "********";

export const getWorkflowNotifications = (workflowId: string): Promise<NotificationConfig> =>
  apiGet(`/workflows/${workflowId}/notifications`);

export const putWorkflowNotifications = (
  workflowId: string,
  body: NotificationConfigInput,
): Promise<NotificationConfig> => apiPut(`/workflows/${workflowId}/notifications`, body);

export const getNotificationSettings = (): Promise<NotificationSettings> =>
  apiGet("/notifications/settings");

export const putNotificationSettings = (
  body: NotificationSettingsInput,
): Promise<NotificationSettings> => apiPut("/notifications/settings", body);

export const getJobNotifications = (jobId: string): Promise<NotificationRecord[]> =>
  apiGet(`/jobs/${jobId}/notifications`);

export const retryNotification = (id: string): Promise<{ status: string }> =>
  apiPost(`/notifications/${id}/retry`);
