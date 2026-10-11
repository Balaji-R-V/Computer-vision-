import { useEffect, useRef, useState } from "react";
import { BACKROOM, ENTRANCE, FLOOR_H, FLOOR_W, VAULT } from "@/lib/sim";
import type { Person, WorldState } from "@/types";

const ROLE_COLOR: Record<Person["role"], string> = {
  staff: "#34d399",
  contractor: "#34d399",
  attendee: "#8fa0bd",
  vip: "#e879f9",
  blacklist: "#f87171",
};

type Layers = { heat: boolean; tethers: boolean; paths: boolean; labels: boolean };

function alertAnchor(loc: string): { x: number; y: number } | null {
  if (loc.startsWith("Main Entrance")) return { x: ENTRANCE.x, y: ENTRANCE.y - 24 };
  if (loc.startsWith("Vault") || loc.startsWith("Safe")) return { x: VAULT.x + VAULT.w / 2, y: VAULT.y + VAULT.h / 2 };
  if (loc.startsWith("Backroom")) return { x: BACKROOM.x + BACKROOM.w / 2, y: BACKROOM.y + BACKROOM.h / 2 };
  return null; // booth ids handled by caller
}

export default function FloorPlan({ world }: { world: WorldState }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const worldRef = useRef(world);
  worldRef.current = world;
  const [layers, setLayers] = useState<Layers>({ heat: true, tethers: true, paths: true, labels: true });
  const layersRef = useRef(layers);
  layersRef.current = layers;

  useEffect(() => {
    const canvas = canvasRef.current!;
    const ctx = canvas.getContext("2d")!;
    let raf = 0;

    const render = (ms: number) => {
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
        canvas.width = w * dpr;
        canvas.height = h * dpr;
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      const S = Math.min(w / FLOOR_W, h / FLOOR_H);
      const ox = (w - FLOOR_W * S) / 2;
      const oy = (h - FLOOR_H * S) / 2;
      const X = (x: number) => ox + x * S;
      const Y = (y: number) => oy + y * S;

      const state = worldRef.current;
      const tpl = state.template;
      const L = layersRef.current;
      const t = ms / 1000;
      const after = state.mode === "after";

      /* base */
      ctx.fillStyle = "#070b16";
      ctx.fillRect(0, 0, w, h);
      const rg = ctx.createRadialGradient(w / 2, h * 0.4, 40, w / 2, h * 0.5, w * 0.7);
      rg.addColorStop(0, after ? "rgba(232,121,249,0.05)" : "rgba(34,211,238,0.05)");
      rg.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = rg;
      ctx.fillRect(0, 0, w, h);

      /* floor grid */
      ctx.strokeStyle = "rgba(26,37,64,0.5)";
      ctx.lineWidth = 1;
      for (let gx = 0; gx <= FLOOR_W; gx += 50) {
        ctx.beginPath();
        ctx.moveTo(X(gx), Y(0));
        ctx.lineTo(X(gx), Y(FLOOR_H));
        ctx.stroke();
      }
      for (let gy = 0; gy <= FLOOR_H; gy += 50) {
        ctx.beginPath();
        ctx.moveTo(X(0), Y(gy));
        ctx.lineTo(X(FLOOR_W), Y(gy));
        ctx.stroke();
      }

      /* hall outline + perimeter */
      ctx.strokeStyle = after ? "rgba(232,121,249,0.7)" : "#22304f";
      ctx.lineWidth = after ? 2 : 1.5;
      ctx.strokeRect(X(8), Y(8), (FLOOR_W - 16) * S, (FLOOR_H - 16) * S);
      if (after) {
        ctx.save();
        ctx.setLineDash([10, 8]);
        ctx.lineDashOffset = -t * 30;
        ctx.strokeStyle = "rgba(232,121,249,0.5)";
        ctx.strokeRect(X(16), Y(16), (FLOOR_W - 32) * S, (FLOOR_H - 32) * S);
        ctx.restore();
      }

      /* aisle flow lines */
      ctx.save();
      ctx.setLineDash([6, 10]);
      ctx.lineDashOffset = -t * 22;
      ctx.strokeStyle = "rgba(34,211,238,0.16)";
      ctx.lineWidth = 1.2;
      for (const ay of [330, 356]) {
        ctx.beginPath();
        ctx.moveTo(X(40), Y(ay));
        ctx.lineTo(X(FLOOR_W - 40), Y(ay));
        ctx.stroke();
      }
      ctx.restore();

      /* heat layer */
      if (L.heat && !after) {
        const maxDwell = Math.max(...state.booths.map((b) => b.dwellSum), 1);
        for (const b of state.booths) {
          const cx = X(b.x + b.w / 2);
          const cy = Y(b.y + b.h + 30);
          const norm = b.dwellSum / maxDwell;
          const intensity = 0.1 + norm * 0.34;
          const rad = b.w * (0.42 + norm * 0.22) * S;
          const g = ctx.createRadialGradient(cx, cy, 3, cx, cy, rad);
          g.addColorStop(0, `rgba(251,191,36,${intensity})`);
          g.addColorStop(0.5, `rgba(251,191,36,${intensity * 0.4})`);
          g.addColorStop(1, "rgba(0,0,0,0)");
          ctx.fillStyle = g;
          ctx.fillRect(cx - rad, cy - rad * 0.6, rad * 2, rad * 1.2);
        }
      }

      /* rooms: vault + backroom */
      const room = (r: { x: number; y: number; w: number; h: number }, label: string, accent: string) => {
        ctx.fillStyle = "rgba(12,18,32,0.9)";
        ctx.fillRect(X(r.x), Y(r.y), r.w * S, r.h * S);
        ctx.strokeStyle = accent;
        ctx.lineWidth = 1.2;
        ctx.strokeRect(X(r.x), Y(r.y), r.w * S, r.h * S);
        // hatch
        ctx.save();
        ctx.beginPath();
        ctx.rect(X(r.x), Y(r.y), r.w * S, r.h * S);
        ctx.clip();
        ctx.strokeStyle = "rgba(34,211,238,0.08)";
        for (let i = -r.h; i < r.w; i += 12) {
          ctx.beginPath();
          ctx.moveTo(X(r.x + i), Y(r.y));
          ctx.lineTo(X(r.x + i + r.h), Y(r.y + r.h));
          ctx.stroke();
        }
        ctx.restore();
        ctx.fillStyle = "#dbe4f0";
        ctx.font = `700 ${10 * S + 4}px "JetBrains Mono", monospace`;
        ctx.fillText(label, X(r.x) + 8, Y(r.y) + 16 * S + 6);
        ctx.fillStyle = after ? "#e879f9" : "#34d399";
        ctx.font = `600 ${8 * S + 3}px "JetBrains Mono", monospace`;
        ctx.fillText(after ? "ARMED · BIOMETRIC" : "WHITELIST ACCESS", X(r.x) + 8, Y(r.y) + 30 * S + 6);
        // door
        ctx.fillStyle = "#22d3ee";
        ctx.fillRect(X(r.x + r.w) - 2, Y(r.y + r.h / 2 - 8), 4, 16 * S + 6);
      };
      room(VAULT, tpl.rooms.vault, "rgba(34,211,238,0.55)");
      room(BACKROOM, tpl.rooms.backroom, "rgba(34,211,238,0.4)");

      /* tether zones */
      if (L.tethers) {
        for (const b of state.booths) {
          if (b.tier !== "high") continue;
          ctx.save();
          ctx.setLineDash([6, 5]);
          ctx.lineDashOffset = -t * 16;
          const pulse = 0.45 + Math.sin(t * 2.2) * 0.15;
          ctx.strokeStyle = `rgba(34,211,238,${pulse})`;
          ctx.lineWidth = 1.4;
          ctx.strokeRect(X(b.x - 22), Y(b.y - 14), (b.w + 44) * S, (b.h + 64) * S);
          ctx.restore();
        }
      }

      /* booths */
      for (const b of state.booths) {
        const bx = X(b.x);
        const by = Y(b.y);
        ctx.fillStyle = b.tier === "high" ? "rgba(17,26,43,0.95)" : "rgba(12,18,32,0.85)";
        ctx.fillRect(bx, by, b.w * S, b.h * S);
        ctx.strokeStyle = b.tier === "high" ? "rgba(34,211,238,0.65)" : "#22304f";
        ctx.lineWidth = b.tier === "high" ? 1.4 : 1;
        ctx.strokeRect(bx, by, b.w * S, b.h * S);
        // vitrine strip (display case line facing aisle)
        ctx.fillStyle = b.tier === "high" ? "rgba(34,211,238,0.35)" : "rgba(132,148,173,0.25)";
        ctx.fillRect(bx + 4, by + b.h * S - 5, b.w * S - 8, 3);
        if (L.labels) {
          ctx.fillStyle = b.tier === "high" ? "#22d3ee" : "#8494ad";
          ctx.font = `700 ${9 * S + 3.5}px "JetBrains Mono", monospace`;
          ctx.fillText(b.id, bx + 7, by + 15 * S + 4);
          ctx.fillStyle = "#4a5a76";
          ctx.font = `500 ${8 * S + 2.5}px "JetBrains Mono", monospace`;
          ctx.fillText(b.name.toUpperCase().slice(0, 22), bx + 7, by + 27 * S + 6);
          if (b.tier === "high") {
            ctx.fillStyle = "rgba(34,211,238,0.75)";
            ctx.font = `600 ${7.5 * S + 2.5}px "JetBrains Mono", monospace`;
            ctx.fillText("◇ HIGH VALUE · TETHERED", bx + 7, by + b.h * S - 12);
          }
        }
        // density badge
        if (!after && b.density > 0) {
          ctx.fillStyle = "rgba(5,8,16,0.85)";
          const label = `${b.density}`;
          ctx.fillRect(bx + b.w * S - 22, by + 4, 18, 13);
          ctx.strokeStyle = "#22304f";
          ctx.strokeRect(bx + b.w * S - 22, by + 4, 18, 13);
          ctx.fillStyle = b.density > 6 ? "#fbbf24" : "#dbe4f0";
          ctx.font = `700 9px "JetBrains Mono", monospace`;
          ctx.fillText(label, bx + b.w * S - 17, by + 14);
        }
      }

      /* entrance */
      ctx.strokeStyle = "#34d399";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(X(ENTRANCE.x - 46), Y(ENTRANCE.y + 22));
      ctx.lineTo(X(ENTRANCE.x + 46), Y(ENTRANCE.y + 22));
      ctx.stroke();
      if (L.labels) {
        ctx.fillStyle = "#34d399";
        ctx.font = `700 ${8.5 * S + 3}px "JetBrains Mono", monospace`;
        ctx.textAlign = "center";
        ctx.fillText(tpl.entranceLabel, X(ENTRANCE.x), Y(ENTRANCE.y + 12));
        ctx.textAlign = "left";
      }

      /* paths */
      if (L.paths) {
        for (const p of state.people) {
          if (p.path.length < 3) continue;
          ctx.beginPath();
          p.path.forEach((pt, i) => {
            if (i === 0) ctx.moveTo(X(pt.x), Y(pt.y));
            else ctx.lineTo(X(pt.x), Y(pt.y));
          });
          ctx.strokeStyle = ROLE_COLOR[p.role] + "2e";
          ctx.lineWidth = 1;
          ctx.stroke();
        }
      }

      /* people dots */
      for (const p of state.people) {
        const px = X(p.x);
        const py = Y(p.y);
        const col = ROLE_COLOR[p.role];
        const bob = Math.sin(t * 2 + p.x * 0.05) * 0.6;
        ctx.beginPath();
        ctx.arc(px, py + bob, p.role === "staff" || p.role === "contractor" ? 2.6 : 2.2, 0, Math.PI * 2);
        ctx.fillStyle = col;
        ctx.shadowColor = col;
        ctx.shadowBlur = 6;
        ctx.fill();
        ctx.shadowBlur = 0;
        if (p.role === "blacklist") {
          const rr = 6 + ((t * 14 + p.y) % 10);
          ctx.beginPath();
          ctx.arc(px, py, rr, 0, Math.PI * 2);
          ctx.strokeStyle = `rgba(248,113,113,${Math.max(0, 0.8 - rr / 14)})`;
          ctx.lineWidth = 1.2;
          ctx.stroke();
        } else if (p.flagged) {
          ctx.beginPath();
          ctx.arc(px, py, 5, 0, Math.PI * 2);
          ctx.strokeStyle = "#fbbf24";
          ctx.lineWidth = 1.2;
          ctx.stroke();
        } else if (p.role === "vip") {
          ctx.beginPath();
          ctx.arc(px, py, 4.5, 0, Math.PI * 2);
          ctx.strokeStyle = "#e879f9";
          ctx.lineWidth = 1;
          ctx.stroke();
        }
      }

      /* alert ping rings */
      const recentAlerts = state.alerts.filter((a) => state.tick - a.tick < 10 && a.status !== "acked");
      for (const a of recentAlerts) {
        let pt = alertAnchor(a.location);
        if (!pt) {
          const booth = state.booths.find((b) => a.location.startsWith(b.id));
          if (booth) pt = { x: booth.x + booth.w / 2, y: booth.y + booth.h / 2 };
        }
        if (!pt) continue;
        const col = a.severity === "P1" ? "248,113,113" : a.severity === "P2" ? "251,191,36" : "34,211,238";
        for (let k = 0; k < 2; k++) {
          const phase = ((t * 0.9 + k * 0.5) % 1.6) / 1.6;
          ctx.beginPath();
          ctx.arc(X(pt.x), Y(pt.y), 6 + phase * 46 * S * 2, 0, Math.PI * 2);
          ctx.strokeStyle = `rgba(${col},${(1 - phase) * 0.65})`;
          ctx.lineWidth = 1.6;
          ctx.stroke();
        }
      }

      /* after-hours dim on public floor */
      if (after) {
        ctx.fillStyle = "rgba(3,5,10,0.35)";
        ctx.fillRect(X(8), Y(8), (FLOOR_W - 16) * S, (FLOOR_H - 16) * S);
        // redraw vault area to pop
        ctx.fillStyle = "rgba(232,121,249,0.06)";
        ctx.fillRect(X(VAULT.x - 30), Y(VAULT.y - 14), (VAULT.w + 80) * S, (VAULT.h + 60) * S);
      }

      raf = requestAnimationFrame(render);
    };
    raf = requestAnimationFrame(render);
    return () => cancelAnimationFrame(raf);
  }, []);

  const toggle = (k: keyof Layers) => setLayers((l) => ({ ...l, [k]: !l[k] }));
  const layerBtn = (k: keyof Layers, label: string, color: string) => (
    <button
      key={k}
      onClick={() => toggle(k)}
      className="flex items-center gap-1.5 px-2 h-6 rounded text-[9px] font-bold tracking-[0.14em] transition-all duration-150"
      style={{
        color: layers[k] ? color : "#4a5a76",
        background: layers[k] ? `${color}14` : "transparent",
        boxShadow: layers[k] ? `inset 0 0 0 1px ${color}55` : "inset 0 0 0 1px #1a2540",
      }}
    >
      <span className="led" style={{ color: layers[k] ? color : "#2a3a5c", background: layers[k] ? color : "#2a3a5c" }} />
      {label}
    </button>
  );

  return (
    <div className="panel relative overflow-hidden scanlines flex flex-col h-full">
      <div className="panel-title">
        <span className="led anim-pulse-dot" style={{ color: "#22d3ee", background: "#22d3ee" }} />
        {world.template.floorName}
        <span className="ml-auto flex items-center gap-1.5">
          {layerBtn("heat", "HEAT", "#fbbf24")}
          {layerBtn("tethers", "TETHERS", "#22d3ee")}
          {layerBtn("paths", "PATHS", "#34d399")}
          {layerBtn("labels", "LABELS", "#8494ad")}
        </span>
      </div>
      <div className="relative flex-1 min-h-[340px]">
        <canvas ref={canvasRef} style={{ width: "100%", height: "100%", display: "block" }} />
        {/* legend */}
        <div className="absolute left-2 bottom-2 glass rounded px-2.5 py-2 space-y-1 z-10">
          {(
            [
              ["#8fa0bd", world.template.visitorsLabel.slice(0, -1)],
              ["#34d399", "STAFF / WHITELIST"],
              ["#e879f9", "VIP"],
              ["#f87171", "WATCHLIST"],
              ["#fbbf24", "FLAGGED LOITER"],
            ] as const
          ).map(([c, l]) => (
            <div key={l} className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full" style={{ background: c, boxShadow: `0 0 5px ${c}` }} />
              <span className="text-[8px] tracking-[0.12em]" style={{ color: "#8494ad" }}>
                {l}
              </span>
            </div>
          ))}
        </div>
        <div className="absolute right-2 top-2 glass rounded px-2 py-1 z-10 text-[8px] tracking-[0.14em]" style={{ color: world.mode === "after" ? "#e879f9" : "#34d399" }}>
          {world.mode === "after" ? world.template.modes.afterBadge : world.template.modes.showBadge}
        </div>
      </div>
    </div>
  );
}
