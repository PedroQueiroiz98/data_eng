/**
 * Entradas do menu de contexto / "⋮" de um arquivo ou pasta do File Explorer.
 * Compartilhado entre o browser em tabela e a paleta. As implementações dos
 * callbacks vivem em `pages/Workspace.tsx` e operam sempre sobre `node.path`.
 */
import type { FileNode } from "@/lib/workspace";
import { kindFromPath } from "@/lib/workspaceFiles";
import type { ContextMenuEntry } from "@/ui/ContextMenu";
import {
  DeleteIcon,
  DownloadIcon,
  DuplicateIcon,
  EditIcon,
  FileIcon,
  FilePlusIcon,
  FolderPlusIcon,
  NotebookIcon,
  RunIcon,
  UploadIcon,
} from "@/ui/icons";

export type CopyKind = "path" | "relative" | "repo" | "read-example";

export interface BatchMenuCallbacks {
  onBatchMove: (paths: string[]) => void;
  onBatchDelete: (paths: string[]) => void;
}

export interface FileMenuCallbacks {
  onOpenFile: (path: string, opts?: { newTab?: boolean }) => void;
  onNewNotebook: (parentDir: string) => void;
  onNewFile: (parentDir: string) => void;
  onNewFolder: (parentDir: string) => void;
  onUpload: (parentDir: string) => void;
  onGenerateCsv: (parentDir: string) => void;
  onRename: (node: FileNode) => void;
  onMove: (node: FileNode) => void;
  onDuplicate: (node: FileNode) => void;
  onDelete: (node: FileNode) => void;
  onDownload: (node: FileNode) => void;
  onCopyPath: (node: FileNode, kind: CopyKind) => void;
  onRun: (node: FileNode) => void;
  onExport: (node: FileNode) => void;
}

const isNotebook = (path: string): boolean => kindFromPath(path) === "notebook";
const DATA_EXT = /\.(csv|tsv|parquet|json|xlsx|txt)$/i;
const i = (Icon: typeof FileIcon) => <Icon className="h-4 w-4" />;

function copyEntries(node: FileNode, cb: FileMenuCallbacks): ContextMenuEntry[] {
  const out: ContextMenuEntry[] = [
    { label: "Copiar caminho", onClick: () => cb.onCopyPath(node, "path") },
    { label: "Copiar caminho relativo", onClick: () => cb.onCopyPath(node, "relative") },
    { label: "Copiar caminho do repositório", onClick: () => cb.onCopyPath(node, "repo") },
  ];
  if (node.type === "file" && DATA_EXT.test(node.path)) {
    out.push({
      label: "Copiar exemplo de leitura",
      onClick: () => cb.onCopyPath(node, "read-example"),
    });
  }
  return out;
}

export function fileContextEntries(
  node: FileNode,
  cb: FileMenuCallbacks,
): ContextMenuEntry[] {
  if (node.type === "dir") {
    return [
      { label: "Novo notebook", icon: i(NotebookIcon), onClick: () => cb.onNewNotebook(node.path) },
      { label: "Novo arquivo", icon: i(FilePlusIcon), onClick: () => cb.onNewFile(node.path) },
      { label: "Nova pasta", icon: i(FolderPlusIcon), onClick: () => cb.onNewFolder(node.path) },
      { label: "Enviar arquivo", icon: i(UploadIcon), onClick: () => cb.onUpload(node.path) },
      { label: "Gerar CSV de teste…", onClick: () => cb.onGenerateCsv(node.path) },
      "separator",
      ...copyEntries(node, cb),
      "separator",
      { label: "Renomear", icon: i(EditIcon), onClick: () => cb.onRename(node) },
      { label: "Mover", onClick: () => cb.onMove(node) },
      { label: "Baixar (zip)", icon: i(DownloadIcon), onClick: () => cb.onDownload(node) },
      { label: "Excluir", icon: i(DeleteIcon), danger: true, onClick: () => cb.onDelete(node) },
    ];
  }
  const common: ContextMenuEntry[] = [
    { label: "Abrir", onClick: () => cb.onOpenFile(node.path) },
    { label: "Abrir em nova aba", onClick: () => cb.onOpenFile(node.path, { newTab: true }) },
  ];
  if (isNotebook(node.path)) {
    return [
      ...common,
      { label: "Executar", icon: i(RunIcon), onClick: () => cb.onRun(node) },
      { label: "Exportar", icon: i(DownloadIcon), onClick: () => cb.onExport(node) },
      "separator",
      ...copyEntries(node, cb),
      "separator",
      { label: "Renomear", icon: i(EditIcon), onClick: () => cb.onRename(node) },
      { label: "Mover", onClick: () => cb.onMove(node) },
      { label: "Duplicar", icon: i(DuplicateIcon), onClick: () => cb.onDuplicate(node) },
      { label: "Excluir", icon: i(DeleteIcon), danger: true, onClick: () => cb.onDelete(node) },
    ];
  }
  return [
    ...common,
    "separator",
    ...copyEntries(node, cb),
    "separator",
    { label: "Renomear", icon: i(EditIcon), onClick: () => cb.onRename(node) },
    { label: "Mover", onClick: () => cb.onMove(node) },
    { label: "Duplicar", icon: i(DuplicateIcon), onClick: () => cb.onDuplicate(node) },
    { label: "Baixar", icon: i(DownloadIcon), onClick: () => cb.onDownload(node) },
    { label: "Excluir", icon: i(DeleteIcon), danger: true, onClick: () => cb.onDelete(node) },
  ];
}

export function batchContextEntries(
  paths: string[],
  cb: BatchMenuCallbacks,
): ContextMenuEntry[] {
  return [
    { label: "Mover para…", onClick: () => cb.onBatchMove(paths) },
    "separator",
    {
      label: `Excluir ${paths.length} itens`,
      icon: i(DeleteIcon),
      danger: true,
      onClick: () => cb.onBatchDelete(paths),
    },
  ];
}
