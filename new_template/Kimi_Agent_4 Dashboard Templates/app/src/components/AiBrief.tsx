import { useMemo } from "react";
import type { WorldState } from "@/types";

export default function AiBrief({ world, onAckAll }: { world: WorldState; onAckAll: () => void }) {
  const brief = useMemo(() => {
    const open = world.alerts.filter((a) => a.status !== "acked");
    const p1 = open.filter((a) => a.severity === "P1");
    const tracking = world.blacklist.filter((b) => b.status === "TRACKING");
    const parts: string[] = [];

    if (world.mode === "after") {
      parts.push(
        `Night watch active. Perimeter armed across 12 zones; ${world.counts.staff} whitelisted staff/contractors on floor, all motion is anomalous by default.`,
      );
      const denied = world.access.filter((a) => a.result === "DENIED").length;
      if (denied > 0) parts.push(`${denied} access attempt${denied > 1 ? "s" : ""} denied on continuous face verification — shrinkage audit trail recording.`);
    } else {
      parts.push(
        `${world.counts.attendees} ${world.template.visitorNoun} (${world.counts.vip} VIP, staff filtered from analytics). Behavioural baseline stable across 8 zones.`,
      );
    }
    if (tracking.length > 0) {
      parts.push(
        `${tracking.length} watchlist match${tracking.length > 1 ? "es" : ""} under active track — exits can be quietly blocked on your signal.`,
      );
    }
    if (p1.length > 0) {
      parts.push(`${p1.length} critical event${p1.length > 1 ? "s" : ""} open, latest: “${p1[p1.length - 1].title}” at ${p1[p1.length - 1].location}.`);
    }
    if (world.staffingGap && world.staffingGap.ratio > 4 && world.mode === "show") {
      parts.push(`Crowd density building at ${world.staffingGap.booth} — redeploy suggested.`);
    }
    return parts.join(" ");
  }, [world]);

  const chips = useMemo(() => {
    const out: string[] = [];
    if (world.blacklist.some((b) => b.status === "TRACKING")) out.push("Quietly block exits 2 & 4");
    if (world.alerts.some((a) => a.type === "SLEIGHT OF HAND" && a.status !== "acked")) out.push("Verify tray contents · B1");
    if (world.staffingGap && world.staffingGap.ratio > 4 && world.mode === "show") out.push(`Redeploy staff → ${world.staffingGap.booth.split(" ")[0]}`);
    if (world.vips.some((v) => !v.greeted)) out.push("Brief sales director on VIP in aisle");
    if (out.length === 0) out.push("No action required — monitoring");
    return out.slice(0, 4);
  }, [world]);

  return (
    <section className="px-4 pt-3">
      <div className="panel relative overflow-hidden">
        <div className="absolute left-0 top-0 bottom-0 w-[3px]" style={{ background: "linear-gradient(180deg,#22d3ee,#34d399)" }} />
        <div className="flex flex-col md:flex-row md:items-center gap-3 px-4 py-3">
          <div className="flex items-center gap-2.5 shrink-0">
            <span
              className="grid place-items-center w-8 h-8 rounded-full text-[13px] font-black"
              style={{
                background: "linear-gradient(135deg, rgba(34,211,238,0.25), rgba(52,211,153,0.18))",
                color: "#22d3ee",
                boxShadow: "0 0 16px rgba(34,211,238,0.25), inset 0 0 0 1px rgba(34,211,238,0.4)",
              }}
            >
              Æ
            </span>
            <div>
              <div className="text-[10px] font-bold tracking-[0.2em] text-white">AEGIS COPILOT</div>
              <div className="label-micro">situation brief · live synthesis</div>
            </div>
          </div>
          <p className="font-sans-reading text-[12.5px] leading-relaxed text-[#b8c4d8] flex-1 md:border-l md:pl-4" style={{ borderColor: "#1a2540" }}>
            {brief}
          </p>
          <div className="flex flex-wrap items-center gap-1.5 shrink-0">
            {chips.map((c) => (
              <button
                key={c}
                onClick={onAckAll}
                className="px-2.5 h-7 rounded text-[10px] tracking-wider transition-colors duration-150 border hover:text-white"
                style={{ borderColor: "#22304f", color: "#8494ad", background: "rgba(17,26,43,0.6)" }}
              >
                {c}
              </button>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
