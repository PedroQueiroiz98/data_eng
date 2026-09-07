import { outputText, type CellOutput } from "@/lib/notebooks";

export function CellOutputs({ outputs }: { outputs: CellOutput[] | undefined }) {
  if (!outputs || outputs.length === 0) return null;
  return (
    <div className="border-t border-surface-border bg-surface-variant px-3 py-2">
      {outputs.map((out, i) => {
        const text = outputText(out);
        const isError = out.output_type === "error";
        return (
          <pre
            key={i}
            className={`overflow-x-auto whitespace-pre-wrap font-mono text-xs ${
              isError ? "text-danger" : "text-fg"
            }`}
          >
            {isError && out.traceback ? out.traceback.join("\n") : text}
          </pre>
        );
      })}
    </div>
  );
}
