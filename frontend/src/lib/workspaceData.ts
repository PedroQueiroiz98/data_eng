import { apiGet, getAuthToken } from "@/lib/api";

export interface DataPreview {
  columns: string[];
  dtypes: string[];
  rows: unknown[][];
  total: number | null;
  truncated: boolean;
  offset: number;
}

export const fetchDataPreview = (
  _ws: string,
  path: string,
  offset = 0,
  limit = 100,
): Promise<DataPreview> =>
  apiGet(
    `/workspace/data?path=${encodeURIComponent(path)}&offset=${offset}&limit=${limit}`,
  );

export async function downloadExport(
  _ws: string,
  path: string,
  fmt: "ipynb" | "py",
): Promise<void> {
  const token = getAuthToken();
  const res = await fetch(
    `/api/workspace/export?path=${encodeURIComponent(path)}&fmt=${fmt}`,
    { headers: token ? { Authorization: `Bearer ${token}` } : {} },
  );
  if (!res.ok) throw new Error(`Export falhou (${res.status})`);
  const blob = await res.blob();
  const name = path.split("/").pop()?.replace(/\.ipynb$/, "") ?? "notebook";
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fmt === "py" ? `${name}.py` : `${name}.ipynb`;
  a.click();
  URL.revokeObjectURL(url);
}
