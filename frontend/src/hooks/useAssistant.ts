import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { assistantAvailability } from "@/lib/assistant";
import { listAiInteractions } from "@/lib/assistantProviders";
import { useAssistantStore } from "@/store/assistant";

const AVAIL_KEY = ["assistant", "availability"];

/** Consulta a disponibilidade e mantém o store de UI em sincronia. */
export function useAssistantAvailability() {
  const q = useQuery({
    queryKey: AVAIL_KEY,
    queryFn: assistantAvailability,
    staleTime: 60_000,
    refetchInterval: 120_000,
  });
  const setAvailability = useAssistantStore((s) => s.setAvailability);
  useEffect(() => {
    if (q.data) setAvailability(q.data);
  }, [q.data, setAvailability]);
  return q;
}

export function useAiInteractions(params: {
  task?: string;
  notebook_path?: string;
  limit?: number;
}) {
  return useQuery({
    queryKey: ["assistant", "interactions", params],
    queryFn: () => listAiInteractions(params),
  });
}
