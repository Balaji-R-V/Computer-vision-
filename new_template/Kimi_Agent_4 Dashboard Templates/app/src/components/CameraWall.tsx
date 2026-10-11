import { useEffect, useRef } from "react";
import type { CameraInfo, Person, WorldState } from "@/types";
import { tickToClock } from "@/lib/ui";

/* viewport windows into floor-plan coordinates */
const VIEWPORTS: Record<string, { x0: number; y0: number; w: number; h: number }> = {
  "CAM-01": { x0: 360, y0: 460, w: 280, h: 180 },
  "CAM-02": { x0: 90, y0: 120, w: 500, h: 210 },
  "CAM-03": { x0: 240, y0: 140, w: 520, h: 390 },
  "CAM-04": { x0: 0, y0: 0, w: 420, h: 160 },
};

const ROLE_COLOR: Record<Person["role"], string> = {
  staff: "#34d399",
  contractor: "#34d399",
  attendee: "#7d8fb0",
  vip: "#e879f9",
  blacklist: "#f87171",
};

function cornerBrackets(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, color: string, lw = 1.4) {
  const l = Math.min(w, h) * 0.28;
  ctx.strokeStyle = color;
  ctx.lineWidth = lw;
  ctx.beginPath();
  const seg = (cx: number, cy: number, dx: number, dy: number) => {
    ctx.moveTo(cx + dx * l, cy);
    ctx.lineTo(cx, cy);
    ctx.lineTo(cx, cy + dy * l);
  };
  seg(x, y, 1, 1);
  seg(x + w, y, -1, 1);
  seg(x, y + h, 1, -1);
  seg(x + w, y + h, -1, -1);
  ctx.stroke();
}

