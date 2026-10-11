import { useEffect, useState } from "react";
import { fmtClock } from "@/lib/ui";
import type { ShowMode, WorldState } from "@/types";

function RadarMark() {
  return (
    <svg width="34" height="34" viewBox="0 0 34 34" className="shrink-0">
      <circle cx="17" cy="17" r="15.5" fill="none" stroke="#1a2540" strokeWidth="1" />
      <circle cx="17" cy="17" r="10.5" fill="none" stroke="#1a2540" strokeWidth="1" strokeDasharray="2 3" />
      <circle cx="17" cy="17" r="5" fill="none" stroke="#22304f" strokeWidth="1" />
      <g className="anim-radar" style={{ transformOrigin: "17px 17px" }}>
        <path d="M17 17 L17 2 A15 15 0 0 1 27.6 9.3 Z" fill="rgba(34,211,238,0.28)" />
        <line x1="17" y1="17" x2="17" y2="2" stroke="#22d3ee" strokeWidth="1.2" />
      </g>
      <circle cx="17" cy="17" r="1.8" fill="#22d3ee" />
      <circle cx="22.5" cy="12" r="1.2" fill="#f87171" className="anim-pulse-dot" />
    </svg>
  );
}

function ThreatGauge({ score }: { score: number }) {
  const level = score >= 60 ? "SEVERE" : score >= 34 ? "GUARDED" : "LOW";
  const color = score >= 60 ? "#f87171" : score >= 34 ? "#fbbf24" : "#34d399";
  const bars = 10;
  const lit = Math.round((score / 100) * bars);
  return (
    <div className="flex items-center gap-3 px-3 py-1.5 rounded border" style={{ borderColor: "#1a2540", background: "rgba(12,18,32,0.6)" }}>
      <span className="relative flex h-2 w-2">
        <span className="absolute inline-flex h-full w-full rounded-full opacity-60 anim-pulse-dot" style={{ background: color }} />
        <span className="relative inline-flex rounded-full h-2 w-2" style={{ background: color, boxShadow: `0 0 8px ${color}` }} />
      </span>
      <div>
        <div className="label-micro">Threat level</div>
        <div className="text-[11px] font-bold tracking-[0.14em]" style={{ color }}>
          {level} <span className="text-[10px] font-medium opacity-70">{score}/100</span>
        </div>
      </div>
      <div className="flex items-end gap-[2px] h-5">
        {Array.from({ length: bars }).map((_, i) => (
          <span
            key={i}
            className="w-[3px] rounded-sm"
            style={{
              height: `${5 + i * 1.5}px`,
              background: i < lit ? color : "#1a2540",
              opacity: i < lit ? 0.55 + (i / bars) * 0.45 : 1,
            }}
          />
        ))}
      </div>
    </div>
  );
}

export default function Header({
  world,
  onMode,
}: {
  world: WorldState;
  onMode: (m: ShowMode) => void;
}) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);

  const openP1 = world.alerts.filter((a) => a.severity === "P1" && a.status !== "acked").length;
  const after = world.mode === "after";
  const tpl = world.template;
  const cams = tpl.cameras;

  return (
    <header className="sticky top-0 z-40 border-b glass" style={{ borderColor: "#1a2540" }}>
      <div className="flex items-center gap-4 px-4 h-14">
        <div className="flex items-center gap-2.5">
          <RadarMark />
          <div>
            <div className="text-[13px] font-bold tracking-[0.22em] text-white leading-none">
              AEGIS<span style={{ color: "#22d3ee" }}>·OS</span>
            </div>
            <div className="label-micro mt-1">AI exhibition security</div>
          </div>
        </div>

        <div className="hidden lg:block h-8 w-px" style={{ background: "#1a2540" }} />
        <div className="hidden lg:block">
          <div className="text-[11px] font-semibold tracking-wider text-white">{tpl.venue}</div>
          <div className="label-micro mt-0.5">{tpl.venueSub}</div>
        </div>

        <div className="flex-1" />

        {/* mode switch */}
        <div className="hidden md:flex items-center rounded border p-0.5" style={{ borderColor: "#1a2540", background: "rgba(5,8,16,0.7)" }}>
          {(["show", "after"] as ShowMode[]).map((m) => {
            const active = world.mode === m;
            return (
              <button
                key={m}
                onClick={() => onMode(m)}
                className="px-3 h-7 rounded text-[10px] font-bold tracking-[0.16em] transition-all duration-150"
                style={{
                  background: active ? (m === "after" ? "rgba(232,121,249,0.14)" : "rgba(52,211,153,0.12)") : "transparent",
                  color: active ? (m === "after" ? "#e879f9" : "#34d399") : "#4a5a76",
                  boxShadow: active ? `inset 0 0 0 1px ${m === "after" ? "rgba(232,121,249,0.4)" : "rgba(52,211,153,0.35)"}` : "none",
                }}
              >
                {m === "show" ? tpl.modes.show : tpl.modes.after}
              </button>
            );
          })}
        </div>

        <ThreatGauge score={world.threatScore} />

        <div className="hidden xl:flex flex-col items-end">
          <div className="text-[15px] font-bold tabular-nums text-white leading-none">{fmtClock(now)}</div>
          <div className="label-micro mt-1">{after ? "perimeter armed · night watch" : tpl.modes.show.replace("● ", "").toLowerCase()}</div>
        </div>

        <div className="hidden sm:flex items-center gap-3 pl-3 border-l" style={{ borderColor: "#1a2540" }}>
          <div className="flex flex-col items-center gap-1" title="All alerts are silent — routed to devices, no audible alarm on the floor">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#34d399" strokeWidth="1.8">
              <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
              <path d="M13.7 21a2 2 0 0 1-3.4 0" />
              <line x1="4" y1="4" x2="20" y2="20" strokeWidth="1.6" />
            </svg>
            <span className="label-micro" style={{ color: "#34d399" }}>silent</span>
          </div>
          <div className="flex flex-col items-center gap-1" title={`${cams.filter((c) => c.online).length}/${cams.length} cameras online`}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#22d3ee" strokeWidth="1.8">
              <path d="M23 7l-7 5 7 5V7z" />
              <rect x="1" y="5" width="15" height="14" rx="2" />
            </svg>
            <span className="label-micro" style={{ color: "#22d3ee" }}>
              {cams.filter((c) => c.online).length}/{cams.length}
            </span>
          </div>
          {openP1 > 0 && (
            <div className="flex flex-col items-center gap-1">
              <span className="text-[13px] font-bold anim-blink" style={{ color: "#f87171" }}>
                {openP1}
              </span>
              <span className="label-micro" style={{ color: "#f87171" }}>open p1</span>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
