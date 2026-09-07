import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthContext } from "@/components/AuthProvider";
import {
  useCreateWorkspace,
  useDeleteWorkspace,
  useWorkspaces,
} from "@/hooks/useWorkspace";
import type { Workspace } from "@/lib/workspace";
import {
  ActionMenu,
  Button,
  Column,
  DataTable,
  Dialog,
  EmptyState,
  PageHeader,
  TextField,
  useConfirm,
  useToast,
} from "@/ui";
import { AddIcon, DeleteIcon, WorkspaceIcon } from "@/ui/icons";

export function Workspaces() {
  const navigate = useNavigate();
  const toast = useToast();
  const confirm = useConfirm();
  const { user } = useAuthContext();
  const isAdmin = user?.role === "admin";

  const { data: workspaces, isLoading, isError } = useWorkspaces();
  const create = useCreateWorkspace();
  const remove = useDeleteWorkspace();

  const [dialog, setDialog] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const submit = async () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    try {
      const ws = await create.mutateAsync({
        name: trimmed,
        description: description.trim() || undefined,
      });
      toast.success("Workspace criado");
      setDialog(false);
      setName("");
      setDescription("");
      navigate(`/workspaces/${ws.id}`);
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const del = async (ws: Workspace) => {
    if (
      await confirm({
        title: "Desativar workspace",
        message: `Desativar "${ws.name}"? Os arquivos são preservados; um admin pode excluir em definitivo depois.`,
        confirmLabel: "Desativar",
        danger: true,
      })
    ) {
      remove.mutate(
        { id: ws.id },
        {
          onSuccess: () => toast.success("Workspace desativado"),
          onError: (e) => toast.error((e as Error).message),
        },
      );
    }
  };

  const columns: Column<Workspace>[] = [
    {
      key: "name",
      header: "Nome",
      sortValue: (w) => w.name,
      render: (w) => (
        <div>
          <div className="font-medium text-fg">{w.name}</div>
          <div className="text-xs text-fg-muted">
            {w.slug}
            {w.description ? ` — ${w.description}` : ""}
          </div>
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      sortValue: (w) => (w.is_active ? 0 : 1),
      render: (w) => (
        <span className={w.is_active ? "text-fg-muted" : "text-danger"}>
          {w.is_active ? "Ativo" : "Inativo"}
        </span>
      ),
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
      render: (w) =>
        isAdmin ? (
          <ActionMenu
            items={[
              {
                label: "Desativar",
                icon: <DeleteIcon className="h-4 w-4" />,
                danger: true,
                onClick: () => void del(w),
              },
            ]}
          />
        ) : null,
    },
  ];

  return (
    <div>
      <PageHeader
        title="Workspaces"
        subtitle="Ambientes isolados com arquivos, notebooks, Git e execução."
        actions={
          isAdmin ? (
            <Button icon={<AddIcon className="h-4 w-4" />} onClick={() => setDialog(true)}>
              Novo Workspace
            </Button>
          ) : undefined
        }
      />

      {isError ? (
        <p className="text-sm text-danger">Falha ao carregar workspaces.</p>
      ) : (
        <DataTable
          columns={columns}
          rows={workspaces}
          rowKey={(w) => w.id}
          loading={isLoading}
          onRowClick={(w) => navigate(`/workspaces/${w.id}`)}
          searchPlaceholder="Pesquisar workspaces"
          empty={
            <EmptyState
              icon={WorkspaceIcon}
              title="Nenhum workspace"
              description={
                isAdmin
                  ? "Crie um workspace para começar."
                  : "Peça a um administrador para criar um workspace."
              }
              action={
                isAdmin ? (
                  <Button
                    icon={<AddIcon className="h-4 w-4" />}
                    onClick={() => setDialog(true)}
                  >
                    Criar Workspace
                  </Button>
                ) : undefined
              }
            />
          }
        />
      )}

      <Dialog
        open={dialog}
        onClose={() => setDialog(false)}
        title="Novo workspace"
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