function drawFeed(
  ctx: CanvasRenderingContext2D,
  W: number,
  H: number,
  cam: CameraInfo,
  world: WorldState,
  timeMs: number,
  detail: boolean,
  bootTime: Date,
) {
  const vp = VIEWPORTS[cam.id];
  const t = timeMs / 1000;

  /* scene background */
  const bg = ctx.createLinearGradient(0, 0, 0, H);
  bg.addColorStop(0, "#060a14");
  bg.addColorStop(0.45, "#0a1120");
  bg.addColorStop(1, "#0d1526");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, W, H);

  /* perspective floor grid */
  ctx.strokeStyle = "rgba(34,211,238,0.06)";
  ctx.lineWidth = 1;
  const horizon = H * 0.22;
  for (let i = 0; i < 7; i++) {
    const yy = horizon + Math.pow(i / 6, 1.6) * (H - horizon);
    ctx.beginPath();
    ctx.moveTo(0, yy);
    ctx.lineTo(W, yy);
    ctx.stroke();
  }
  const vpx = W / 2;
  for (let i = -5; i <= 5; i++) {
    ctx.beginPath();
    ctx.moveTo(vpx + i * W * 0.055, horizon);
    ctx.lineTo(vpx + i * W * 0.28, H);
    ctx.stroke();
  }

  /* drifting scan band */
  const bandY = ((t * 26 + cam.seed * 7) % (H + 80)) - 40;
  const band = ctx.createLinearGradient(0, bandY - 24, 0, bandY + 24);
  band.addColorStop(0, "rgba(34,211,238,0)");
  band.addColorStop(0.5, "rgba(34,211,238,0.05)");
  band.addColorStop(1, "rgba(34,211,238,0)");
  ctx.fillStyle = band;
  ctx.fillRect(0, bandY - 24, W, 48);

  /* tether zone overlay (high-value / vault cams) */
  if (cam.kind === "highvalue" || cam.kind === "vault") {
    ctx.save();
    ctx.setLineDash([5, 4]);
    ctx.strokeStyle = "rgba(34,211,238,0.4)";
    ctx.lineWidth = 1;
    const zx = W * 0.18;
    const zw = W * 0.64;
    const zy = H * 0.42;
    const zh = H * 0.4;
    ctx.strokeRect(zx, zy, zw, zh);
    ctx.setLineDash([]);
    ctx.fillStyle = "rgba(34,211,238,0.75)";
    ctx.font = `600 ${Math.max(8, H * 0.045)}px "JetBrains Mono", monospace`;
    ctx.fillText("VIRTUAL TETHER · ARMED", zx + 6, zy - 5);
    ctx.restore();
  }

  /* people */
  const visible = world.people.filter(
    (p) => p.x >= vp.x0 && p.x <= vp.x0 + vp.w && p.y >= vp.y0 && p.y <= vp.y0 + vp.h,
  );
  const maxDraw = detail ? 14 : 8;
  let labelBudget = detail ? 5 : 2;
  visible.slice(0, maxDraw).forEach((p, i) => {
    const u = (p.x - vp.x0) / vp.w;
    const v = (p.y - vp.y0) / vp.h;
    const sx = u * W;
    const sy = horizon + v * (H - horizon) * 1.04;
    const sc = (0.4 + v * 0.9) * (H / 220);
    const bob = Math.sin(t * 3 + cam.seed + i * 1.7) * sc * 0.8;
    const col = ROLE_COLOR[p.role];

    const fh = 30 * sc; // figure height
    const fw = 11 * sc;
    // silhouette
    ctx.fillStyle = "rgba(10,16,28,0.9)";
    ctx.strokeStyle = col;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect(sx - fw / 2, sy - fh + bob, fw, fh * 0.68, fw * 0.32);
    ctx.fill();
    ctx.globalAlpha = 0.85;
    ctx.stroke();
    ctx.globalAlpha = 1;
    ctx.beginPath();
    ctx.arc(sx, sy - fh + bob - fw * 0.28, fw * 0.34, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalAlpha = 0.85;
    ctx.stroke();
    ctx.globalAlpha = 1;
    // ground shadow
    ctx.fillStyle = "rgba(0,0,0,0.35)";
    ctx.beginPath();
    ctx.ellipse(sx, sy + 2, fw * 0.9, 2.4 * sc, 0, 0, Math.PI * 2);
    ctx.fill();

    /* AI tracking box on subset */
    const interesting = p.flagged || p.role === "blacklist" || p.role === "vip";
    const wantLabel = interesting || labelBudget > 0;
    if (wantLabel) {
      labelBudget--;
      const bw = fw * 2.6;
      const bh = fh * 1.22;
      const bx = sx - bw / 2;
      const by = sy - fh + bob - fw * 0.75;
      const boxCol = p.role === "blacklist" ? "#f87171" : p.role === "vip" ? "#e879f9" : p.flagged ? "#fbbf24" : col;
      cornerBrackets(ctx, bx, by, bw, bh, boxCol);
      if (detail) {
        const tag = p.role === "blacklist" ? "WATCHLIST" : p.role.toUpperCase();
        const conf = (93 + ((cam.seed + i * 13) % 7)).toFixed(1);
        ctx.font = `600 ${Math.max(7, 7.5 * sc * 0.9)}px "JetBrains Mono", monospace`;
        const label = `${p.id} · ${tag} ${conf}%`;
        const tw = ctx.measureText(label).width;
        ctx.fillStyle = "rgba(5,8,16,0.82)";
        ctx.fillRect(bx, by - 11, tw + 8, 11);
        ctx.fillStyle = boxCol;
        ctx.fillText(label, bx + 4, by - 3);
      }
    }
  });

  /* active event flash */
  const recent = [...world.alerts].reverse().find((a) => a.cam === cam.id && world.tick - a.tick < 9);
  if (recent) {
    const blink = Math.sin(t * 9) > -0.2;
    const col = recent.severity === "P1" ? "#f87171" : "#fbbf24";
    if (blink) {
      const ew = W * 0.34;
      const eh = H * 0.4;
      cornerBrackets(ctx, W / 2 - ew / 2, H * 0.42, ew, eh, col, 2);
      ctx.font = `700 ${Math.max(9, H * 0.055)}px "JetBrains Mono", monospace`;
      ctx.fillStyle = col;
      ctx.fillText(`▲ ${recent.type}`, W / 2 - ew / 2, H * 0.42 - 8);
    }
  }

  /* vignette */
  const vg = ctx.createRadialGradient(W / 2, H / 2, H * 0.3, W / 2, H / 2, H * 0.95);
  vg.addColorStop(0, "rgba(0,0,0,0)");
  vg.addColorStop(1, "rgba(0,0,0,0.5)");
  ctx.fillStyle = vg;
  ctx.fillRect(0, 0, W, H);

  /* HUD */
  const fs = Math.max(8, H * 0.05);
  ctx.font = `600 ${fs}px "JetBrains Mono", monospace`;
  ctx.fillStyle = "rgba(219,228,240,0.9)";
  ctx.fillText(cam.id, 10, 8 + fs);
  ctx.fillStyle = "#f87171";
  if (Math.sin(t * 2.4) > -0.4) {
    ctx.beginPath();
    ctx.arc(10 + ctx.measureText(cam.id).width + 12, 5 + fs, fs * 0.3, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.fillStyle = "rgba(132,148,173,0.9)";
  ctx.textAlign = "right";
  ctx.fillText(tickToClock(world.tick, bootTime), W - 10, 8 + fs);
  ctx.textAlign = "left";

  /* AI module chips — top center */
  if (detail) {
    const chips = ["FACE", "TETHER", "SLEIGHT", "LOITER", "PATH"];
    ctx.font = `600 ${fs * 0.62}px "JetBrains Mono", monospace`;
    const widths = chips.map((c) => ctx.measureText(c).width + 12);
    const totalW = widths.reduce((s, x) => s + x, 0) + 6 * (chips.length - 1);
    let cx = W / 2 - totalW / 2;
    const cy = 8 + fs * 1.6;
    chips.forEach((c, i) => {
      const cw = widths[i];
      ctx.strokeStyle = "rgba(34,211,238,0.3)";
      ctx.strokeRect(cx, cy - fs * 0.8, cw, fs * 1.1);
      ctx.fillStyle = "rgba(34,211,238,0.6)";
      ctx.fillText(c, cx + 6, cy + fs * 0.08);
      cx += cw + 6;
    });
  }
}

function FeedCanvas({
  cam,
  worldRef,
  bootTime,
  detail,
  className,
}: {
  cam: CameraInfo;
  worldRef: React.MutableRefObject<WorldState>;
  bootTime: Date;
  detail: boolean;
  className?: string;
}) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current!;
    const ctx = canvas.getContext("2d")!;
    let raf = 0;
    const render = (ms: number) => {
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      const { clientWidth: w, clientHeight: h } = canvas;
      if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
        canvas.width = w * dpr;
        canvas.height = h * dpr;
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      drawFeed(ctx, w, h, cam, worldRef.current, ms, detail, bootTime);
      raf = requestAnimationFrame(render);
    };
    raf = requestAnimationFrame(render);
    return () => cancelAnimationFrame(raf);
  }, [cam, worldRef, detail, bootTime]);

  return <canvas ref={ref} className={className} style={{ width: "100%", height: "100%", display: "block" }} />;
}

