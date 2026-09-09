import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { openExecutionSocket, openWorkspaceSocket } from "@/lib/ws";
import type { ExecutionDetail } from "@/lib/executions";

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  closed = false;

  constructor(readonly url: string) {
    MockWebSocket.instances.push(this);
  }
  close(): void {
    this.closed = true;
    this.onclose?.();
  }
  emit(obj: unknown): void {
    this.onmessage?.({ data: JSON.stringify(obj) });
  }
  static last(): MockWebSocket {
    return MockWebSocket.instances.at(-1)!;
  }
}

const execution = (status: string): ExecutionDetail =>
  ({ id: "e1", status, error_message: null, has_output: false }) as unknown as ExecutionDetail;

beforeEach(() => {
  MockWebSocket.instances = [];
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
});

describe("openExecutionSocket", () => {
  it("entrega snapshot e logs e acompanha o último seq", () => {
    const onSnapshot = vi.fn();
    const onLog = vi.fn();
    openExecutionSocket(
      "e1",
      { onSnapshot, onLog },
      { WebSocketImpl: MockWebSocket as unknown as typeof WebSocket, baseUrl: "ws://x/ws" },
    );

    const ws = MockWebSocket.last();
    expect(ws.url).toBe("ws://x/ws/executions/e1?after_seq=0");

    ws.onopen?.();
    ws.emit({ type: "snapshot", execution: execution("RUNNING"), logs: [{ seq: 3 }, { seq: 5 }] });
    expect(onSnapshot).toHaveBeenCalledOnce();

    ws.emit({ type: "log", seq: 6, level: "INFO", message: "oi", ts: "t" });
    expect(onLog).toHaveBeenCalledWith(expect.objectContaining({ seq: 6 }));
  });

  it("reconecta com after_seq = último seq visto", () => {
    openExecutionSocket(
      "e1",
      {},
      { WebSocketImpl: MockWebSocket as unknown as typeof WebSocket, baseUrl: "ws://x/ws" },
    );
    const first = MockWebSocket.last();
    first.onopen?.();
    first.emit({ type: "log", seq: 9, level: "INFO", message: "x", ts: "t" });

    first.onclose?.(); // queda
    vi.advanceTimersByTime(20_000); // deixa o backoff disparar

    const second = MockWebSocket.last();
    expect(second).not.toBe(first);
    expect(second.url).toBe("ws://x/ws/executions/e1?after_seq=9");
  });

  it("para de reconectar quando chega status terminal", () => {
    openExecutionSocket(
      "e1",
      {},
      { WebSocketImpl: MockWebSocket as unknown as typeof WebSocket, baseUrl: "ws://x/ws" },
    );
    const ws = MockWebSocket.last();
    ws.emit({ type: "status_changed", status: "SUCCESS" });
    expect(ws.closed).toBe(true);

    ws.onclose?.();
    vi.advanceTimersByTime(60_000);
    expect(MockWebSocket.instances).toHaveLength(1); // não reconectou
  });

  it("stop() encerra e impede reconexão", () => {
    const stop = openExecutionSocket(
      "e1",
      {},
      { WebSocketImpl: MockWebSocket as unknown as typeof WebSocket, baseUrl: "ws://x/ws" },
    );
    const ws = MockWebSocket.last();
    stop();
    expect(ws.closed).toBe(true);
    vi.advanceTimersByTime(60_000);
    expect(MockWebSocket.instances).toHaveLength(1);
  });
});

describe("openWorkspaceSocket", () => {
  it("conecta em /workspace, entrega snapshot + fs.batch e retoma por after_seq", () => {
    const onSnapshot = vi.fn();
    const onBatch = vi.fn();
    openWorkspaceSocket(
      { onSnapshot, onBatch },
      { WebSocketImpl: MockWebSocket as unknown as typeof WebSocket, baseUrl: "ws://x/ws" },
    );
    const ws = MockWebSocket.last();
    expect(ws.url).toBe("ws://x/ws/workspace?after_seq=0");

    ws.onopen?.();
    ws.emit({ type: "snapshot", tree: { name: "", path: "", type: "dir", children: [] }, seq: 4 });
    expect(onSnapshot).toHaveBeenCalledOnce();

    ws.emit({ type: "fs.batch", seq: 7, ts: 1, changes: [{ op: "created", path: "a.csv", is_dir: false }] });
    expect(onBatch).toHaveBeenCalledWith(expect.objectContaining({ seq: 7 }));

    ws.onclose?.();
    vi.advanceTimersByTime(20_000);
    expect(MockWebSocket.last().url).toBe("ws://x/ws/workspace?after_seq=7");
  });
});
