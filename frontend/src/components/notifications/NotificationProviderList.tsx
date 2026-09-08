import { useState } from "react";
import {
  ActionMenu,
  Button,
  Column,
  DataTable,
  EmptyState,
  IconButton,
  StatusChip,
  useConfirm,
  useToast,
} from "@/ui";
import { AddIcon, BellIcon, DeleteIcon, EditIcon, PauseIcon, RunIcon, SendIcon } from "@/ui/icons";
import {
  useDeleteNotificationProvider,
  useNotificationProviders,
  useTestNotificationProvider,
  useToggleNotificationProvider,
} from "@/hooks/useNotificationProviders";
import type { NotificationProvider } from "@/lib/notificationProviders";
import { PROVIDER_META } from "@/components/notifications/providerMeta";
import { ProviderDrawer } from "@/components/notifications/ProviderDrawer";

interface Props {
  canManage: boolean;
}

export function NotificationProviderList({ canManage }: Props) {
  const { data, isLoading, isError } = useNotificationProviders();
  const toast = useToast();
  const confirm = useConfirm();
  const del = useDeleteNotificationProvider();
  const toggle = useToggleNotificationProvider();
  const test = useTestNotificationProvider();

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<NotificationProvider | null>(null);

  const openCreate = () => {
    setEditing(null);
    setDrawerOpen(true);
  };
  const openEdit = (p: NotificationProvider) => {
    setEditing(p);
    setDrawerOpen(true);
  };

  const runTest = async (p: NotificationProvider) => {
    toast.show("Testando…", "info");
    try {
      const r = await test.mutateAsync(p.id);
      if (r.ok) toast.success("✓ Notificação enviada com sucesso.");
      else toast.error(`✕ ${r.error || "Falha ao enviar notificação."}`);
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const remove = async (p: NotificationProvider) => {
    if (
      await confirm({
        title: "Excluir provedor",
        message: `Excluir "${p.name}"? O histórico de envios é mantido.`,
        confirmLabel: "Excluir",
        danger: true,
      })
    ) {
      del.mutate(p.id, { onSuccess: () => toast.success("Provedor excluído") });
    }
  };

  const columns: Column<NotificationProvider>[] = [
    {
      key: "name",
      header: "Nome",
      sortValue: (p) => p.name,
      render: (p) => {
        const Icon = PROVIDER_META[p.provider_type].Icon;
        return (
          <div className="flex items-start gap-2">
            <Icon className="mt-0.5 h-4 w-4 shrink-0 text-fg-muted" />
            <div className="min-w-0">
              <div className="font-medium text-fg">{p.name}</div>
              {p.description && (
                <div className="truncate text-xs text-fg-faint">{p.description}</div>
              )}
            </div>
          </div>
        );
      },
    },
    {
      key: "type",
      header: "Tipo",
      sortValue: (p) => p.provider_type,
      render: (p) => (
        <span className="text-fg-muted">{PROVIDER_META[p.provider_type].label}</span>
      ),
    },
    {
      key: "status",
      header: "Status",
      sortValue: (p) => (p.enabled ? "0" : "1"),
      render: (p) => <StatusChip status={p.enabled ? "ENABLED" : "DISABLED"} size="sm" />,
    },
    {
      key: "summary",
      header: "Configuração",
      render: (p) => <span className="text-xs text-fg-muted">{p.summary}</span>,
    },
    {
      key: "updated",
      header: "Última alteração",
      sortValue: (p) => p.updated_at,
      render: (p) => (
        <span className="text-xs text-fg-faint">
          {new Date(p.updated_at).toLocaleString()}
        </span>
      ),
    },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (p) =>
        canManage ? (
          <div className="flex items-center justify-end gap-1">
            <IconButton
              label="Testar"
              size="sm"
              icon={<SendIcon className="h-4 w-4" />}
              onClick={() => void runTest(p)}
            />
            <IconButton
              label="Editar"
              size="sm"
              icon={<EditIcon className="h-4 w-4" />}
              onClick={() => openEdit(p)}
            />
            <ActionMenu
              items={[
                {
                  label: p.enabled ? "Desativar" : "Ativar",
                  icon: p.enabled ? <PauseIcon className="h-4 w-4" /> : <RunIcon className="h-4 w-4" />,
                  onClick: () =>
                    toggle.mutate({ id: p.id, enabled: !p.enabled }),
                },
                {
                  label: "Excluir",
                  icon: <DeleteIcon className="h-4 w-4" />,
                  danger: true,
                  onClick: () => void remove(p),
                },
              ]}
            />
          </div>
        ) : null,
    },
  ];

  if (isError) {
    return <p className="text-sm text-danger">Falha ao carregar provedores.</p>;
  }

  return (
    <div>
      {canManage && (
        <div className="mb-3 flex justify-end">
          <Button icon={<AddIcon className="h-4 w-4" />} onClick={openCreate}>
            Adicionar provedor
          </Button>
        </div>
      )}
      <DataTable
        columns={columns}
        rows={data}
        rowKey={(p) => p.id}
        loading={isLoading}
        empty={
          <EmptyState
            icon={BellIcon}
            title="Nenhum serviço de notificação configurado"
            description="Configure Email ou Bitrix para que o sistema envie notificações automaticamente."
            action={
              canManage ? (
                <Button icon={<AddIcon className="h-4 w-4" />} onClick={openCreate}>
                  Adicionar provedor
                </Button>
              ) : undefined
            }
          />
        }
      />
      <ProviderDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        provider={editing}
      />
    </div>
  );
}
