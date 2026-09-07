import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
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
import { useRunWorkflow } from "@/hooks/useJobs";
import { useNotebooks } from "@/hooks/useNotebooks";
import { useSaveGraph, useUpdateWorkflow, useWorkflow } from "@/hooks/useWorkflows";
import { buildGraphPayload, type WorkflowDetail } from "@/lib/workflows";

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
  };

  const selected = useMemo(
    () => nodes.find((n) => n.id === selectedId) ?? null,
    [nodes, selectedId],
  );

  if (isLoading) return <p className="text-slate-500">Carregando…</p>;
  if (isError || !wf) return <p className="text-red-600">Workflow não encontrado.</p>;

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col">
      <div className="mb-3 flex items-center gap-3">
        <Link to="/workflows" className="text-sm text-slate-500 hover:underline">
          ← Workflows
        </Link>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="rounded border border-slate-300 px-2 py-1 text-lg font-medium"
        />
        <span className="text-xs text-slate-400">{wf.status}</span>
        <div className="ml-auto flex gap-2">
          <button type="button" onClick={addTask} className="btn-cell text-sm">
            + Tarefa
          </button>
          <button
            type="button"
            onClick={removeSelected}
            disabled={!selectedId}
            className="btn-cell text-sm text-red-600"
          >
            Remover
          </button>
          <button
            type="button"
            onClick={onSave}
            disabled={saveGraph.isPending}
            className="rounded border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-40"
          >
            {saveGraph.isPending ? "Salvando…" : "Salvar"}
          </button>
          <button
            type="button"
            onClick={async () => {
              const job = await run.mutateAsync({});
              navigate(`/jobs/${job.id}`);
            }}
            disabled={run.isPending || nodes.length === 0}
            className="rounded bg-slate-800 px-3 py-1.5 text-sm text-white disabled:opacity-40"
          >
            {run.isPending ? "Iniciando…" : "Executar"}
          </button>
        </div>
      </div>

      {run.isError && (
        <p className="mb-2 text-sm text-red-600">{(run.error as Error).message}</p>
      )}

      {saveGraph.isError && (
        <p className="mb-2 text-sm text-red-600">
          {(saveGraph.error as Error).message}
        </p>
      )}

      <div className="flex min-h-0 flex-1 gap-3">
        <div className="min-w-0 flex-1 rounded border border-slate-200">
          <ReactFlow
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

        <aside className="w-64 shrink-0 rounded border border-slate-200 p-3 text-sm">
          {!selected && (
            <p className="text-slate-500">Selecione uma tarefa para editar.</p>
          )}
          {selected && (
            <div className="space-y-3">
              <label className="block">
                <span className="text-xs text-slate-500">Nome</span>
                <input
                  value={(selected.data as TaskNodeData).name}
                  onChange={(e) => patchSelected({ name: e.target.value })}
                  className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1"
                />
              </label>
              <label className="block">
                <span className="text-xs text-slate-500">Notebook</span>
                <select
                  value={(selected.data as TaskNodeData).notebookId ?? ""}
                  onChange={(e) => {
                    const nid = e.target.value || null;
                    patchSelected({ notebookId: nid, notebookName: notebookName(nid) });
                  }}
                  className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1"
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
                <span className="text-xs text-slate-500">Timeout (s)</span>
                <input
                  type="number"
                  min={1}
                  value={(selected.data as TaskNodeData).timeoutS ?? ""}
                  onChange={(e) =>
                    patchSelected({
                      timeoutS: e.target.value ? Number(e.target.value) : null,
                    })
                  }
                  className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1"
                />
              </label>
              <label className="block">
                <span className="text-xs text-slate-500">Máx. retries</span>
                <input
                  type="number"
                  min={0}
                  max={20}
                  value={(selected.data as TaskNodeData).maxRetries}
                  onChange={(e) =>
                    patchSelected({ maxRetries: Number(e.target.value) || 0 })
                  }
                  className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1"
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
