import { useCallback, useEffect, useRef, useState } from "react";
import { DataViewer } from "@/components/workspace/DataViewer";
import { fetchDataPreview, type DataPreview } from "@/lib/workspaceData";
import { SpinnerIcon } from "@/ui/icons";

const PAGE = 100;

export function WorkspaceDataTab({
  workspaceId,
  path,
}: {
  workspaceId: string;
  path: string;
}) {
  const [preview, setPreview] = useState<DataPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const offset = useRef(0);

  useEffect(() => {
    let alive = true;
    offset.current = 0;
    setPreview(null);
    setError(null);
    fetchDataPreview(workspaceId, path, 0, PAGE)
      .then((p) => {
        if (alive) {
          setPreview(p);
          offset.current = p.rows.length;
        }
      })
      .catch((e) => alive && setError((e as Error).message));
    return () => {
      alive = false;
    };
  }, [workspaceId, path]);

  const loadMore = useCallback(() => {
    if (!preview) return;
    setLoadingMore(true);
    fetchDataPreview(workspaceId, path, offset.current, PAGE)
      .then((p) => {
        offset.current += p.rows.length;
        setPreview((prev) =>
          prev
            ? {
                ...p,
                rows: [...prev.rows, ...p.rows],
                total: p.total ?? prev.total,
              }
            : p,
        );
      })
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoadingMore(false));
  }, [preview, workspaceId, path]);

  if (error) {
    return <div className="p-4 text-sm text-danger">Falha ao ler os dados: {error}</div>;
  }
  if (!preview) {
    return (
      <div className="flex h-full items-center justify-center text-fg-faint">
        <SpinnerIcon className="h-5 w-5 animate-spin" />
      </div>
    );
  }

  const hasMore =
    preview.truncated ||
    (preview.total != null && preview.rows.length < preview.total);

  return (
    <div className="h-full p-2">
      <DataViewer
        columns={preview.columns}
        dtypes={preview.dtypes}
        rows={preview.rows}
        total={preview.total}
        truncated={hasMore}
        onLoadMore={hasMore ? loadMore : undefined}
        loadingMore={loadingMore}
      />
    </div>
  );
}
