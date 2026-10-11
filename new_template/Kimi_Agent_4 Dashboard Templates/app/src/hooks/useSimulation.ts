import { useEffect, useMemo, useState } from "react";
import { createWorld, tickWorld, toggleMode } from "@/lib/sim";
import { TEMPLATES } from "@/lib/templates";
import type { ShowMode, TemplateId, WorldState } from "@/types";

export function useSimulation(tickMs = 1000) {
  const [world, setWorld] = useState<WorldState>(() => createWorld(TEMPLATES.expo));

  useEffect(() => {
    const id = window.setInterval(() => {
      setWorld((w) => tickWorld(w));
    }, tickMs);
    return () => window.clearInterval(id);
  }, [tickMs]);

  const api = useMemo(
    () => ({
      setMode: (mode: ShowMode) => setWorld((w) => toggleMode(w, mode)),
      setTemplate: (id: TemplateId) => setWorld(() => createWorld(TEMPLATES[id])),
      ackAlert: (id: string) =>
        setWorld((w) => ({
          ...w,
          alerts: w.alerts.map((a) => (a.id === id ? { ...a, status: "acked" as const } : a)),
        })),
      ackAll: () =>
        setWorld((w) => ({ ...w, alerts: w.alerts.map((a) => ({ ...a, status: "acked" as const })) })),
      greetVip: (id: string) =>
        setWorld((w) => ({ ...w, vips: w.vips.map((v) => (v.id === id ? { ...v, greeted: true } : v)) })),
    }),
    [],
  );

  return { world, ...api };
}
