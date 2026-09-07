import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { bulkFailureReport } from "@/components/bulkReport";
import { useCreateNotebook, useDeleteNotebook, useNotebooks } from "@/hooks/useNotebooks";
import { bulkRun, bulkSuccessMessage } from "@/lib/bulk";
import { executeNotebook } from "@/lib/executions";
import { deleteNotebook, type Notebook } from "@/lib/notebooks";
import {
  ActionMenu,
  Button,
  Column,
  DataTable,
  Dialog,
  EmptyState,
  IconButton,
  PageHeader,
  TextField,
  useAlert,
  useConfirm,
  useToast,
} from "@/ui";
import {
  AddIcon,
  DeleteIcon,
  EditIcon,
  NotebookIcon,
  RunIcon,
  ScheduleIcon,
} from "@/ui/icons";

export function Notebooks() {
  const navigate = useNavigate();
  const toast = useToast();
  const confirm = useConfirm();
  const alert = useAlert();
  const qc = useQueryClient();
  const { data: notebooks, isLoading, isError } = useNotebooks();
  const create = useCreateNotebook();
  const remove = useDeleteNotebook();
  const [bulkBusy, setBulkBusy] = useState(false);

  const nameOf = (id: string) =>
    notebooks?.find((n) => n.id === id)?.name ?? id.slice(0, 8);

  const bulkDelete = async (ids: string[], clear: () => void) => {
    if (
      !(await confirm({
        title: "Excluir notebooks",
        message: `Excluir ${ids.length} notebook(s) e todas as suas versões? Esta ação não pode ser desfeita.`,
        confirmLabel: "Excluir",
        danger: true,
      }))
    )
      return;
    setBulkBusy(true);
    const res = await bulkRun(ids, deleteNotebook);
    setBulkBusy(false);
    await qc.invalidateQueries({ queryKey: ["notebooks"] });
    clear();
    if (res.ok > 0) toast.success(bulkSuccessMessage(res.ok, "notebook"));
    if (res.failed > 0) await alert(bulkFailureReport(res, ids.length, "notebooks", nameOf));
  };

  const [dialog, setDialog] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const submit = async () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    const nb = await create.mutateAsync({ name: trimmed, description: description.trim() || undefined });
    toast.success("Notebook criado");
    setDialog(false);
    setName("");
    setDescription("");
    navigate(`/notebooks/${nb.id}`);
  };

  const run = async (nb: Notebook) => {
    try {
      const ex = await executeNotebook(nb.id, { parameters: {} });
      toast.success("Execução iniciada");
      navigate(`/executions/${ex.id}`);
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const del = async (nb: Notebook) => {
    if (await confirm({
      title: "Excluir notebook",
      message: `Excluir "${nb.name}" e todas as suas versões? Esta ação não pode ser desfeita.`,
      confirmLabel: "Excluir",
      danger: true,
    })) {
      remove.mutate(nb.id, {
        onSuccess: () => toast.success("Notebook excluído"),
        onError: (e) => toast.error((e as Error).message),
      });
    }
  };

  const columns: Column<Notebook>[] = [
    {
      key: "name",
      header: "Nome",
      sortValue: (n) => n.name,
      render: (n) => (
        <div>
          <div className="font-medium text-fg">{n.name}</div>
          {n.description && (
            <div className="text-xs text-fg-muted">{n.description}</div>
          )}
        </div>
      ),
    },
    {
      key: "version",
      header: "Versão",
      sortValue: (n) => n.current_version,
      render: (n) => <span className="tabular-nums text-fg-muted">v{n.current_version}</span>,
    },
    {
      key: "updated",
      header: "Atualizado",
      sortValue: (n) => n.updated_at,
      render: (n) => (
        <span className="text-fg-muted">{new Date(n.updated_at).toLocaleString()}</span>
      ),
    },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (n) => (
        <div className="flex items-center justify-end gap-0.5">
          <IconButton
            label="Editar notebook"
            size="sm"
            icon={<EditIcon className="h-4 w-4" />}
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/notebooks/${n.id}`);
            }}
          />
          <IconButton
            label="Executar agora"
            size="sm"
            icon={<RunIcon className="h-4 w-4" />}
            onClick={(e) => {
              e.stopPropagation();
              void run(n);
            }}
          />
          <ActionMenu
            items={[
              {
                label: "Agendar execução",
                icon: <ScheduleIcon className="h-4 w-4" />,
                onClick: () => navigate("/schedules"),
              },
              {
                label: "Excluir",
                icon: <DeleteIcon className="h-4 w-4" />,
                danger: true,
                onClick: () => void del(n),
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
        title="Notebooks"
        subtitle="Notebooks Python versionados, executados via Papermill."
        actions={
          <Button icon={<AddIcon className="h-4 w-4" />} onClick={() => setDialog(true)}>
            Novo Notebook
          </Button>
        }
      />

      {isError ? (
        <p className="text-sm text-danger">Falha ao carregar notebooks.</p>
      ) : (
        <DataTable
          columns={columns}
          rows={notebooks}
          rowKey={(n) => n.id}
          loading={isLoading}
          onRowClick={(n) => navigate(`/notebooks/${n.id}`)}
          searchPlaceholder="Pesquisar notebooks"
          selectable
          bulkActions={(ids, clear) => (
            <Button
              size="sm"
              variant="danger"
              loading={bulkBusy}
              icon={<DeleteIcon className="h-4 w-4" />}
              onClick={() => void bulkDelete(ids, clear)}
            >
              Excluir {ids.length}
            </Button>
          )}
          empty={
            <EmptyState
              icon={NotebookIcon}
              title="Nenhum notebook encontrado"
              description="Crie seu primeiro notebook para começar."
              action={
                <Button icon={<AddIcon className="h-4 w-4" />} onClick={() => setDialog(true)}>
                  Criar Notebook
                </Button>
              }
            />
          }
        />
      )}

      <Dialog
        open={dialog}
        onClose={() => setDialog(false)}
        title="Novo notebook"
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
        <div className="space-y-3">
          <TextField
            label="Nome"
            value={name}
            autoFocus
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
          />
          <TextField
            label="Descrição (opcional)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>
      </Dialog>
    </div>
  );
}
