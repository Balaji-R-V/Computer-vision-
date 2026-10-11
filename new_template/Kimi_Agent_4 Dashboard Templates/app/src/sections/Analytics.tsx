import type { ClassMethod, WorldState } from "@/types";
import { relTime } from "@/lib/ui";

/* ---------------- Threat recognition & access control ---------------- */

function ThreatAccess({ world }: { world: WorldState }) {
  return (
    <div className="panel flex flex-col">
      <div className="panel-title">
        <span className="led anim-pulse-dot" style={{ color: "#f87171", background: "#f87171" }} />
        Threat recognition &amp; access
      </div>
      <div className="p-3 space-y-3 flex-1">
        {/* watchlist */}
        <div>
          <div className="label-micro mb-1.5">{world.template.blacklist.title}</div>
          {world.blacklist.length === 0 ? (
            <div className="border border-dashed rounded px-3 py-3 text-[10px]" style={{ borderColor: "#22304f", color: "#4a5a76" }}>
              {world.template.blacklist.emptyText}
            </div>
          ) : (
            <div className="space-y-1.5">
              {world.blacklist.map((b) => (
                <div key={b.id} className="flex items-center gap-2.5 rounded border px-2.5 py-2" style={{ borderColor: b.status === "TRACKING" ? "rgba(248,113,113,0.45)" : "#1a2540", background: b.status === "TRACKING" ? "rgba(248,113,113,0.06)" : "transparent" }}>
                  {/* synthetic face chip */}
                  <svg width="26" height="26" viewBox="0 0 26 26" className="shrink-0">
                    <rect x="1" y="1" width="24" height="24" rx="3" fill="#0a1120" stroke={b.status === "TRACKING" ? "#f87171" : "#22304f"} />
                    <circle cx="13" cy="10" r="4" fill="none" stroke="#8494ad" strokeWidth="1.2" />
                    <path d="M6.5 21c1.2-3.4 3.6-5 6.5-5s5.3 1.6 6.5 5" fill="none" stroke="#8494ad" strokeWidth="1.2" />
                    <path d="M4 4h4M4 4v4M22 4h-4M22 4v4M4 22h4M4 22v-4M22 22h-4M22 22v-4" stroke={b.status === "TRACKING" ? "#f87171" : "#34d399"} strokeWidth="1.3" />
                  </svg>
                  <div className="min-w-0">
                    <div className="text-[10.5px] font-bold text-white truncate">{b.alias}</div>
                    <div className="text-[9px] truncate" style={{ color: "#4a5a76" }}>
                      {b.knownFor}
                    </div>
                  </div>
                  <div className="ml-auto text-right shrink-0">
                    <div className="text-[11px] font-bold tabular-nums" style={{ color: "#f87171" }}>
                      {b.confidence.toFixed(1)}%
                    </div>
                    <div className="text-[8.5px] tracking-[0.12em]" style={{ color: b.status === "TRACKING" ? "#f87171" : "#34d399" }}>
                      {b.status}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        {/* vault log */}
        <div>
          <div className="label-micro mb-1.5">{world.template.access.logTitle}</div>
          <div className="rounded border divide-y" style={{ borderColor: "#1a2540", background: "rgba(5,8,16,0.4)" }}>
            {world.access.slice(0, 6).map((a) => (
              <div key={a.id} className="flex items-center gap-2 px-2.5 py-1.5">
                <span
                  className="text-[8.5px] font-black tracking-[0.1em] px-1 py-0.5 rounded"
                  style={
                    a.result === "GRANTED"
                      ? { color: "#34d399", background: "rgba(52,211,153,0.1)" }
                      : { color: "#f87171", background: "rgba(248,113,113,0.12)" }
                  }
                >
                  {a.result}
                </span>
                <div className="min-w-0">
                  <div className="text-[10px] text-[#c6d0e0] truncate">
                    {a.person} <span style={{ color: "#4a5a76" }}>→ {a.zone}</span>
                  </div>
                  {a.note && (
                    <div className="text-[8.5px]" style={{ color: "#f87171" }}>
                      {a.note}
                    </div>
                  )}
                </div>
                <span className="ml-auto text-[8.5px] shrink-0" style={{ color: "#4a5a76" }}>
                  {a.method}
                </span>
              </div>
            ))}
          </div>
          <div className="mt-1.5 text-[8.5px] leading-relaxed" style={{ color: "#4a5a76" }}>
            {world.template.access.note}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ---------------- VIP arrivals ---------------- */

function VipPanel({ world, onGreet }: { world: WorldState; onGreet: (id: string) => void }) {
  return (
    <div className="panel flex flex-col">
      <div className="panel-title">
        <span className="led anim-pulse-dot" style={{ color: "#e879f9", background: "#e879f9" }} />
        {world.template.vip.title}
        <span className="ml-auto text-[9px]" style={{ color: "#4a5a76" }}>
          {world.template.vip.subtitle}
        </span>
      </div>
      <div className="p-3 space-y-1.5 flex-1">
        {world.vips.length === 0 && (
          <div className="border border-dashed rounded px-3 py-4 text-[10px] text-center" style={{ borderColor: "#22304f", color: "#4a5a76" }}>
            {world.template.vip.emptyText}
          </div>
        )}
        {world.vips.slice(0, 5).map((v) => (
          <div key={v.id} className="flex items-center gap-2.5 rounded border px-2.5 py-2" style={{ borderColor: v.greeted ? "#1a2540" : "rgba(232,121,249,0.4)", background: v.greeted ? "transparent" : "rgba(232,121,249,0.05)" }}>
            <div
              className="grid place-items-center w-7 h-7 rounded-full text-[10px] font-black shrink-0"
              style={{
                background: v.tier === "PLATINUM" ? "linear-gradient(135deg,#e879f9,#8b5cf6)" : "linear-gradient(135deg,#fbbf24,#d97706)",
                color: "#0a0f1a",
              }}
            >
              {v.name.split(" ").map((n) => n[0]).slice(0, 2).join("")}
            </div>
            <div className="min-w-0">
              <div className="text-[10.5px] font-bold text-white truncate">{v.name}</div>
              <div className="text-[8.5px] truncate" style={{ color: "#4a5a76" }}>
                {v.spendBand} · into {v.interest}
              </div>
            </div>
            <div className="ml-auto text-right shrink-0">
              {v.greeted ? (
                <div className="text-[8.5px] tracking-[0.12em]" style={{ color: "#34d399" }}>
                  ✓ GREETED · {v.director}
                </div>
              ) : (
                <button
                  onClick={() => onGreet(v.id)}
                  className="text-[8.5px] font-bold tracking-[0.12em] px-2 py-1 rounded transition-colors hover:text-white"
                  style={{ color: "#e879f9", background: "rgba(232,121,249,0.1)", boxShadow: "inset 0 0 0 1px rgba(232,121,249,0.4)" }}
                >
                  ASSIGN {v.director}
                </button>
              )}
              <div className="text-[8px] mt-0.5" style={{ color: "#4a5a76" }}>
                {relTime(v.tick, world.tick)}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ---------------- Organizer analytics / booth valuation ---------------- */

function roiGrade(traffic: number, avgDwell: number): { g: string; c: string } {
  const score = traffic * 0.6 + avgDwell * 2.2;
  if (score > 260) return { g: "A+", c: "#34d399" };
  if (score > 190) return { g: "A", c: "#34d399" };
  if (score > 130) return { g: "B", c: "#22d3ee" };
  return { g: "C", c: "#fbbf24" };
}

function BoothIntel({ world }: { world: WorldState }) {
  const rows = [...world.booths]
    .map((b) => ({ ...b, avgDwell: b.dwellSum / Math.max(1, b.traffic) }))
    .sort((a, b) => b.traffic - a.traffic);
  const maxTraffic = Math.max(...rows.map((r) => r.traffic), 1);
  const totalDwell = world.booths.reduce((s, b) => s + b.dwellSum, 0);

  return (
    <div className="panel flex flex-col">
      <div className="panel-title">
        <span className="led anim-pulse-dot" style={{ color: "#fbbf24", background: "#fbbf24" }} />
        {world.template.analytics.panelTitle}
        <span className="ml-auto text-[9px]" style={{ color: "#4a5a76" }}>
          staff excluded from counts
        </span>
      </div>
      <div className="p-3 flex-1 flex flex-col">
        <div className="grid grid-cols-3 gap-2 mb-2.5">
          {(
            [
              [world.template.analytics.visitLabel, world.booths.reduce((s, b) => s + b.traffic, 0).toLocaleString(), "#22d3ee"],
              ["TOTAL DWELL", `${Math.round(totalDwell / 60)} min`, "#fbbf24"],
              ["AVG DWELL / VISIT", `${Math.round(totalDwell / Math.max(1, world.booths.reduce((s, b) => s + b.traffic, 0)))}s`, "#34d399"],
            ] as const
          ).map(([l, v, c]) => (
            <div key={l} className="rounded border px-2 py-1.5" style={{ borderColor: "#1a2540", background: "rgba(5,8,16,0.4)" }}>
              <div className="label-micro">{l}</div>
              <div className="text-[14px] font-bold tabular-nums mt-0.5" style={{ color: c }}>
                {v}
              </div>
            </div>
          ))}
        </div>

        <div className="space-y-1 flex-1">
          {rows.map((b, i) => {
            const roi = roiGrade(b.traffic, b.avgDwell);
            return (
              <div key={b.id} className="flex items-center gap-2">
                <span className="text-[9px] w-3 tabular-nums" style={{ color: "#4a5a76" }}>
                  {i + 1}
                </span>
                <span className="text-[9.5px] font-bold w-6" style={{ color: b.tier === "high" ? "#22d3ee" : "#8494ad" }}>
                  {b.id}
                </span>
                <div className="flex-1 h-3.5 rounded-sm overflow-hidden" style={{ background: "rgba(26,37,64,0.5)" }}>
                  <div
                    className="h-full rounded-sm transition-all duration-700"
                    style={{
                      width: `${(b.traffic / maxTraffic) * 100}%`,
                      background: `linear-gradient(90deg, ${roi.c}55, ${roi.c})`,
                    }}
                  />
                </div>
                <span className="text-[9px] tabular-nums w-10 text-right" style={{ color: "#8494ad" }}>
                  {b.traffic}
                </span>
                <span className="text-[9px] tabular-nums w-8 text-right" style={{ color: "#4a5a76" }}>
                  {Math.round(b.avgDwell)}s
                </span>
                <span className="text-[9px] font-black w-6 text-right" style={{ color: roi.c }}>
                  {roi.g}
                </span>
              </div>
            );
          })}
        </div>

        <div className="mt-2.5 rounded border px-2.5 py-2" style={{ borderColor: "rgba(251,191,36,0.3)", background: "rgba(251,191,36,0.05)" }}>
          <div className="text-[8.5px] font-bold tracking-[0.14em]" style={{ color: "#fbbf24" }}>
            {world.template.analytics.staffingTitle}
          </div>
          <div className="text-[9.5px] mt-1 font-sans-reading leading-relaxed" style={{ color: "#b8c4d8" }}>
            {world.staffingGap && world.staffingGap.ratio > 3
              ? world.template.analytics.staffing(world.staffingGap.booth, world.staffingGap.ratio.toFixed(1))
              : world.template.analytics.balanced}
          </div>
        </div>
        <div className="mt-1.5 text-[8.5px]" style={{ color: "#4a5a76" }}>
          {world.template.analytics.footer}
        </div>
      </div>
    </div>
  );
}

/* ---------------- Staff vs attendee classification ---------------- */

const METHOD_META: Record<ClassMethod, { color: string; desc: string }> = {
  "UNIFORM COLOR": { color: "#22d3ee", desc: "black-suit / colour rules" },
  "LANYARD / BADGE": { color: "#34d399", desc: "reflective badge on chest" },
  "FACE WHITELIST": { color: "#e879f9", desc: "continuous re-verification" },
  "BEHAVIORAL PATH": { color: "#fbbf24", desc: "dwell + movement vectors" },
};

function Classification({ world }: { world: WorldState }) {
  const total = Math.max(1, Object.values(world.classMix).reduce((s, n) => s + n, 0));
  const { staff, attendees, vip, unknown } = world.counts;

  return (
    <div className="panel flex flex-col">
      <div className="panel-title">
        <span className="led anim-pulse-dot" style={{ color: "#34d399", background: "#34d399" }} />
        Staff vs attendee · layered classification
      </div>
      <div className="p-3 flex-1 flex flex-col">
        <div className="flex items-end gap-4 mb-3">
          {(
            [
              [world.template.visitorsLabel, attendees, "#8fa0bd"],
              ["STAFF", staff, "#34d399"],
              ["VIP", vip, "#e879f9"],
              ["UNRESOLVED", unknown, "#f87171"],
            ] as const
          ).map(([l, v, c]) => (
            <div key={l}>
              <div className="text-[20px] font-black tabular-nums leading-none" style={{ color: c }}>
                {v}
              </div>
              <div className="label-micro mt-1">{l}</div>
            </div>
          ))}
        </div>

        {/* stacked bar */}
        <div className="label-micro mb-1">Classification method in force</div>
        <div className="flex h-4 rounded-sm overflow-hidden border" style={{ borderColor: "#1a2540" }}>
          {(Object.keys(METHOD_META) as ClassMethod[]).map((m) => {
            const pct = (world.classMix[m] / total) * 100;
            if (pct < 0.5) return null;
            return (
              <div
                key={m}
                className="h-full transition-all duration-700"
                style={{ width: `${pct}%`, background: `${METHOD_META[m].color}cc` }}
                title={`${m}: ${world.classMix[m]}`}
              />
            );
          })}
        </div>
        <div className="mt-2 space-y-1">
          {(Object.keys(METHOD_META) as ClassMethod[]).map((m) => (
            <div key={m} className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: METHOD_META[m].color, boxShadow: `0 0 4px ${METHOD_META[m].color}` }} />
              <span className="text-[9px] font-bold tracking-wider" style={{ color: "#c6d0e0" }}>
                {m}
              </span>
              <span className="text-[8.5px]" style={{ color: "#4a5a76" }}>
                {METHOD_META[m].desc}
              </span>
              <span className="ml-auto text-[9px] tabular-nums" style={{ color: METHOD_META[m].color }}>
                {world.classMix[m]}
              </span>
            </div>
          ))}
        </div>

        <div className="mt-auto pt-2.5">
          <div className="rounded border px-2.5 py-2" style={{ borderColor: "rgba(52,211,153,0.3)", background: "rgba(52,211,153,0.05)" }}>
            <div className="text-[8.5px] font-bold tracking-[0.14em]" style={{ color: "#34d399" }}>
              {world.template.classification.whyTitle}
            </div>
            <div className="text-[9.5px] mt-1 font-sans-reading leading-relaxed" style={{ color: "#b8c4d8" }}>
              {world.template.classification.whyText}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Analytics({ world, onGreet }: { world: WorldState; onGreet: (id: string) => void }) {
  return (
    <section className="px-4 pb-4 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3 items-stretch">
      <ThreatAccess world={world} />
      <VipPanel world={world} onGreet={onGreet} />
      <BoothIntel world={world} />
      <Classification world={world} />
    </section>
  );
}
