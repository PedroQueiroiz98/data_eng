import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  useCreateSchedule,
  useDeleteSchedule,
  useSchedules,
  useUpdateSchedule,
} from "@/hooks/useSchedules";
import { useWorkflows } from "@/hooks/useWorkflows";
import { runWorkflow } from "@/lib/jobs";
import type { Schedule } from "@/lib/schedules";
import {
  buildCron,
  DEFAULT_PARTS,
  describeCron,
  isValidCron,
  occurrencesInMonth,
  type FreqParts,
  type Frequency,
} from "@/lib/cron";
import {
  ActionMenu,
  Button,
  Column,
  DataTable,
  Dialog,
  EmptyState,
  IconButton,
  PageHeader,
  SelectField,
  StatusChip,
  Switch,
  TextField,
  useConfirm,
  useToast,
} from "@/ui";
import {
  AddIcon,
  BackIcon,
  ChevronRightIcon,
  DeleteIcon,
  EditIcon,
  PauseIcon,
  RunIcon,
  ScheduleIcon,
} from "@/ui/icons";

const FREQS: { value: Frequency; label: string }[] = [
  { value: "once", label: "Uma vez" },
  { value: "hourly", label: "De hora em hora" },
  { value: "daily", label: "Diariamente" },
  { value: "weekly", label: "Semanalmente" },
  { value: "monthly", label: "Mensalmente" },
  { value: "custom", label: "Cron personalizado" },
];
const WEEKDAYS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];

// ─── formulário (dialog) ─────────────────────────────────────────────────────

interface FormState {
  workflowId: string;
  freq: Frequency;
  parts: FreqParts;
  cron: string;
  timezone: string;
  enabled: boolean;
}

