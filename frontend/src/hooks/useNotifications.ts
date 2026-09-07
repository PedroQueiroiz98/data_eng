import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getJobNotifications,
  getNotificationSettings,
  getWorkflowNotifications,
  putNotificationSettings,
  putWorkflowNotifications,
  retryNotification,
  type NotificationConfigInput,
  type NotificationSettingsInput,
} from "@/lib/notifications";

export function useWorkflowNotifications(workflowId: string, enabled = true) {
  return useQuery({
    queryKey: ["workflow-notifications", workflowId],
    queryFn: () => getWorkflowNotifications(workflowId),
    enabled: enabled && !!workflowId,
  });
}

export function useSaveWorkflowNotifications(workflowId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: NotificationConfigInput) => putWorkflowNotifications(workflowId, body),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["workflow-notifications", workflowId] }),
  });
}

export function useNotificationSettings(enabled = true) {
  return useQuery({
    queryKey: ["notification-settings"],
    queryFn: getNotificationSettings,
    enabled,
  });
}

export function useSaveNotificationSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: NotificationSettingsInput) => putNotificationSettings(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notification-settings"] }),
  });
}

export function useJobNotifications(jobId: string, enabled = true) {
  return useQuery({
    queryKey: ["job-notifications", jobId],
    queryFn: () => getJobNotifications(jobId),
    enabled: enabled && !!jobId,
    refetchInterval: 5000,
  });
}

export function useRetryNotification(jobId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => retryNotification(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["job-notifications", jobId] }),
  });
}
