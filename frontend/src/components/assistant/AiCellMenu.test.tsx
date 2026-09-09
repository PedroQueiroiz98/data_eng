import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AiCellMenu } from "@/components/assistant/AiCellMenu";
import { useEditorConfig } from "@/lib/editorConfig";
import { useAssistantStore } from "@/store/assistant";

function setAi(enabled: boolean, available: boolean) {
  useEditorConfig.getState().setSection("ai", { enabled });
  useAssistantStore.setState({ available });
}

afterEach(() => {
  setAi(false, false);
  vi.restoreAllMocks();
});

describe("AiCellMenu", () => {
  it("não renderiza quando a IA está desligada", () => {
    setAi(false, true);
    const { container } = render(<AiCellMenu cellId="c1" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("não renderiza quando não há provedor", () => {
    setAi(true, false);
    const { container } = render(<AiCellMenu cellId="c1" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("dispara nbp:ai-command com o task certo", async () => {
    setAi(true, true);
    const u = userEvent.setup();
    const spy = vi.fn();
    window.addEventListener("nbp:ai-command", spy as EventListener);
    render(<AiCellMenu cellId="c1" />);
    await u.click(screen.getByText("✨ AI"));
    await u.click(screen.getByText("Explicar"));
    const ev = spy.mock.calls[0]?.[0] as CustomEvent;
    expect(ev.detail).toMatchObject({ task: "EXPLAIN", cellId: "c1" });
    window.removeEventListener("nbp:ai-command", spy as EventListener);
  });
});
