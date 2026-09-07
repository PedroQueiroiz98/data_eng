export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-fg/10 ${className}`} />;
}

export function SkeletonRows({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="surface divide-y divide-surface-border">
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex items-center gap-4 px-4 py-3">
          {Array.from({ length: cols }).map((_, c) => (
            <Skeleton
              key={c}
              className={`h-4 ${c === 0 ? "w-40" : c === cols - 1 ? "ml-auto w-16" : "w-24"}`}
            />
          ))}
        </div>
      ))}
    </div>
  );
}
