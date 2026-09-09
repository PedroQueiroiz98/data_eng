/** Ícone por tipo de arquivo/pasta para o File Explorer (lucide, sem emojis). */
import type { ComponentType } from "react";
import type { FileNode } from "@/lib/workspace";
import { extOf, kindFromPath } from "@/lib/workspaceFiles";
import {
  CodeFileIcon,
  DescriptionIcon,
  FileIcon,
  FolderIcon,
  JsonFileIcon,
  NotebookIcon,
  SheetFileIcon,
  TableFileIcon,
} from "@/ui/icons";

type IconC = ComponentType<{ className?: string }>;

export function fileNodeIconComponent(node: Pick<FileNode, "type" | "path">): IconC {
  if (node.type === "dir") return FolderIcon;
  const ext = extOf(node.path);
  if (ext === "xlsx" || ext === "xls") return SheetFileIcon;
  switch (kindFromPath(node.path)) {
    case "notebook":
      return NotebookIcon;
    case "csv":
    case "parquet":
      return TableFileIcon;
    case "json":
      return JsonFileIcon;
    case "code":
      return CodeFileIcon;
    case "markdown":
      return DescriptionIcon;
    default:
      return FileIcon;
  }
}

const TYPE_LABEL: Record<string, string> = {
  dir: "Pasta",
  notebook: "Notebook",
  code: "Código",
  json: "JSON",
  csv: "CSV",
  parquet: "Parquet",
  markdown: "Markdown",
  text: "Texto",
};

export function fileTypeLabel(node: Pick<FileNode, "type" | "path">): string {
  if (node.type === "dir") return "Pasta";
  const ext = extOf(node.path);
  if (ext === "xlsx" || ext === "xls") return "Excel";
  if (ext === "pdf") return "PDF";
  return TYPE_LABEL[kindFromPath(node.path)] ?? "Arquivo";
}

export function fileNodeIcon(
  node: Pick<FileNode, "type" | "path">,
  className = "h-4 w-4 shrink-0",
) {
  const Icon = fileNodeIconComponent(node);
  const color =
    node.type === "dir"
      ? "text-fg-muted"
      : kindFromPath(node.path) === "notebook"
        ? "text-primary"
        : "text-fg-faint";
  return <Icon className={`${className} ${color}`} />;
}
