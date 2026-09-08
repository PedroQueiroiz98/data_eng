import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  addEdge,
  Background,
  Controls,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { TaskNode, type TaskNodeData } from "@/components/workflow/TaskNode";
import { useTheme } from "@/components/ThemeProvider";
import { useRunWorkflow } from "@/hooks/useJobs";
import { useNotebooks } from "@/hooks/useNotebooks";
import { useSaveGraph, useUpdateWorkflow, useWorkflow } from "@/hooks/useWorkflows";
import { buildGraphPayload, type WorkflowDetail } from "@/lib/workflows";
import { Button, IconButton, PageHeader, StatusChip, useToast } from "@/ui";
import { AddIcon, BellIcon, DeleteIcon, RunIcon, SaveIcon } from "@/ui/icons";

const nodeTypes = { task: TaskNode };
const newId = (): string =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `t-${Math.random().toString(36).slice(2)}`;

function toFlow(wf: WorkflowDetail): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = wf.tasks.map((t, i) => ({
    id: t.id,
    type: "task",
    position: t.ui_position ?? { x: 60 + i * 240, y: 80 },
    data: {
      name: t.name,
      notebookId: t.notebook_id,
      notebookName: null,
      timeoutS: t.timeout_s,
      maxRetries: t.max_retries,
    } satisfies TaskNodeData,
  }));
  const edges: Edge[] = wf.dependencies.map((d) => ({
    id: d.id,
    source: d.from_task_id,
    target: d.to_task_id,
  }));
  return { nodes, edges };
}

