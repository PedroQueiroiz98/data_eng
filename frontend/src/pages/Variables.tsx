import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
import { AddIcon, DeleteIcon, VariableIcon } from "@/ui/icons";

interface Variable {
  key: string;
  value: string;
  scope: string;
  updated_at: string;
}

export function Variables() {
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["variables"],
    queryFn: () => apiGet<Variable[]>("/variables"),
  });
  const save = useMutation({
    mutationFn: ({ key, value }: { key: string; value: string }) =>
      apiPut(`/variables/${key}`, { value }),
    onSuccess: () => {
      toast.success("Variável salva");
      qc.invalidateQueries({ queryKey: ["variables"] });
    },
    onError: (e) => toast.error((e as Error).message),
  });
  const remove = useMutation({
    mutationFn: (key: string) => apiDelete(`/variables/${key}`),
    onSuccess: () => {
      toast.success("Variável excluída");
      qc.invalidateQueries({ queryKey: ["variables"] });
    },
  });

  const [dialog, setDialog] = useState(false);
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");

  const submit = async () => {
    if (!key.trim()) return;
    await save.mutateAsync({ key: key.trim(), value });
    setDialog(false);
    setKey("");
    setValue("");
  };

  const del = async (k: string) => {
    if (
      await confirm({
        title: "Excluir variável",
        message: `Excluir "${k}"?`,
        confirmLabel: "Excluir",
        danger: true,
      })
    )
      remove.mutate(k);
  };

  const columns: Column<Variable>[] = [
    {
      key: "key",
      header: "Chave",
      sortValue: (v) => v.key,
      render: (v) => <span className="font-mono text-fg">{v.key}</span>,
    },
    {
      key: "value",
      header: "Valor",
      sortValue: (v) => v.value,
      render: (v) => <span className="text-fg-muted">{v.value}</span>,
    },
    {
      key: "scope",
      header: "Escopo",
      sortValue: (v) => v.scope,
      render: (v) => <span className="text-xs text-fg-faint">{v.scope}</span>,
    },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (v) => (
        <IconButton
          label="Excluir"
          size="sm"
          danger
          icon={<DeleteIcon className="h-4 w-4" />}
          onClick={() => void del(v.key)}
        />
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Variáveis"
        subtitle="Valores não-sensíveis, injetados como env var na execução."
        actions={
          <Button icon={<AddIcon className="h-4 w-4" />} onClick={() => setDialog(true)}>
            Nova Variável
          </Button>
        }
      />

      {isError ? (
        <p className="text-sm text-danger">Falha ao carregar variáveis.</p>
      ) : (
        <DataTable
          columns={columns}
          rows={data}
          rowKey={(v) => `${v.scope}/${v.key}`}
          loading={isLoading}
          empty={
            <EmptyState
              icon={VariableIcon}
              title="Nenhuma variável"
              description="Cadastre variáveis para usar nas execuções."
            />
          }
        />
      )}

      <Dialog
        open={dialog}
        onClose={() => setDialog(false)}
        title="Nova variável"
        footer={
          <>
            <Button variant="text" onClick={() => setDialog(false)}>
              Cancelar
            </Button>
            <Button loading={save.isPending} disabled={!key.trim()} onClick={submit}>
              Salvar
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <TextField
            label="Chave"
            mono
            value={key}
            placeholder="ENVIRONMENT"
            onChange={(e) => setKey(e.target.value)}
          />
          <TextField label="Valor" value={value} onChange={(e) => setValue(e.target.value)} />
        </div>
      </Dialog>
    </div>
  );
}
