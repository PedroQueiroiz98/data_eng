import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthContext } from "@/components/AuthProvider";
import { apiDelete, apiGet, apiPut } from "@/lib/api";
import {
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
import { AddIcon, DeleteIcon, EditIcon, SecretIcon } from "@/ui/icons";

interface SecretMeta {
  key: string;
  created_at: string;
  updated_at: string;
}

export function Secrets() {
  const { user } = useAuthContext();
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["secrets"],
    queryFn: () => apiGet<SecretMeta[]>("/secrets"),
    enabled: user?.role === "admin",
  });
  const save = useMutation({
    mutationFn: ({ key, value }: { key: string; value: string }) =>
      apiPut(`/secrets/${key}`, { value }),
    onSuccess: () => {
      toast.success("Secret salvo");
      qc.invalidateQueries({ queryKey: ["secrets"] });
    },
    onError: (e) => toast.error((e as Error).message),
  });
  const remove = useMutation({
    mutationFn: (key: string) => apiDelete(`/secrets/${key}`),
    onSuccess: () => {
      toast.success("Secret excluído");
      qc.invalidateQueries({ queryKey: ["secrets"] });
    },
  });

  const [dialog, setDialog] = useState<{ mode: "create" | "edit"; key: string } | null>(null);
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");

  const openCreate = () => {
    setDialog({ mode: "create", key: "" });
    setKey("");
    setValue("");
  };
  const openEdit = (k: string) => {
    setDialog({ mode: "edit", key: k });
    setKey(k);
    setValue("");
  };

  if (user?.role !== "admin") {
    return (
      <div>
        <PageHeader title="Secrets" />
        <EmptyState icon={SecretIcon} title="Acesso restrito" description="Apenas administradores." />
      </div>
    );
  }

  const submit = async () => {
    const k = dialog?.mode === "edit" ? dialog.key : key.trim();
    if (!k || !value) return;
    await save.mutateAsync({ key: k, value });
    setDialog(null);
    setKey("");
    setValue("");
  };

  const del = async (k: string) => {
    if (
      await confirm({
        title: "Excluir secret",
        message: `Excluir "${k}"?`,
        confirmLabel: "Excluir",
        danger: true,
      })
    )
      remove.mutate(k);
  };

  const columns: Column<SecretMeta>[] = [
    {
      key: "key",
      header: "Chave",
      sortValue: (s) => s.key,
      render: (s) => <span className="font-mono text-fg">{s.key}</span>,
    },
    {
      key: "updated",
      header: "Atualizado",
      sortValue: (s) => s.updated_at,
      render: (s) => (
        <span className="text-fg-muted">{new Date(s.updated_at).toLocaleString()}</span>
      ),
    },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (s) => (
        <div className="flex justify-end gap-1">
          <IconButton
            label="Editar"
            size="sm"
            icon={<EditIcon className="h-4 w-4" />}
            onClick={() => openEdit(s.key)}
          />
          <IconButton
            label="Excluir"
            size="sm"
            danger
            icon={<DeleteIcon className="h-4 w-4" />}
            onClick={() => void del(s.key)}
          />
        </div>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Secrets"
        subtitle="Cifrados em repouso, injetados como env var e mascarados nos logs. O valor nunca é retornado."
        actions={
          <Button icon={<AddIcon className="h-4 w-4" />} onClick={openCreate}>
            Novo Secret
          </Button>
        }
      />

      {isError ? (
        <p className="text-sm text-danger">Falha ao carregar secrets.</p>
      ) : (
        <DataTable
          columns={columns}
          rows={data}
          rowKey={(s) => s.key}
          loading={isLoading}
          empty={
            <EmptyState
              icon={SecretIcon}
              title="Nenhum secret"
              description="Cadastre um secret para usá-lo nas execuções."
            />
          }
        />
      )}

      <Dialog
        open={!!dialog}
        onClose={() => setDialog(null)}
        title={dialog?.mode === "edit" ? `Editar secret "${dialog.key}"` : "Novo secret"}
        footer={
          <>
            <Button variant="text" onClick={() => setDialog(null)}>
              Cancelar
            </Button>
            <Button
              loading={save.isPending}
              disabled={dialog?.mode === "edit" ? !value : !key.trim() || !value}
              onClick={submit}
            >
              Salvar
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <TextField
            label="Chave"
            mono
            value={dialog?.mode === "edit" ? dialog.key : key}
            placeholder="API_KEY"
            disabled={dialog?.mode === "edit"}
            onChange={(e) => setKey(e.target.value)}
          />
          <TextField
            label="Valor"
            type="password"
            value={value}
            hint={
              dialog?.mode === "edit"
                ? "O valor atual nunca é exibido por segurança — informe o novo valor."
                : undefined
            }
            onChange={(e) => setValue(e.target.value)}
          />
        </div>
      </Dialog>
    </div>
  );
}