function EditorInner({ id }: { id: string }) {
  const navigate = useNavigate();
  const toast = useToast();
  const { theme } = useTheme();
  const { data: wf, isLoading, isError } = useWorkflow(id);
  const { data: notebooks } = useNotebooks();
  const saveGraph = useSaveGraph(id);
  const updateMeta = useUpdateWorkflow(id);
  const run = useRunWorkflow(id);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loadedAt, setLoadedAt] = useState<string | null>(null);
  const [name, setName] = useState("");

  const notebookName = useCallback(
    (nid: string | null) => notebooks?.find((n) => n.id === nid)?.name ?? null,
    [notebooks],
  );

  useEffect(() => {
    if (!wf || wf.updated_at === loadedAt) return;
    const flow = toFlow(wf);
    flow.nodes.forEach((n) => {
      (n.data as TaskNodeData).notebookName = notebookName(
        (n.data as TaskNodeData).notebookId,
      );
    });
    setNodes(flow.nodes);
    setEdges(flow.edges);
    setName(wf.name);
    setLoadedAt(wf.updated_at);
  }, [wf, loadedAt, notebookName, setNodes, setEdges]);

  const onConnect = useCallback(
    (c: Connection) => setEdges((eds) => addEdge({ ...c, id: newId() }, eds)),
    [setEdges],
  );

  const patchSelected = (patch: Partial<TaskNodeData>) => {
    setNodes((ns) =>
      ns.map((n) =>
        n.id === selectedId ? { ...n, data: { ...n.data, ...patch } } : n,
      ),
    );
  };

  const addTask = () => {
    const nid = newId();
    setNodes((ns) => [
      ...ns,
      {
        id: nid,
        type: "task",
        position: { x: 120 + ns.length * 40, y: 200 + ns.length * 20 },
        data: {
          name: "Nova tarefa",
          notebookId: null,
          notebookName: null,
          timeoutS: null,
          maxRetries: 0,
        } satisfies TaskNodeData,
      },
    ]);
    setSelectedId(nid);
  };

  const removeSelected = () => {
    if (!selectedId) return;
    setNodes((ns) => ns.filter((n) => n.id !== selectedId));
    setEdges((es) => es.filter((e) => e.source !== selectedId && e.target !== selectedId));
    setSelectedId(null);
  };

  const onSave = async () => {
    if (name.trim() && name.trim() !== wf?.name) {
      await updateMeta.mutateAsync({ name: name.trim() });
    }
    const payload = buildGraphPayload(
      nodes.map((n) => ({
        id: n.id,
        position: n.position,
        data: {
          name: (n.data as TaskNodeData).name,
          notebookId: (n.data as TaskNodeData).notebookId,
          timeoutS: (n.data as TaskNodeData).timeoutS,
          maxRetries: (n.data as TaskNodeData).maxRetries,
        },
      })),
      edges.map((e) => ({ source: e.source, target: e.target })),
    );
    await saveGraph.mutateAsync(payload);
    setLoadedAt(null); // recarrega do servidor (ids reais para novas tasks)
    toast.success("Workflow salvo");
  };

  const selected = useMemo(
    () => nodes.find((n) => n.id === selectedId) ?? null,
    [nodes, selectedId],
  );

  if (isLoading) return <p className="text-sm text-fg-faint">Carregando…</p>;
  if (isError || !wf) return <p className="text-sm text-danger">Workflow não encontrado.</p>;

  return (
    <div className="flex h-[calc(100vh-9rem)] flex-col">
      <PageHeader
        back={{ to: "/workflows", label: "Workflows" }}
        title={
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full max-w-md rounded-md border border-transparent bg-transparent px-1 py-0.5 text-2xl font-semibold hover:border-surface-border focus:border-primary focus:bg-surface focus:outline-none"
          />
        }
        subtitle={<StatusChip status={wf.status} size="sm" />}
        actions={
          <>
            <IconButton
              label="Adicionar tarefa"
              icon={<AddIcon className="h-4 w-4" />}
              onClick={addTask}
            />
            <IconButton
              label="Remover selecionada"
              danger
              icon={<DeleteIcon className="h-4 w-4" />}
              disabled={!selectedId}
              onClick={removeSelected}
            />
            <IconButton
              label="Central de Notificações"
              icon={<BellIcon className="h-4 w-4" />}
              onClick={() => navigate(`/notifications?workflow_id=${id}&tab=history`)}
            />
            <Button
              variant="outlined"
              size="sm"
              icon={<SaveIcon className="h-4 w-4" />}
              loading={saveGraph.isPending}
              onClick={onSave}
            >
              Salvar
            </Button>
            <Button
              size="sm"
              icon={<RunIcon className="h-4 w-4" />}
              loading={run.isPending}
              disabled={nodes.length === 0}
              onClick={async () => {
                const job = await run.mutateAsync({});
                toast.success("Job iniciado");
                navigate(`/jobs/${job.id}`);
              }}
            >
              Executar
            </Button>
          </>
        }
      />

      {(run.isError || saveGraph.isError) && (
        <p className="mb-2 text-sm text-danger">
          {((run.error ?? saveGraph.error) as Error).message}
        </p>
      )}

      <div className="flex min-h-0 flex-1 gap-3">
        <div className="min-w-0 flex-1 rounded border border-surface-border">
          <ReactFlow
            colorMode={theme}
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={(_, n) => setSelectedId(n.id)}
            onPaneClick={() => setSelectedId(null)}
            fitView
          >
            <Background />
            <Controls />
          </ReactFlow>
        </div>

        <aside className="w-64 shrink-0 rounded border border-surface-border p-3 text-sm">
          {!selected && (
            <p className="text-fg-muted">Selecione uma tarefa para editar.</p>
          )}
          {selected && (
            <div className="space-y-3">
              <label className="block">
                <span className="text-xs text-fg-muted">Nome</span>
                <input
                  value={(selected.data as TaskNodeData).name}
                  onChange={(e) => patchSelected({ name: e.target.value })}
                  className="mt-0.5 w-full rounded border border-surface-border px-2 py-1"
                />
              </label>
              <label className="block">
                <span className="text-xs text-fg-muted">Notebook</span>
                <select
                  value={(selected.data as TaskNodeData).notebookId ?? ""}
                  onChange={(e) => {
                    const nid = e.target.value || null;
                    patchSelected({ notebookId: nid, notebookName: notebookName(nid) });
                  }}
                  className="mt-0.5 w-full rounded border border-surface-border px-2 py-1"
                >
                  <option value="">—</option>
                  {notebooks?.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="text-xs text-fg-muted">Timeout (s)</span>
                <input
                  type="number"
                  min={1}
                  value={(selected.data as TaskNodeData).timeoutS ?? ""}
                  onChange={(e) =>
                    patchSelected({
                      timeoutS: e.target.value ? Number(e.target.value) : null,
                    })
                  }
                  className="mt-0.5 w-full rounded border border-surface-border px-2 py-1"
                />
              </label>
              <label className="block">
                <span className="text-xs text-fg-muted">Máx. retries</span>
                <input
                  type="number"
                  min={0}
                  max={20}
                  value={(selected.data as TaskNodeData).maxRetries}
                  onChange={(e) =>
                    patchSelected({ maxRetries: Number(e.target.value) || 0 })
                  }
                  className="mt-0.5 w-full rounded border border-surface-border px-2 py-1"
                />
              </label>
            </div>
          )}
        </aside>
      </div>

    </div>
  );
}

export function WorkflowEditor() {
  const { id = "" } = useParams();
  return (
    <ReactFlowProvider>
      <EditorInner id={id} />
    </ReactFlowProvider>
  );
}
