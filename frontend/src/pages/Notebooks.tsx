import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCreateNotebook, useDeleteNotebook, useNotebooks } from "@/hooks/useNotebooks";
import { executeNotebook } from "@/lib/executions";
import type { Notebook } from "@/lib/notebooks";
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
  const { data: notebooks, isLoading, isError } = useNotebooks();
  const create = useCreateNotebook();
  const remove = useDeleteNotebook();

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
          <div className="font-medium text-slate-800">{n.name}</div>
          {n.description && (
            <div className="text-xs text-slate-500">{n.description}</div>
          )}
        </div>
      ),
    },
    {
      key: "version",
      header: "Versão",
      sortValue: (n) => n.current_version,
      render: (n) => <span className="tabular-nums text-slate-600">v{n.current_version}</span>,
    },
    {
      key: "updated",
      header: "Atualizado",
      sortValue: (n) => n.updated_at,
      render: (n) => (
        <span className="text-slate-500">{new Date(n.updated_at).toLocaleString()}</span>
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
        <p className="text-sm text-red-600">Falha ao carregar notebooks.</p>
      ) : (
        <DataTable
          columns={columns}
          rows={notebooks}
          rowKey={(n) => n.id}
          loading={isLoading}
          onRowClick={(n) => navigate(`/notebooks/${n.id}`)}
          searchPlaceholder="Pesquisar notebooks"
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
