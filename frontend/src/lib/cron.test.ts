import { describe, expect, it } from "vitest";
import {
  buildCron,
  DEFAULT_PARTS,
  describeCron,
  isValidCron,
  occurrencesInMonth,
} from "@/lib/cron";

describe("buildCron", () => {
  it("gera cron para as frequências comuns", () => {
    const p = { ...DEFAULT_PARTS, time: "09:00", weekday: 1, monthday: 15, month: 3, minute: 5 };
    expect(buildCron("daily", p)).toBe("0 9 * * *");
    expect(buildCron("weekly", p)).toBe("0 9 * * 1");
    expect(buildCron("monthly", p)).toBe("0 9 15 * *");
    expect(buildCron("once", p)).toBe("0 9 15 3 *");
    expect(buildCron("hourly", p)).toBe("5 * * * *");
  });
});

describe("describeCron", () => {
  it("descreve expressões simples", () => {
    expect(describeCron("0 9 * * *")).toBe("Diariamente às 09:00");
    expect(describeCron("30 14 * * 5")).toBe("Toda sexta às 14:30");
    expect(describeCron("0 8 1 * *")).toBe("Todo dia 1 às 08:00");
    expect(describeCron("*/10 * * * *")).toBe("A cada 10 min");
    expect(describeCron("0 * * * *")).toBe("De hora em hora");
  });
  it("cai para a própria expressão em cron complexo", () => {
    expect(describeCron("15 3,15 * * 1-5")).toBe("15 3,15 * * 1-5");
  });
});

describe("isValidCron / occurrencesInMonth", () => {
  it("valida", () => {
    expect(isValidCron("0 9 * * *")).toBe(true);
    expect(isValidCron("banana")).toBe(false);
    expect(isValidCron("0 9 * *")).toBe(false);
  });
  it("expande ocorrências no mês", () => {
    // diariamente às 09:00, janeiro/2026 → 31 ocorrências
    const occ = occurrencesInMonth("0 9 * * *", "UTC", 2026, 0);
    expect(occ.length).toBe(31);
    expect(occ[0]?.getUTCHours()).toBe(9);
  });
});
