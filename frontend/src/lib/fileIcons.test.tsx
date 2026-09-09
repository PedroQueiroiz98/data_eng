import { describe, expect, it } from "vitest";
import { fileNodeIconComponent, fileTypeLabel } from "@/lib/fileIcons";
import {
  CodeFileIcon,
  FolderIcon,
  JsonFileIcon,
  NotebookIcon,
  SheetFileIcon,
  TableFileIcon,
} from "@/ui/icons";

const f = (path: string) => ({ type: "file" as const, path });

describe("fileIcons", () => {
  it("mapeia o ícone por tipo", () => {
    expect(fileNodeIconComponent({ type: "dir", path: "x" })).toBe(FolderIcon);
    expect(fileNodeIconComponent(f("a/etl.ipynb"))).toBe(NotebookIcon);
    expect(fileNodeIconComponent(f("a/dados.csv"))).toBe(TableFileIcon);
    expect(fileNodeIconComponent(f("a/x.parquet"))).toBe(TableFileIcon);
    expect(fileNodeIconComponent(f("a/cfg.json"))).toBe(JsonFileIcon);
    expect(fileNodeIconComponent(f("a/transform.py"))).toBe(CodeFileIcon);
    expect(fileNodeIconComponent(f("a/planilha.xlsx"))).toBe(SheetFileIcon);
  });

  it("rótulo de tipo legível", () => {
    expect(fileTypeLabel({ type: "dir", path: "x" })).toBe("Pasta");
    expect(fileTypeLabel(f("a/etl.ipynb"))).toBe("Notebook");
    expect(fileTypeLabel(f("a/d.csv"))).toBe("CSV");
    expect(fileTypeLabel(f("a/x.pdf"))).toBe("PDF");
    expect(fileTypeLabel(f("a/README.md"))).toBe("Markdown");
  });
});
