import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCreateWorkflow, useDeleteWorkflow, useWorkflows } from "@/hooks/useWorkflows";
import { runWorkflow } from "@/lib/jobs";
import type { Workflow } from "@/lib/workflows";
import {
  ActionMenu,
  Button,
  Column,
  DataTable,
  Dialog,
  EmptyState,
  IconButton,
  PageHeader,
  StatusChip,
  TextField,
  useConfirm,
  useToast,
} from "@/ui";
import { AddIcon, DeleteIcon, EditIcon, RunIcon, WorkflowIcon } from "@/ui/icons";

export function Workflows() {
  const navigate = useNavigate();
  const toast = useToast();
  const confirm = useConfirm();
  const { data, isLoading, isError } = useWorkflows();
  const create = useCreateWorkflow();
  const remove = useDeleteWorkflow();

  const [dialog, setDialog] = useState(false);
  const [name, setName] = useState("");

  const submit = async () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    const wf = await create.mutateAsync({ name: trimmed });
    toast.success("Workflow criado");
    setDialog(false);
    setName("");
    navigate(`/workflows/${wf.id}`);
  };

  const run = async (wf: Workflow) => {
    try {
      const job = await runWorkflow(wf.id, {});
      toast.success("Job iniciado");
      navigate(`/jobs/${job.id}`);
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const del = async (wf: Workflow) => {
    if (
      await confirm({
        title: "Excluir workflow",
        message: `Excluir "${wf.name}"?`,
        confirmLabel: "Excluir",
        danger: true,
      })
    ) {
      remove.mutate(wf.id, {
        onSuccess: () => toast.success("Workflow excluído"),
        onError: (e) => toast.error((e as Error).message),
      });
    }
  };

  const columns: Column<Workflow>[] = [
    {
      key: "name",
      header: "Nome",
      sortValue: (w) => w.name,
      render: (w) => <span className="font-medium text-fg">{w.name}</span>,
    },
    {
      key: "status",
      header: "Status",
      sortValue: (w) => w.status,
      render: (w) => <StatusChip status={w.status} />,
    },
    {
      key: "updated",
      header: "Atualizado",
      sortValue: (w) => w.updated_at,
      render: (w) => (
        <span className="text-fg-muted">{new Date(w.updated_at).toLocaleString()}</span>
      ),
    },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (w) => (
        <div className="flex items-center justify-end gap-0.5">
          <IconButton
            label="Editar workflow"
            size="sm"
            icon={<EditIcon className="h-4 w-4" />}
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/workflows/${w.id}`);
            }}
          />
          <IconButton
            label="Executar workflow"
            size="sm"
            icon={<RunIcon className="h-4 w-4" />}
            onClick={(e) => {
              e.stopPropagation();
              void run(w);
            }}
          />
          <ActionMenu
            items={[
              {
                label: "Excluir",
                icon: <DeleteIcon className="h-4 w-4" />,
                danger: true,
                onClick: () => void del(w),
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
        title="Workflows"
        subtitle="Pipelines DAG de notebooks."
        actions={
          <Button icon={<AddIcon className="h-4 w-4" />} onClick={() => setDialog(true)}>
            Novo Workflow
          </Button>
        }
      />

      {isError ? (
        <p className="text-sm text-danger">Falha ao carregar workflows.</p>
      ) : (
        <DataTable
          columns={columns}
          rows={data}
          rowKey={(w) => w.id}
          loading={isLoading}
          onRowClick={(w) => navigate(`/workflows/${w.id}`)}
          searchPlaceholder="Pesquisar workflows"
          empty={
            <EmptyState
              icon={WorkflowIcon}
              title="Nenhum workflow ainda"
              description="Monte seu primeiro pipeline conectando notebooks."
              action={
                <Button icon={<AddIcon className="h-4 w-4" />} onClick={() => setDialog(true)}>
                  Criar Workflow
                </Button>
              }
            />
          }
        />
      )}

      <Dialog
        open={dialog}
        onClose={() => setDialog(false)}
        title="Novo workflow"
        footer={
          <>
            <Button variant="text" onClick={() => setDialog(false)}>
              Cancelar
            </Button>
            <Button loading={create.isPending} disabled={!name.trim()} onClick={submit}>
              Criar
            </Button>
          </>
        }
      >
        <TextField
          label="Nome"
          value={name}
          autoFocus
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
        />
      </Dialog>
    </div>
  );
}
