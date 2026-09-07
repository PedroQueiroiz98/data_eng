import { describe, expect, it } from "vitest";
import { buildGraphPayload, type FlowEdgeLike, type FlowNodeLike } from "@/lib/workflows";

const node = (id: string, over: Partial<FlowNodeLike["data"]> = {}): FlowNodeLike => ({
  id,
  position: { x: 10.6, y: 20.2 },
  data: { name: id, notebookId: "nb-1", timeoutS: null, maxRetries: 0, ...over },
});

describe("buildGraphPayload", () => {
  it("mapeia nodes para tasks com key = id e posição arredondada", () => {
    const payload = buildGraphPayload([node("a"), node("b", { maxRetries: 3 })], []);
    expect(payload.tasks).toHaveLength(2);
    expect(payload.tasks[0]).toMatchObject({
      key: "a",
      name: "a",
      type: "NOTEBOOK",
      notebook_id: "nb-1",
      ui_position: { x: 11, y: 20 },
    });
    expect(payload.tasks[1]!.max_retries).toBe(3);
  });

  it("mapeia edges para dependencies from_key/to_key", () => {
    const edges: FlowEdgeLike[] = [
      { source: "a", target: "b" },
      { source: "b", target: "c" },
    ];
    const payload = buildGraphPayload([node("a"), node("b"), node("c")], edges);
    expect(payload.dependencies).toEqual([
      { from_key: "a", to_key: "b" },
      { from_key: "b", to_key: "c" },
    ]);
  });
});
