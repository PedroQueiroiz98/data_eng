import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AiResultCard, extractCode } from "@/components/assistant/AiResultCard";

describe("extractCode", () => {
  it("extrai o 1º bloco cercado", () => {
    expect(extractCode("bla\n```python\nprint(1)\n```\nfim")).toBe("print(1)");
  });
  it("devolve o texto todo se não houver bloco", () => {
    expect(extractCode("print(2)")).toBe("print(2)");
  });
});

function setup(task: "GENERATE" | "FIX" = "GENERATE") {
  const onInsert = vi.fn();
  const onInsertBelow = vi.fn();
  const onReplace = vi.fn();
  const onReject = vi.fn();
  render(
    <AiResultCard
      task={task}
      text={"```python\ndf.head(10)\n```"}
      streaming={false}
      error={null}
      originalSource={"df"}
      onInsert={onInsert}
      onInsertBelow={onInsertBelow}
      onReplace={onReplace}
      onReject={onReject}
    />,
  );
  return { onInsert, onInsertBelow, onReplace, onReject };
}

describe("AiResultCard", () => {
  it("dispara Inserir / Inserir abaixo / Descartar com o código extraído", async () => {
    const u = userEvent.setup();
    const { onInsert, onInsertBelow, onReject } = setup();
    await u.click(screen.getByText("Inserir"));
    expect(onInsert).toHaveBeenCalledWith("df.head(10)");
    await u.click(screen.getByText("Inserir abaixo"));
    expect(onInsertBelow).toHaveBeenCalledWith("df.head(10)");
    await u.click(screen.getByText("Descartar"));
    expect(onReject).toHaveBeenCalled();
  });

  it("mostra 'ver diff' para tarefas significativas (FIX)", () => {
    setup("FIX");
    expect(screen.getByText("ver diff")).toBeInTheDocument();
  });
});
