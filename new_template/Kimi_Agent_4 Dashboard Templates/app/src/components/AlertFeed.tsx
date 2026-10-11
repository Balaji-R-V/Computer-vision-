import type { Alert, WorldState } from "@/types";
import { SEV_COLOR, SEV_LABEL, relTime } from "@/lib/ui";

function WatchIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="7" y="6" width="10" height="12" rx="2.5" />
      <path d="M9 6l.6-3h4.8L15 6M9 18l.6 3h4.8l.6-3" />
    </svg>
  );
}
function PhoneIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="6" y="2" width="12" height="20" rx="2.5" />
      <line x1="10" y1="19" x2="14" y2="19" />
    </svg>
  );
}
function ClipIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polygon points="6 3 20 12 6 21 6 3" fill="currentColor" stroke="none" />
    </svg>
  );
}

function AlertCard({ alert, now, onAck }: { alert: Alert; now: number; onAck: (id: string) => void }) {
  const c = SEV_COLOR[alert.severity];
  const open = alert.status !== "acked";
  return (
    <article
      className="anim-alert-in relative rounded-r border-y border-r pl-3 pr-2.5 py-2.5 transition-opacity duration-300"
      style={{
        borderColor: "#1a2540",
        borderLeft: `3px solid ${c}`,
        background: open ? `linear-gradient(90deg, ${c}0d 0%, rgba(12,18,32,0.6) 55%)` : "rgba(12,18,32,0.35)",
        opacity: open ? 1 : 0.45,
      }}
    >
      <div className="flex items-center gap-2">
        <span className="text-[9px] font-black tracking-[0.14em] px-1.5 py-0.5 rounded" style={{ color: c, background: `${c}1a`, boxShadow: `inset 0 0 0 1px ${c}44` }}>
          {alert.severity} · {SEV_LABEL[alert.severity]}
        </span>
        <span className="text-[9px] tracking-[0.12em]" style={{ color: "#4a5a76" }}>
          {alert.id}
        </span>
        <span className="ml-auto text-[9px] tabular-nums" style={{ color: "#4a5a76" }}>
          {relTime(alert.tick, now)}
        </span>
      </div>
      <h4 className="mt-1.5 text-[11.5px] font-bold leading-snug" style={{ color: open ? "#eef3fa" : "#8494ad" }}>
        {alert.title}
      </h4>
      <p className="mt-1 text-[10px] leading-relaxed font-sans-reading" style={{ color: "#8494ad" }}>
        {alert.detail}
      </p>
      <div className="mt-2 flex items-center gap-2 flex-wrap">
        <span className="text-[9px] tracking-wider" style={{ color: "#4a5a76" }}>
          {alert.location} · {alert.cam}
        </span>
        <span className="flex-1" />
        {alert.silent && (
          <span className="flex items-center gap-1 text-[8.5px] tracking-[0.1em]" style={{ color: "#34d399" }} title="Silent alert — no audible alarm on the floor">
            ⌁ SILENT →
            {alert.devices.includes("watch") && <WatchIcon />}
            {alert.devices.includes("phone") && <PhoneIcon />}
          </span>
        )}
        <span className="flex items-center gap-1 text-[8.5px] tracking-wider px-1.5 py-0.5 rounded border" style={{ color: "#8494ad", borderColor: "#22304f" }} title="Video clip attached to alert">
          <ClipIcon /> {alert.clipSec}s
        </span>
        {open ? (
          <button
            onClick={() => onAck(alert.id)}
            className="text-[9px] font-bold tracking-[0.12em] px-2 py-0.5 rounded transition-colors duration-150 hover:text-white"
            style={{ color: c, background: `${c}14`, boxShadow: `inset 0 0 0 1px ${c}55` }}
          >
            {alert.status === "new" ? "DISPATCH…" : "ACKNOWLEDGE"}
          </button>
        ) : (
          <span className="text-[9px] tracking-[0.12em]" style={{ color: "#4a5a76" }}>
            ✓ ACKED
          </span>
        )}
      </div>
    </article>
  );
}

export default function AlertFeed({ world, onAck, onAckAll }: { world: WorldState; onAck: (id: string) => void; onAckAll: () => void }) {
  const alerts = [...world.alerts].reverse();
  const openCount = alerts.filter((a) => a.status !== "acked").length;

  return (
    <div className="panel relative overflow-hidden flex flex-col h-full">
      <div className="panel-title">
        <span className="led anim-pulse-dot" style={{ color: "#fbbf24", background: "#fbbf24" }} />
        Graded silent alerts
        <span className="ml-auto flex items-center gap-2">
          <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ color: "#fbbf24", background: "rgba(251,191,36,0.1)" }}>
            {openCount} OPEN
          </span>
          <button onClick={onAckAll} className="text-[9px] tracking-[0.12em] hover:text-white transition-colors" style={{ color: "#4a5a76" }}>
            ACK ALL
          </button>
        </span>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-2 min-h-0" style={{ maxHeight: "100%" }}>
        {alerts.length === 0 && (
          <div className="h-full grid place-items-center border border-dashed rounded" style={{ borderColor: "#22304f" }}>
            <div className="text-center py-10">
              <div className="text-[10px] tracking-[0.18em]" style={{ color: "#34d399" }}>
                ALL ZONES NOMINAL
              </div>
              <div className="text-[9px] mt-1" style={{ color: "#4a5a76" }}>
                AI is watching 4 feeds · baselines stable
              </div>
            </div>
          </div>
        )}
        {alerts.map((a) => (
          <AlertCard key={a.id} alert={a} now={world.tick} onAck={onAck} />
        ))}
      </div>
    </div>
  );
}
