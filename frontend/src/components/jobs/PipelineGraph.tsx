import { useMemo } from "react";
import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  ReactFlowProvider,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useTheme } from "@/components/ThemeProvider";
import { fmtDuration, type JobTask, topoLayers } from "@/lib/jobs";
import { StatusIcon } from "@/ui";

interface Props {
  tasks: JobTask[];
  dependencies: { from: string; to: string }[];
  selectedId: string | null;
  onSelect: (task: JobTask) => void;
}

interface Data {
  task: JobTask;
  selected: boolean;
  [key: string]: unknown;
}

const BORDER: Record<string, string> = {
  SUCCESS: "border-t-ok",
  RUNNING: "border-t-info",
  FAILED: "border-t-danger",
  SKIPPED: "border-t-warn",
  CANCELLED: "border-t-fg-faint",
};

function TaskFlowNode({ data }: NodeProps) {
  const { task, selected } = data as unknown as Data;
  return (
    <div
      className={`w-56 rounded-md border border-t-4 bg-surface px-3 py-2 shadow-e1 ${
        BORDER[task.status] ?? "border-t-fg-faint"
      } ${selected ? "ring-2 ring-primary" : "border-surface-border"}`}
    >
      <Handle type="target" position={Position.Left} className="!bg-fg-faint" />
      <div className="flex items-center gap-1.5">
        <StatusIcon status={task.status} className="h-3.5 w-3.5 shrink-0" />
        <span className="truncate text-sm font-medium text-fg">{task.name}</span>
      </div>
      <div className="mt-0.5 text-xs text-fg-muted">
        {task.status.toLowerCase()}
        {task.duration_ms != null && ` · ${fmtDuration(task.duration_ms)}`}
      </div>
      {task.notebook_name && (
        <div className="truncate text-[11px] text-fg-faint">{task.notebook_name}</div>
      )}
      <Handle type="source" position={Position.Right} className="!bg-fg-faint" />
    </div>
  );
}

const nodeTypes = { task: TaskFlowNode };

function Inner({ tasks, dependencies, selectedId, onSelect }: Props) {
  const { theme } = useTheme();

  const { nodes, edges } = useMemo(() => {
    const layers = topoLayers(tasks, dependencies);
    const posByWtid = new Map<string, { x: number; y: number }>();
    const ns: Node[] = [];
    layers.forEach((layer, li) => {
      layer.forEach((t, i) => {
        const x = li * 260;
        const y = i * 108 - ((layer.length - 1) * 108) / 2;
        posByWtid.set(t.workflow_task_id, { x, y });
        ns.push({
          id: t.workflow_task_id,
          type: "task",
          position: { x, y },
          data: { task: t, selected: t.id === selectedId } as unknown as Record<string, unknown>,
        });
      });
    });
    const es: Edge[] = dependencies
      .filter((d) => posByWtid.has(d.from) && posByWtid.has(d.to))
      .map((d, i) => ({
        id: `e${i}`,
        source: d.from,
        target: d.to,
        animated: false,
      }));
    return { nodes: ns, edges: es };
  }, [tasks, dependencies, selectedId]);

  const byWtid = useMemo(
    () => new Map(tasks.map((t) => [t.workflow_task_id, t])),
    [tasks],
  );

  return (
    <div className="h-[340px] w-full">
      <ReactFlow
        colorMode={theme}
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={(_, n) => {
          const t = byWtid.get(n.id);
          if (t) onSelect(t);
        }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

export function PipelineGraph(props: Props) {
  return (
    <ReactFlowProvider>
      <Inner {...props} />
    </ReactFlowProvider>
  );
}
