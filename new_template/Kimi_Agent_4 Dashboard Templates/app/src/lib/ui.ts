import type { Severity } from "@/types";

export const SEV_COLOR: Record<Severity, string> = {
  P1: "#f87171",
  P2: "#fbbf24",
  P3: "#22d3ee",
};

export const SEV_LABEL: Record<Severity, string> = {
  P1: "CRITICAL",
  P2: "ELEVATED",
  P3: "ADVISORY",
};

export function fmtClock(date: Date) {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(date.getHours())}:${p(date.getMinutes())}:${p(date.getSeconds())}`;
}

export function tickToClock(tick: number, base: Date) {
  const d = new Date(base.getTime() + tick * 1000);
  return fmtClock(d);
}

export function relTime(tick: number, now: number) {
  const d = Math.max(0, now - tick);
  if (d < 60) return `${d}s ago`;
  if (d < 3600) return `${Math.floor(d / 60)}m ago`;
  return `${Math.floor(d / 3600)}h ago`;
}