export default function CameraWall({ world }: { world: WorldState }) {
  const worldRef = useRef(world);
  worldRef.current = world;
  const bootTime = useRef(new Date()).current;
  const cams = world.template.cameras;
  const featured = cams.find((c) => c.kind === "highvalue")!;
  const small = cams.filter((c) => c.id !== featured.id);

  return (
    <div className="panel relative overflow-hidden scanlines flex flex-col h-full">
      <div className="panel-title">
        <span className="led anim-pulse-dot" style={{ color: "#f87171", background: "#f87171" }} />
        Live camera wall
        <span className="ml-auto flex items-center gap-3 normal-case tracking-normal">
          <span className="text-[9px]" style={{ color: "#4a5a76" }}>
            AI overlays: tracking · classification · tether zones
          </span>
        </span>
      </div>

      <div className="p-2 flex flex-col gap-2 flex-1 min-h-0">
        {/* featured feed */}
        <div className="relative rounded overflow-hidden border flex-[2] min-h-[190px]" style={{ borderColor: "#22304f" }}>
          <FeedCanvas cam={featured} worldRef={worldRef} bootTime={bootTime} detail />
          <div className="absolute left-2 bottom-2 glass rounded px-2 py-1 z-10">
            <div className="text-[9px] font-bold tracking-[0.16em]" style={{ color: "#22d3ee" }}>
              {featured.id} · {featured.name}
            </div>
            <div className="text-[8px]" style={{ color: "#8494ad" }}>
              {featured.zone} — {world.template.featuredCamNote}
            </div>
          </div>
        </div>
        {/* secondary feeds */}
        <div className="grid grid-cols-3 gap-2 flex-1 min-h-[86px]">
          {small.map((c) => (
            <div key={c.id} className="relative rounded overflow-hidden border" style={{ borderColor: "#1a2540" }}>
              <FeedCanvas cam={c} worldRef={worldRef} bootTime={bootTime} detail={false} />
              <div className="absolute left-1 bottom-1 z-10 text-[8px] font-bold tracking-wider px-1 rounded" style={{ background: "rgba(5,8,16,0.75)", color: "#8494ad" }}>
                {c.id}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
