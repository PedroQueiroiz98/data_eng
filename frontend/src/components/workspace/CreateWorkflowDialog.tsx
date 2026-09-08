import { useEffect, useState } from "react";
import { createWorkflow, saveWorkflowGraph } from "@/lib/workflows";
import { Button, Dialog, TextArea, TextField, useToast } from "@/ui";

interface Props {
  open: boolean;
  workspaceId: string;
  notebookPath: string;
  onClose: () => void;
  onCreated: (workflowId: string) => void;
}

export function CreateWorkflowDialog({
  open,
  workspaceId,
  notebookPath,
  onClose,
  onCreated,
}: Props) {
  const toast = useToast();
  const base = notebookPath.split("/").pop()?.replace(/\.ipynb$/, "") ?? "workflow";
  const [name, setName] = useState(base);
  const [paramsText, setParamsText] = useState("{}");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) {
      setName(base);
      setParamsText("{}");
    }
  }, [open, base]);

  const submit = async () => {
    let parameters: Record<string, unknown>;
    try {
      parameters = JSON.parse(paramsText || "{}");
    } catch {
      toast.error("Parâmetros: JSON inválido");
      return;
    }
    setBusy(true);
    try {
      const wf = await createWorkflow({ name: name.trim() || base });
      await saveWorkflowGraph(wf.id, {
        tasks: [
          {
            key: "t1",
            name: base,
            type: "NOTEBOOK",
            workspace_id: workspaceId,
            notebook_path: notebookPath,
            parameters,
            ui_position: { x: 80, y: 80 },
          },
        ],
        dependencies: [],
      });
      toast.success("Workflow criado");
      onCreated(wf.id);
      onClose();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Criar Workflow"
      footer={
        <>
          <Button variant="text" onClick={onClose}>
            Cancelar
          </Button>
          <Button loading={busy} onClick={submit}>
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
        />
        <div className="text-xs text-fg-muted">
          Notebook: <span className="font-mono">{notebookPath}</span>
        </div>
        <TextArea
          label="Parâmetros (JSON)"
          rows={4}
          value={paramsText}
          onChange={(e) => setParamsText(e.target.value)}
        />
      </div>
    </Dialog>
  );
}
