/** Parser ANSI mínimo (SGR): reset, bold, 8 + 8 cores de fg. Suficiente p/ tracebacks. */

interface Span {
  text: string;
  bold: boolean;
  color: string | null;
}

const FG: Record<number, string> = {
  30: "#3b3b3b",
  31: "#d64545",
  32: "#3fa34d",
  33: "#c08a2e",
  34: "#3b7fd6",
  35: "#a24bd6",
  36: "#2aa5b5",
  37: "#b8b8b8",
  90: "#6b7280",
  91: "#f87171",
  92: "#4ade80",
  93: "#facc15",
  94: "#60a5fa",
  95: "#e879f9",
  96: "#22d3ee",
  97: "#f3f4f6",
};

// eslint-disable-next-line no-control-regex
const ANSI_RE = /\x1b\[([0-9;]*)m/g;

export function parseAnsi(input: string): Span[] {
  const spans: Span[] = [];
  let bold = false;
  let color: string | null = null;
  let last = 0;
  let m: RegExpExecArray | null;
  ANSI_RE.lastIndex = 0;
  while ((m = ANSI_RE.exec(input)) !== null) {
    if (m.index > last) {
      spans.push({ text: input.slice(last, m.index), bold, color });
    }
    for (const raw of (m[1] || "0").split(";")) {
      const code = Number(raw || "0");
      if (code === 0) {
        bold = false;
        color = null;
      } else if (code === 1) {
        bold = true;
      } else if (code === 22) {
        bold = false;
      } else if (code === 39) {
        color = null;
      } else if (FG[code]) {
        color = FG[code]!;
      }
    }
    last = ANSI_RE.lastIndex;
  }
  if (last < input.length) spans.push({ text: input.slice(last), bold, color });
  return spans;
}
