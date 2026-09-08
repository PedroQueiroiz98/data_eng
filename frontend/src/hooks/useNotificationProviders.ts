import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createProvider,
  deleteProvider,
  getDelivery,
  getProvider,
  listDeliveries,
  listProviders,
  retryDelivery,
  setProviderEnabled,
  testProvider,
  updateProvider,
  type DeliveryFilters,
  type NotificationProviderInput,
} from "@/lib/notificationProviders";

const PROVIDERS_KEY = ["notification-providers"];
const DELIVERIES_KEY = ["notification-deliveries"];

export function useNotificationProviders() {
  return useQuery({ queryKey: PROVIDERS_KEY, queryFn: listProviders });
}

export function useNotificationProvider(id: string, enabled = true) {
  return useQuery({
    queryKey: [...PROVIDERS_KEY, id],
    queryFn: () => getProvider(id),
    enabled: enabled && !!id,
  });
}

export function useCreateNotificationProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: NotificationProviderInput) => createProvider(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: PROVIDERS_KEY }),
  });
}

export function useUpdateNotificationProvider(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<NotificationProviderInput>) => updateProvider(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: PROVIDERS_KEY }),
  });
}

export function useDeleteNotificationProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteProvider(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: PROVIDERS_KEY }),
  });
}

export function useToggleNotificationProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      setProviderEnabled(id, enabled),
    onSuccess: () => qc.invalidateQueries({ queryKey: PROVIDERS_KEY }),
  });
}

export function useTestNotificationProvider() {
  return useMutation({ mutationFn: (id: string) => testProvider(id) });
}

export function useNotificationDeliveries(filters: DeliveryFilters, enabled = true) {
  return useQuery({
    queryKey: [...DELIVERIES_KEY, filters],
    queryFn: () => listDeliveries(filters),
    enabled,
    refetchInterval: 5000,
  });
}

export function useNotificationDelivery(id: string | null) {
  return useQuery({
    queryKey: [...DELIVERIES_KEY, "detail", id],
    queryFn: () => getDelivery(id as string),
    enabled: !!id,
  });
}

export function useRetryNotificationDelivery() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => retryDelivery(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: DELIVERIES_KEY }),
  });
}
