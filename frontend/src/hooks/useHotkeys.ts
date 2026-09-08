import { useEffect, useRef } from "react";

export type HotkeyMap = Record<string, (e: KeyboardEvent) => void>;

function comboOf(e: KeyboardEvent): string {
  const parts: string[] = [];
  if (e.ctrlKey || e.metaKey) parts.push("mod");
  if (e.shiftKey) parts.push("shift");
  if (e.altKey) parts.push("alt");
  const k = e.key.toLowerCase();
  parts.push(k === " " ? "space" : k);
  return parts.join("+");
}

const inPlainInput = (): boolean => {
  const el = document.activeElement as HTMLElement | null;
  if (!el) return false;
  if (el.closest(".monaco-editor")) return false;
  const tag = el.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || el.isContentEditable;
};

/**
 * Listener global de atalhos. Combos: "mod+s", "shift+enter", "mod+shift+p"…
 * `mod` = Ctrl ou Cmd. Atalhos de execução (enter) são ignorados quando o foco
 * está num input simples (diálogos), mas funcionam dentro do Monaco.
 */
export function useHotkeys(map: HotkeyMap, enabled = true): void {
  const mapRef = useRef(map);
  mapRef.current = map;

  useEffect(() => {
    if (!enabled) return;
    const onKey = (e: KeyboardEvent): void => {
      const combo = comboOf(e);
      const handler = mapRef.current[combo];
      if (!handler) return;
      if (combo.endsWith("enter") && !combo.includes("mod") && inPlainInput()) return;
      e.preventDefault();
      handler(e);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [enabled]);
}