function ScheduleFormDialog({
  open,
  onClose,
  initial,
  workflows,
  onSubmit,
  saving,
}: {
  open: boolean;
  onClose: () => void;
  initial?: Partial<FormState>;
  workflows: { id: string; name: string }[];
  onSubmit: (s: FormState) => void;
  saving: boolean;
}) {
  const [s, setS] = useState<FormState>({
    workflowId: "",
    freq: "daily",
    parts: { ...DEFAULT_PARTS },
    cron: "0 9 * * *",
    timezone: "America/Sao_Paulo",
    enabled: true,
    ...initial,
  });

  const effectiveCron = s.freq === "custom" ? s.cron : buildCron(s.freq, s.parts);
  const set = (patch: Partial<FormState>) => setS((prev) => ({ ...prev, ...patch }));
  const setPart = (patch: Partial<FreqParts>) =>
    setS((prev) => ({ ...prev, parts: { ...prev.parts, ...patch } }));

  const valid = s.workflowId && isValidCron(effectiveCron);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={initial?.workflowId ? "Editar agendamento" : "Novo agendamento"}
      footer={
        <>
          <Button variant="text" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            loading={saving}
            disabled={!valid}
            onClick={() => onSubmit({ ...s, cron: effectiveCron })}
          >
            Salvar
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <SelectField
          label="Workflow"
          value={s.workflowId}
          onChange={(e) => set({ workflowId: e.target.value })}
        >
          <option value="">Selecione…</option>
          {workflows.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
        </SelectField>

        <SelectField
          label="Frequência"
          value={s.freq}
          onChange={(e) => set({ freq: e.target.value as Frequency })}
        >
          {FREQS.map((f) => (
            <option key={f.value} value={f.value}>
              {f.label}
            </option>
          ))}
        </SelectField>

        {s.freq === "custom" ? (
          <TextField
            label="Expressão cron (5 campos)"
            mono
            value={s.cron}
            onChange={(e) => set({ cron: e.target.value })}
            error={isValidCron(s.cron) ? undefined : "Cron inválido"}
          />
        ) : (
          <div className="grid grid-cols-2 gap-3">
            {s.freq === "hourly" ? (
              <TextField
                label="Minuto"
                type="number"
                min={0}
                max={59}
                value={s.parts.minute}
                onChange={(e) => setPart({ minute: Number(e.target.value) || 0 })}
              />
            ) : (
              <TextField
                label="Horário"
                type="time"
                value={s.parts.time}
                onChange={(e) => setPart({ time: e.target.value })}
              />
            )}
            {s.freq === "weekly" && (
              <SelectField
                label="Dia da semana"
                value={s.parts.weekday}
                onChange={(e) => setPart({ weekday: Number(e.target.value) })}
              >
                {WEEKDAYS.map((d, i) => (
                  <option key={i} value={i}>
                    {d}
                  </option>
                ))}
              </SelectField>
            )}
            {(s.freq === "monthly" || s.freq === "once") && (
              <TextField
                label="Dia do mês"
                type="number"
                min={1}
                max={31}
                value={s.parts.monthday}
                onChange={(e) => setPart({ monthday: Number(e.target.value) || 1 })}
              />
            )}
            {s.freq === "once" && (
              <TextField
                label="Mês"
                type="number"
                min={1}
                max={12}
                value={s.parts.month}
                onChange={(e) => setPart({ month: Number(e.target.value) || 1 })}
              />
            )}
          </div>
        )}

        <div className="rounded-md bg-surface-variant px-3 py-2 text-xs text-slate-600">
          <span className="font-medium">{describeCron(effectiveCron)}</span>
          <span className="ml-2 font-mono text-slate-400">→ {effectiveCron}</span>
        </div>

        <TextField
          label="Timezone"
          value={s.timezone}
          onChange={(e) => set({ timezone: e.target.value })}
        />

        <Switch checked={s.enabled} onChange={(v) => set({ enabled: v })} label="Ativo" />
      </div>
    </Dialog>
  );
}

// ─── calendário ─────────────────────────────────────────────────────────────

interface CalEvent {
  schedule: Schedule;
  date: Date;
}

function ScheduleCalendar({
  schedules,
  wfName,
  onSelect,
}: {
  schedules: Schedule[];
  wfName: (id: string) => string;
  onSelect: (s: Schedule) => void;
}) {
  const [cursor, setCursor] = useState(() => {
    const n = new Date();
    return { y: n.getFullYear(), m: n.getMonth() };
  });

  const events = useMemo<CalEvent[]>(() => {
    const out: CalEvent[] = [];
    for (const s of schedules) {
      if (!s.enabled) continue;
      for (const date of occurrencesInMonth(s.cron, s.timezone, cursor.y, cursor.m)) {
        out.push({ schedule: s, date });
      }
    }
    return out.sort((a, b) => a.date.getTime() - b.date.getTime());
  }, [schedules, cursor]);

  const byDay = useMemo(() => {
    const map = new Map<number, CalEvent[]>();
    for (const e of events) {
      const day = e.date.getDate();
      if (!map.has(day)) map.set(day, []);
      map.get(day)!.push(e);
    }
    return map;
  }, [events]);

  const first = new Date(cursor.y, cursor.m, 1);
  const daysInMonth = new Date(cursor.y, cursor.m + 1, 0).getDate();
  const leading = first.getDay();
  const cells: (number | null)[] = [
    ...Array.from({ length: leading }, () => null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];
  while (cells.length % 7 !== 0) cells.push(null);

  const monthLabel = first.toLocaleDateString("pt-BR", { month: "long", year: "numeric" });
  const today = new Date();
  const isToday = (d: number) =>
    today.getFullYear() === cursor.y && today.getMonth() === cursor.m && today.getDate() === d;

  return (
    <div className="surface p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold capitalize text-slate-700">{monthLabel}</h2>
        <div className="flex gap-1">
          <IconButton
            label="Mês anterior"
            size="sm"
            icon={<BackIcon className="h-4 w-4" />}
            onClick={() =>
              setCursor((c) => (c.m === 0 ? { y: c.y - 1, m: 11 } : { ...c, m: c.m - 1 }))
            }
          />
          <IconButton
            label="Próximo mês"
            size="sm"
            icon={<ChevronRightIcon className="h-4 w-4" />}
            onClick={() =>
              setCursor((c) => (c.m === 11 ? { y: c.y + 1, m: 0 } : { ...c, m: c.m + 1 }))
            }
          />
        </div>
      </div>

      <div className="grid grid-cols-7 gap-px overflow-hidden rounded border border-surface-border bg-surface-border text-xs">
        {WEEKDAYS.map((d) => (
          <div key={d} className="bg-surface-variant px-2 py-1.5 text-center font-medium text-slate-500">
            {d}
          </div>
        ))}
        {cells.map((day, i) => (
          <div
            key={i}
            className={`min-h-[92px] bg-surface p-1.5 ${day == null ? "opacity-40" : ""}`}
          >
            {day != null && (
              <>
                <div
                  className={`mb-1 text-right text-[11px] ${
                    isToday(day)
                      ? "inline-block rounded-full bg-primary px-1.5 text-primary-fg"
                      : "text-slate-400"
                  }`}
                >
                  {day}
                </div>
                <div className="space-y-1">
                  {(byDay.get(day) ?? []).slice(0, 3).map((e, j) => (
                    <button
                      key={j}
                      type="button"
                      onClick={() => onSelect(e.schedule)}
                      className="block w-full truncate rounded bg-primary-container px-1.5 py-0.5 text-left text-[11px] text-primary-on-container hover:brightness-95"
                      title={`${wfName(e.schedule.workflow_id)} · ${e.date.toLocaleTimeString()}`}
                    >
                      {e.date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}{" "}
                      {wfName(e.schedule.workflow_id)}
                    </button>
                  ))}
                  {(byDay.get(day)?.length ?? 0) > 3 && (
                    <div className="text-[10px] text-slate-400">
                      +{(byDay.get(day)!.length - 3)} mais
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── página ─────────────────────────────────────────────────────────────────

export function Schedules() {
  const navigate = useNavigate();
  const toast = useToast();
  const confirm = useConfirm();
  const { data: schedules, isLoading, isError } = useSchedules();
  const { data: workflows } = useWorkflows();
  const create = useCreateSchedule();
  const update = useUpdateSchedule();
  const remove = useDeleteSchedule();

  const [tab, setTab] = useState<"calendar" | "list">("calendar");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Schedule | null>(null);
  const [detail, setDetail] = useState<Schedule | null>(null);

  const wfList = workflows ?? [];
  const wfName = (id: string) => wfList.find((w) => w.id === id)?.name ?? id.slice(0, 8);

  const openCreate = () => {
    setEditing(null);
    setFormOpen(true);
  };
  const openEdit = (s: Schedule) => {
    setDetail(null);
    setEditing(s);
    setFormOpen(true);
  };

  const submit = (f: FormState) => {
    if (editing) {
      update.mutate(
        { id: editing.id, cron: f.cron, timezone: f.timezone, enabled: f.enabled },
        {
          onSuccess: () => {
            toast.success("Agendamento atualizado");
            setFormOpen(false);
          },
          onError: (e) => toast.error((e as Error).message),
        },
      );
    } else {
      create.mutate(
        { workflow_id: f.workflowId, cron: f.cron, timezone: f.timezone, enabled: f.enabled },
        {
          onSuccess: () => {
            toast.success("Agendamento criado");
            setFormOpen(false);
          },
          onError: (e) => toast.error((e as Error).message),
        },
      );
    }
  };

  const toggle = (s: Schedule) =>
    update.mutate(
      { id: s.id, enabled: !s.enabled },
      {
        onSuccess: () => toast.success(s.enabled ? "Agendamento pausado" : "Agendamento ativado"),
        onError: (e) => toast.error((e as Error).message),
      },
    );

  const del = async (s: Schedule) => {
    if (
      await confirm({
        title: "Excluir agendamento",
        message: `Excluir o agendamento de "${wfName(s.workflow_id)}"?`,
        confirmLabel: "Excluir",
        danger: true,
      })
    ) {
      remove.mutate(s.id, {
        onSuccess: () => {
          toast.success("Agendamento excluído");
          setDetail(null);
        },
        onError: (e) => toast.error((e as Error).message),
      });
    }
  };

  const runNow = async (s: Schedule) => {
    try {
      const job = await runWorkflow(s.workflow_id, {});
      toast.success("Execução iniciada");
      navigate(`/jobs/${job.id}`);
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const columns: Column<Schedule>[] = [
    {
      key: "workflow",
      header: "Workflow",
      sortValue: (s) => wfName(s.workflow_id),
      render: (s) => <span className="font-medium text-slate-800">{wfName(s.workflow_id)}</span>,
    },
    {
      key: "freq",
      header: "Frequência",
      sortValue: (s) => s.cron,
      render: (s) => (
        <div>
          <div className="text-slate-700">{describeCron(s.cron)}</div>
          <div className="font-mono text-[11px] text-slate-400">
            {s.cron} · {s.timezone}
          </div>
        </div>
      ),
    },
    {
      key: "next",
      header: "Próxima execução",
      sortValue: (s) => s.next_run_at ?? "",
      render: (s) => (
        <span className="text-slate-500">
          {s.next_run_at ? new Date(s.next_run_at).toLocaleString() : "—"}
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      sortValue: (s) => String(s.enabled),
      render: (s) => <StatusChip status={s.enabled ? "ENABLED" : "DISABLED"} />,
    },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (s) => (
        <div className="flex items-center justify-end gap-0.5">
          <IconButton
            label="Executar agora"
            size="sm"
            icon={<RunIcon className="h-4 w-4" />}
            onClick={(e) => {
              e.stopPropagation();
              void runNow(s);
            }}
          />
          <IconButton
            label="Editar"
            size="sm"
            icon={<EditIcon className="h-4 w-4" />}
            onClick={(e) => {
              e.stopPropagation();
              openEdit(s);
            }}
          />
          <ActionMenu
            items={[
              {
                label: s.enabled ? "Pausar" : "Ativar",
                icon: <PauseIcon className="h-4 w-4" />,
                onClick: () => toggle(s),
              },
              {
                label: "Excluir",
                icon: <DeleteIcon className="h-4 w-4" />,
                danger: true,
                onClick: () => void del(s),
              },
            ]}
          />
        </div>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Agendamentos"
        subtitle="Execuções automáticas de workflows (cron)."
        actions={
          <Button icon={<AddIcon className="h-4 w-4" />} onClick={openCreate}>
            Novo Agendamento
          </Button>
        }
      />

      <div className="mb-4 inline-flex rounded-md border border-surface-border bg-surface p-0.5 text-sm">
        {(["calendar", "list"] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`inline-flex items-center gap-1.5 rounded px-3 py-1.5 ${
              tab === t ? "bg-primary-container text-primary-on-container" : "text-slate-500"
            }`}
          >
            <ScheduleIcon className="h-4 w-4" />
            {t === "calendar" ? "Calendário" : "Lista"}
          </button>
        ))}
      </div>

      {isError ? (
        <p className="text-sm text-red-600">Falha ao carregar agendamentos.</p>
      ) : isLoading ? (
        <p className="text-sm text-slate-400">Carregando…</p>
      ) : (schedules ?? []).length === 0 ? (
        <EmptyState
          icon={ScheduleIcon}
          title="Nenhum agendamento"
          description="Crie um agendamento para executar um workflow automaticamente."
          action={
            <Button icon={<AddIcon className="h-4 w-4" />} onClick={openCreate}>
              Criar Agendamento
            </Button>
          }
        />
      ) : tab === "calendar" ? (
        <ScheduleCalendar
          schedules={schedules ?? []}
          wfName={wfName}
          onSelect={(s) => setDetail(s)}
        />
      ) : (
        <DataTable
          columns={columns}
          rows={schedules}
          rowKey={(s) => s.id}
          onRowClick={(s) => setDetail(s)}
        />
      )}

      {/* detalhe do agendamento */}
      <Dialog
        open={detail !== null}
        onClose={() => setDetail(null)}
        title="Detalhes do agendamento"
        footer={
          detail && (
            <>
              <Button
                variant="outlined"
                size="sm"
                icon={<PauseIcon className="h-4 w-4" />}
                onClick={() => detail && toggle(detail)}
              >
                {detail.enabled ? "Pausar" : "Ativar"}
              </Button>
              <Button
                variant="outlined"
                size="sm"
                icon={<EditIcon className="h-4 w-4" />}
                onClick={() => detail && openEdit(detail)}
              >
                Editar
              </Button>
              <Button
                size="sm"
                icon={<RunIcon className="h-4 w-4" />}
                onClick={() => detail && runNow(detail)}
              >
                Executar agora
              </Button>
            </>
          )
        }
      >
        {detail && (
          <dl className="space-y-2 text-sm">
            <Row label="Workflow" value={wfName(detail.workflow_id)} />
            <Row label="Frequência" value={describeCron(detail.cron)} />
            <Row label="Cron" value={<code className="font-mono text-xs">{detail.cron}</code>} />
            <Row label="Timezone" value={detail.timezone} />
            <Row
              label="Próxima execução"
              value={detail.next_run_at ? new Date(detail.next_run_at).toLocaleString() : "—"}
            />
            <Row
              label="Última execução"
              value={detail.last_run_at ? new Date(detail.last_run_at).toLocaleString() : "—"}
            />
            <Row
              label="Status"
              value={<StatusChip status={detail.enabled ? "ENABLED" : "DISABLED"} />}
            />
          </dl>
        )}
      </Dialog>

      {formOpen && (
        <ScheduleFormDialog
          open={formOpen}
          onClose={() => setFormOpen(false)}
          workflows={wfList}
          saving={create.isPending || update.isPending}
          onSubmit={submit}
          initial={
            editing
              ? {
                  workflowId: editing.workflow_id,
                  freq: "custom",
                  cron: editing.cron,
                  timezone: editing.timezone,
                  enabled: editing.enabled,
                }
              : undefined
          }
        />
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-slate-400">{label}</dt>
      <dd className="text-right text-slate-700">{value}</dd>
    </div>
  );
}
