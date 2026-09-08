import { useCallback, useRef, useState } from "react";

interface Options {
  axis: "x" | "y";
  value: number;
  min: number;
  max: number;
  /** true quando arrastar para cima/esquerda deve *aumentar* o tamanho (painéis) */
  invert?: boolean;
  onChange: (value: number) => void;
}

interface DragHandleProps {
  onPointerDown: (e: React.PointerEvent) => void;
  onPointerMove: (e: React.PointerEvent) => void;
  onPointerUp: (e: React.PointerEvent) => void;
  onPointerCancel: (e: React.PointerEvent) => void;
  onDoubleClick?: (e: React.MouseEvent) => void;
}

/**
 * Divisor redimensionável baseado em pointer events (sem lib).
 * O componente é dono do valor (vem do store); este hook só faz a matemática do drag.
 */
export function useResizable({
  axis,
  value,
  min,
  max,
  invert = false,
  onChange,
}: Options): { dragging: boolean; handleProps: DragHandleProps } {
  const start = useRef<{ pos: number; val: number } | null>(null);
  const [dragging, setDragging] = useState(false);

  const onPointerDown = useCallback(
    (e: React.PointerEvent) => {
      e.preventDefault();
      (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
      start.current = { pos: axis === "x" ? e.clientX : e.clientY, val: value };
      setDragging(true);
    },
    [axis, value],
  );

  const onPointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!start.current) return;
      const cur = axis === "x" ? e.clientX : e.clientY;
      let delta = cur - start.current.pos;
      if (invert) delta = -delta;
      const next = Math.min(max, Math.max(min, start.current.val + delta));
      onChange(next);
    },
    [axis, invert, max, min, onChange],
  );

  const end = useCallback((e: React.PointerEvent) => {
    start.current = null;
    setDragging(false);
    (e.currentTarget as Element).releasePointerCapture?.(e.pointerId);
  }, []);

  return {
    dragging,
    handleProps: {
      onPointerDown,
      onPointerMove,
      onPointerUp: end,
      onPointerCancel: end,
    },
  };
}
