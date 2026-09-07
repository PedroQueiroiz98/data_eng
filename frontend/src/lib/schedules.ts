import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/api";

export interface Schedule {
  id: string;
  workflow_id: string;
  cron: string;
  timezone: string;
  enabled: boolean;
  parameters: Record<string, unknown>;
  last_run_at: string | null;
  next_run_at: string | null;
  created_at: string;
}

export const listSchedules = (): Promise<Schedule[]> =>
  apiGet<Schedule[]>("/schedules");

export const createSchedule = (body: {
  workflow_id: string;
  cron: string;
  timezone?: string;
  enabled?: boolean;
  parameters?: Record<string, unknown>;
}): Promise<Schedule> => apiPost<Schedule>("/schedules", body);

export const updateSchedule = (
  id: string,
  body: {
    cron?: string;
    timezone?: string;
    enabled?: boolean;
    parameters?: Record<string, unknown>;
  },
): Promise<Schedule> => apiPut<Schedule>(`/schedules/${id}`, body);

export const deleteSchedule = (id: string): Promise<void> =>
  apiDelete(`/schedules/${id}`);
