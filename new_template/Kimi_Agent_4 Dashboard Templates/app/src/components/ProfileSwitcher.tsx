import { TEMPLATES, TEMPLATE_ORDER } from "@/lib/templates";
import type { TemplateId as Tid, WorldState as WS } from "@/types";

const TAB_COLORS: Record<Tid, string> = {
  expo: "#22d3ee",
  retail: "#fbbf24",
  restaurant: "#e879f9",
  office: "#34d399",
};

export default function ProfileSwitcher({ world, onSwitch }: { world: WS; onSwitch: (id: Tid) => void }) {
  return (
    <div className="flex items-center gap-3 px-4 h-10 border-b" style={{ borderColor: "#1a2540", background: "#070b16" }}>
      <span className="label-micro shrink-0">Deployment profile</span>
      <div className="flex items-center gap-1">
        {TEMPLATE_ORDER.map((id) => {
          const tpl = TEMPLATES[id];
          const active = world.template.id === id;
          const c = TAB_COLORS[id];
          return (
            <button
              key={id}
              onClick={() => onSwitch(id)}
              className="flex items-center gap-1.5 px-3 h-7 rounded text-[10px] font-bold tracking-[0.16em] transition-all duration-150"
              style={{
                color: active ? c : "#4a5a76",
                background: active ? `${c}14` : "transparent",
                boxShadow: active ? `inset 0 0 0 1px ${c}55` : "inset 0 0 0 1px transparent",
              }}
            >
              <span
                className="led"
                style={{
                  color: active ? c : "#2a3a5c",
                  background: active ? c : "#2a3a5c",
                }}
              />
              {tpl.tab}
            </button>
          );
        })}
      </div>
      <span className="hidden md:block text-[9px] tracking-wider truncate" style={{ color: "#2e3d5c" }}>
        — same AI engine, re-profiled zones, cameras, alert semantics &amp; analytics
      </span>
    </div>
  );
}
