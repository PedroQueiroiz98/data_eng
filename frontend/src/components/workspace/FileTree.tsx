import { useMemo } from "react";
import type { FileNode } from "@/lib/workspace";
import { ActionMenu } from "@/ui";
import {
  ChevronDownIcon,
  ChevronRightIcon,
  DeleteIcon,
  DownloadIcon,
  EditIcon,
  FileIcon,
  FilePlusIcon,
  FolderIcon,
  FolderOpenIcon,
  FolderPlusIcon,
  UploadIcon,
} from "@/ui/icons";

export interface FileTreeCallbacks {
  onOpenFile: (path: string) => void;
  onNewFile: (parentDir: string) => void;
  onNewFolder: (parentDir: string) => void;
  onRename: (node: FileNode) => void;
  onDelete: (node: FileNode) => void;
  onUpload: (parentDir: string) => void;
  onDownload: (node: FileNode) => void;
}

interface Props extends FileTreeCallbacks {
  root: FileNode;
  openPath: string | null;
  expanded: Set<string>;
  onToggleDir: (path: string) => void;
}

export function FileTree({ root, ...rest }: Props) {
  const children = useMemo(() => sortNodes(root.children ?? []), [root]);
  return (
    <div className="select-none py-1 text-sm">
      {children.length === 0 && (
        <p className="px-3 py-2 text-xs text-fg-faint">Workspace vazio.</p>
      )}
      {children.map((node) => (
        <TreeNode key={node.path} node={node} depth={0} {...rest} />
      ))}
    </div>
  );
}

interface NodeProps extends FileTreeCallbacks {
  node: FileNode;
  depth: number;
  openPath: string | null;
  expanded: Set<string>;
  onToggleDir: (path: string) => void;
}

function TreeNode(props: NodeProps) {
  const { node, depth, openPath, expanded, onToggleDir } = props;
  const isDir = node.type === "dir";
  const isOpen = expanded.has(node.path);
  const isActive = openPath === node.path;
  const pad = { paddingLeft: `${depth * 14 + 8}px` };

  const rowMenu = isDir
    ? [
        {
          label: "Novo arquivo",
          icon: <FilePlusIcon className="h-4 w-4" />,
          onClick: () => props.onNewFile(node.path),
        },
        {
          label: "Nova pasta",
          icon: <FolderPlusIcon className="h-4 w-4" />,
          onClick: () => props.onNewFolder(node.path),
        },
        {
          label: "Enviar arquivo",
          icon: <UploadIcon className="h-4 w-4" />,
          onClick: () => props.onUpload(node.path),
        },
        {
          label: "Baixar (zip)",
          icon: <DownloadIcon className="h-4 w-4" />,
          onClick: () => props.onDownload(node),
        },
        {
          label: "Renomear",
          icon: <EditIcon className="h-4 w-4" />,
          onClick: () => props.onRename(node),
        },
        {
          label: "Excluir",
          icon: <DeleteIcon className="h-4 w-4" />,
          danger: true,
          onClick: () => props.onDelete(node),
        },
      ]
    : [
        {
          label: "Baixar",
          icon: <DownloadIcon className="h-4 w-4" />,
          onClick: () => props.onDownload(node),
        },
        {
          label: "Renomear",
          icon: <EditIcon className="h-4 w-4" />,
          onClick: () => props.onRename(node),
        },
        {
          label: "Excluir",
          icon: <DeleteIcon className="h-4 w-4" />,
          danger: true,
          onClick: () => props.onDelete(node),
        },
      ];

  return (
    <div>
      <div
        className={`group flex items-center gap-1 rounded pr-1 ${
          isActive
            ? "bg-primary-container text-primary-on-container"
            : "hover:bg-surface-variant"
        }`}
      >
        <button
          type="button"
          style={pad}
          className="flex min-w-0 flex-1 items-center gap-1.5 py-1 text-left"
          onClick={() => (isDir ? onToggleDir(node.path) : props.onOpenFile(node.path))}
        >
          {isDir ? (
            <>
              {isOpen ? (
                <ChevronDownIcon className="h-3.5 w-3.5 shrink-0 text-fg-faint" />
              ) : (
                <ChevronRightIcon className="h-3.5 w-3.5 shrink-0 text-fg-faint" />
              )}
              {isOpen ? (
                <FolderOpenIcon className="h-4 w-4 shrink-0 text-fg-muted" />
              ) : (
                <FolderIcon className="h-4 w-4 shrink-0 text-fg-muted" />
              )}
            </>
          ) : (
            <>
              <span className="w-3.5 shrink-0" />
              <FileIcon className="h-4 w-4 shrink-0 text-fg-faint" />
            </>
          )}
          <span className="truncate">{node.name}</span>
        </button>
        <span className="opacity-0 transition group-hover:opacity-100">
          <ActionMenu items={rowMenu} />
        </span>
      </div>

      {isDir && isOpen && (
        <div>
          {sortNodes(node.children ?? []).map((child) => (
            <TreeNode key={child.path} {...props} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

function sortNodes(nodes: FileNode[]): FileNode[] {
  return [...nodes].sort((a, b) => {
    if (a.type !== b.type) return a.type === "dir" ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
}
