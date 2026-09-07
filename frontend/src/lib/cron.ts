import parser from "cron-parser";

export type Frequency =
  | "once"
  | "daily"
  | "weekly"
  | "monthly"
  | "hourly"
  | "custom";

export interface FreqParts {
  time: string; // "HH:MM"
  weekday: number; // 0-6 (dom-sáb) — para weekly
  monthday: number; // 1-31 — para monthly / once
  month: number; // 1-12 — para once
  minute: number; // para hourly
}

export const DEFAULT_PARTS: FreqParts = {
  time: "09:00",
  weekday: 1,
  monthday: 1,
  month: new Date().getMonth() + 1,
  minute: 0,
};

/** Constrói a expressão cron (5 campos) a partir da frequência escolhida. */
export function buildCron(freq: Frequency, p: FreqParts): string {
  const [hh, mm] = p.time.split(":");
  const h = Number(hh) || 0;
  const m = Number(mm) || 0;
  switch (freq) {
    case "hourly":
      return `${p.minute} * * * *`;
    case "daily":
      return `${m} ${h} * * *`;
    case "weekly":
      return `${m} ${h} * * ${p.weekday}`;
    case "monthly":
      return `${m} ${h} ${p.monthday} * *`;
    case "once":
      // dispara nessa data/hora (aprox. uma vez até o próximo ano)
      return `${m} ${h} ${p.monthday} ${p.month} *`;
    default:
      return `${m} ${h} * * *`;
  }
}

const WEEKDAYS = ["domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado"];

/** Descrição legível de um cron simples; cai para a própria expressão se for complexo. */
export function describeCron(cron: string): string {
  const parts = cron.trim().split(/\s+/);
  if (parts.length !== 5) return cron;
  const min = parts[0] ?? "*";
  const hour = parts[1] ?? "*";
  const dom = parts[2] ?? "*";
  const mon = parts[3] ?? "*";
  const dow = parts[4] ?? "*";
  const at =
    /^\d+$/.test(min) && /^\d+$/.test(hour)
      ? `${hour.padStart(2, "0")}:${min.padStart(2, "0")}`
      : null;

  if (min.startsWith("*/") && hour === "*" && dom === "*" && mon === "*" && dow === "*")
    return `A cada ${min.slice(2)} min`;
  if (hour.startsWith("*/") && dom === "*" && mon === "*" && dow === "*")
    return `A cada ${hour.slice(2)}h`;
  if (min === "0" && hour === "*" && dom === "*" && mon === "*" && dow === "*")
    return "De hora em hora";
  if (at && dom === "*" && mon === "*" && dow === "*") return `Diariamente às ${at}`;
  if (at && dom === "*" && mon === "*" && /^\d$/.test(dow))
    return `Toda ${WEEKDAYS[Number(dow)] ?? dow} às ${at}`;
  if (at && /^\d+$/.test(dom) && mon === "*" && dow === "*")
    return `Todo dia ${dom} às ${at}`;
  if (at && /^\d+$/.test(dom) && /^\d+$/.test(mon) && dow === "*")
    return `${dom}/${mon} às ${at}`;
  return cron;
}

/** Ocorrências do cron dentro do mês (0-indexed) informado, no timezone dado. */
export function occurrencesInMonth(
  cron: string,
  timezone: string,
  year: number,
  month: number,
): Date[] {
  const start = new Date(Date.UTC(year, month, 1));
  const end = new Date(Date.UTC(year, month + 1, 1));
  try {
    const it = parser.parseExpression(cron, {
      currentDate: start,
      endDate: end,
      tz: timezone || "UTC",
      iterator: true,
    });
    const out: Date[] = [];
    while (it.hasNext() && out.length < 200) {
      const next = it.next();
      out.push((next as { value: { toDate: () => Date } }).value.toDate());
    }
    return out;
  } catch {
    return [];
  }
}

export function isValidCron(cron: string): boolean {
  try {
    parser.parseExpression(cron);
    return cron.trim().split(/\s+/).length === 5;
  } catch {
    return false;
  }
}
