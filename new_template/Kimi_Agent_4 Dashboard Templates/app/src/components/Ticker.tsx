import type { WorldState } from "@/types";
import { SEV_COLOR } from "@/lib/ui";

export default function Ticker({ world }: { world: WorldState }) {
  const items = world.alerts.slice(-14).reverse();
  if (items.length === 0) {
    items.push({
      id: "init",
      tick: 0,
      severity: "P3",
      type: "PERIMETER",
      title: "All zones nominal — behavioural baselines stable",
      detail: "",
      location: "Hall B",
      cam: "ALL",
      devices: [],
      clipSec: 0,
      status: "acked",
      silent: true,
    });
  }
  const line = items.map((a) => (
    <span key={a.id} className="inline-flex items-center gap-2 mx-6">
      <span className="led" style={{ color: SEV_COLOR[a.severity], background: SEV_COLOR[a.severity] }} />
      <span className="font-bold" style={{ color: SEV_COLOR[a.severity] }}>
        {a.severity}
      </span>
      <span className="text-[#8494ad]">{a.type}</span>
      <span className="text-[#dbe4f0]">{a.title}</span>
      <span className="text-[#4a5a76]">· {a.location}</span>
      {a.silent && <span className="text-[#34d399] opacity-80">⌁ SILENT→DEVICES</span>}
    </span>
  ));
  return (
    <div className="ticker-mask relative overflow-hidden border-b h-8 flex items-center" style={{ borderColor: "#1a2540", background: "#070b16" }}>
      <div className="anim-ticker flex whitespace-nowrap text-[10px] tracking-wider">
        <div className="flex">{line}</div>
        <div className="flex" aria-hidden>
          {line}
        </div>
      </div>
      <div className="absolute inset-y-0 left-0 w-16 bg-gradient-to-r from-[#070b16] to-transparent pointer-events-none" />
      <div className="absolute inset-y-0 right-0 w-16 bg-gradient-to-l from-[#070b16] to-transparent pointer-events-none" />
    </div>
  );
}
