import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusChip } from "@/ui/StatusChip";

describe("StatusChip", () => {
  it("mostra rótulo legível + ícone para status conhecidos", () => {
    const { rerender } = render(<StatusChip status="SUCCESS" />);
    expect(screen.getByText("Success")).toBeInTheDocument();

    rerender(<StatusChip status="FAILED" />);
    expect(screen.getByText("Failed")).toBeInTheDocument();

    rerender(<StatusChip status="RUNNING" />);
    expect(screen.getByText("Running")).toBeInTheDocument();

    rerender(<StatusChip status="SKIPPED" />);
    expect(screen.getByText("Skipped")).toBeInTheDocument();
  });

  it("usa o próprio texto para status desconhecido", () => {
    render(<StatusChip status="WHATEVER" />);
    expect(screen.getByText("WHATEVER")).toBeInTheDocument();
  });
});
