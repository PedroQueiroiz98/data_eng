import { useMemo, useState } from "react";
import {
  useCreateSchedule,
  useDeleteSchedule,
  useSchedules,
  useUpdateSchedule,
} from "@/hooks/useSchedules";
import { buildCron, describeCron, type Frequency } from "@/lib/cron";
import { Button, Switch, useToast } from "@/ui";
import { DeleteIcon, ScheduleIcon } from "@/ui/icons";

const FREQS: { id: Frequency; label: string }[] = [
  { id: "daily", label: "Diário" },
  { id: "weekly", label: "Semanal" },
  { id: "hourly", label: "De hora em hora" },
  { id: "custom", label: "Cron manual" },
];
const WEEKDAYS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];

export function SchedulePanel({ workflowId }: { workflowId: string }) {
  const toast = useToast();
  const schedules = useSchedules();
  const create = useCreateSchedule();
  const update = useUpdateSchedule();
  const del = useDeleteSchedule();

  const mine = useMemo(
    () => (schedules.data ?? []).filter((s) => s.workflow_id === workflowId),
    [schedules.data, workflowId],
  );

  const [freq, setFreq] = useState<Frequency>("daily");
  const [time, setTime] = useState("02:00");
  const [weekday, setWeekday] = useState(1);
  const [rawCron, setRawCron] = useState("0 2 * * *");
  const [tz, setTz] = useState("America/Sao_Paulo");

  const cron =
    freq === "custom"
      ? rawCron
      : buildCron(freq, {
          time,
          weekday,
          monthday: 1,
          month: 1,
          minute: 0,
        });

  const add = () => {
    create.mutate(
      { workflow_id: workflowId, cron, timezone: tz, enabled: true },
      {
        onSuccess: () => toast.success("Agendamento criado"),
        onError: (e) => toast.error((e as Error).message),
      },
    );
  };

  return (
    <div className="space-y-3 text-sm">
      <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-fg-faint">
        <ScheduleIcon className="h-3.5 w-3.5" /> Agendamento
      </div>

      {mine.length === 0 && (
        <p className="text-xs text-fg-muted">Nenhum agendamento para este workflow.</p>
      )}
      {mine.map((s) => (
        <div
          key={s.id}
          className="rounded border border-surface-border p-2 text-xs"
        >
          <div className="font-medium">{describeCron(s.cron)}</div>
          <div className="text-fg-faint">
            {s.cron} · {s.timezone}
          </div>
          <div className="text-fg-faint">
            Próxima:{" "}
            {s.next_run_at ? new Date(s.next_run_at).toLocaleString("pt-BR") : "—"}
          </div>
          <div className="mt-1 flex items-center gap-2">
            <Switch
              checked={s.enabled}
              onChange={(v) => update.mutate({ id: s.id, enabled: v })}
              label={s.enabled ? "Ativo" : "Pausado"}
            />
            <button
              type="button"
              className="ml-auto text-fg-faint hover:text-danger"
              title="Excluir"
              onClick={() => del.mutate(s.id)}
            >
              <DeleteIcon className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      ))}

      <div className="space-y-2 rounded border border-dashed border-surface-border p-2">
        <select
          value={freq}
          onChange={(e) => setFreq(e.target.value as Frequency)}
          className="w-full rounded border border-surface-border bg-surface px-2 py-1 text-xs"
        >
          {FREQS.map((f) => (
            <option key={f.id} value={f.id}>
              {f.label}
            </option>
          ))}
        </select>
        {freq === "custom" ? (
          <input
            value={rawCron}
            onChange={(e) => setRawCron(e.target.value)}
            placeholder="m h dom mês dia-sem"
            className="w-full rounded border border-surface-border bg-surface px-2 py-1 font-mono text-xs"
          />
        ) : (
          <div className="flex gap-2">
            {freq !== "hourly" && (
              <input
                type="time"
                value={time}
                onChange={(e) => setTime(e.target.value)}
                className="rounded border border-surface-border bg-surface px-2 py-1 text-xs"
              />
            )}
            {freq === "weekly" && (
              <select
                value={weekday}
                onChange={(e) => setWeekday(Number(e.target.value))}
                className="rounded border border-surface-border bg-surface px-2 py-1 text-xs"
              >
                {WEEKDAYS.map((d, i) => (
                  <option key={i} value={i}>
                    {d}
                  </option>
                ))}
              </select>
            )}
          </div>
        )}
        <input
          value={tz}
          onChange={(e) => setTz(e.target.value)}
          className="w-full rounded border border-surface-border bg-surface px-2 py-1 text-xs"
        />
        <div className="text-[11px] text-fg-faint">
          {describeCron(cron)} · <span className="font-mono">{cron}</span>
        </div>
        <Button
          size="sm"
          loading={create.isPending}
          onClick={add}
        >
          Adicionar agendamento
        </Button>
      </div>
    </div>
  );
}
