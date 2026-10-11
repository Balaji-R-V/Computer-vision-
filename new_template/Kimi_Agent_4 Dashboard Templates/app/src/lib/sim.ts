import type {
  Alert,
  AlertType,
  BlacklistHit,
  Booth,
  ClassMethod,
  Person,
  Role,
  Severity,
  ShowMode,
  Template,
  VipGuest,
  WorldState,
} from "@/types";

/* ------------------------------------------------------------------ */
/* Hall geometry — 1000 x 640 coordinate space                        */
/* ------------------------------------------------------------------ */

export const FLOOR_W = 1000;
export const FLOOR_H = 640;

export const ENTRANCE = { x: 500, y: 610 };
export const VAULT = { x: 24, y: 24, w: 150, h: 96 };
export const BACKROOM = { x: 826, y: 24, w: 150, h: 96 };

const BOOTH_W = 168;
const BOOTH_H = 104;
const BOOTH_X0 = 116;
const BOOTH_GAP_X = 60;
const ROW_Y = [168, 396];

function makeBooths(tpl: Template): Booth[] {
  return tpl.zones.map((z, i) => ({
    id: z.id,
    name: z.name,
    tier: z.tier,
    x: BOOTH_X0 + (i % 4) * (BOOTH_W + BOOTH_GAP_X),
    y: ROW_Y[Math.floor(i / 4)],
    w: BOOTH_W,
    h: BOOTH_H,
    traffic: 40 + Math.floor(rand() * 160),
    dwellSum: 1200 + Math.floor(rand() * 5200),
    staffCount: 2,
    density: 0,
    lastVisit: {},
  }));
}

/* ------------------------------------------------------------------ */
/* RNG (mulberry32)                                                    */
/* ------------------------------------------------------------------ */

let _s = 0x9e3779b9;
function rand() {
  _s |= 0;
  _s = (_s + 0x6d2b79f5) | 0;
  let t = Math.imul(_s ^ (_s >>> 15), 1 | _s);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
}
const pick = <T,>(arr: T[]): T => arr[Math.floor(rand() * arr.length)];

/* ------------------------------------------------------------------ */
/* People                                                              */
/* ------------------------------------------------------------------ */

const STAFF_NAMES = ["R. Okafor", "M. Lin", "S. Petrov", "A. Dubois", "K. Tanaka", "L. Moreau", "J. Weiss", "P. Naik", "E. Costa", "H. Brandt", "T. Sato", "V. Rossi"];

let personSeq = 100;
function makePerson(role: Role, x: number, y: number, opts?: Partial<Person>): Person {
  const classifiedBy: ClassMethod =
    role === "staff"
      ? pick(["FACE WHITELIST", "UNIFORM COLOR", "LANYARD / BADGE"] as ClassMethod[])
      : role === "contractor"
        ? "BEHAVIORAL PATH"
        : role === "vip" || role === "blacklist"
          ? "FACE WHITELIST"
          : pick(["UNIFORM COLOR", "BEHAVIORAL PATH"] as ClassMethod[]);
  return {
    id: `T-${personSeq++}`,
    role,
    x,
    y,
    tx: x,
    ty: y,
    speed: role === "staff" ? 1.5 + rand() : 0.7 + rand() * 0.9,
    dwell: 0,
    nearBooth: null,
    classifiedBy,
    path: [],
    flagged: false,
    ...opts,
  };
}

function spawnPopulation(tpl: Template): Person[] {
  const people: Person[] = [];
  tpl.zones.forEach((_, i) => {
    const bx = BOOTH_X0 + (i % 4) * (BOOTH_W + BOOTH_GAP_X);
    const by = ROW_Y[Math.floor(i / 4)];
    for (let k = 0; k < 2; k++) {
      people.push(
        makePerson("staff", bx + 20 + rand() * (BOOTH_W - 40), by + BOOTH_H / 2 + (rand() - 0.5) * 30, {
          name: STAFF_NAMES[people.length % STAFF_NAMES.length],
        }),
      );
    }
  });
  // guards
  people.push(makePerson("staff", VAULT.x + VAULT.w + 30, VAULT.y + 40, { name: "Guard · R-2" }));
  people.push(makePerson("staff", ENTRANCE.x - 60, ENTRANCE.y - 40, { name: "Guard · Gate" }));
  // attendees wandering
  for (let i = 0; i < 34; i++) {
    people.push(makePerson("attendee", 120 + rand() * 760, 150 + rand() * 380));
  }
  return people;
}

function wanderTarget(p: Person, mode: ShowMode): { x: number; y: number } {
  if (mode === "after") {
    // only staff/contractors remain: purposeful vault <-> counter <-> exit paths
    if (p.role === "staff" || p.role === "contractor") {
      return pick([
        { x: VAULT.x + VAULT.w + 24, y: VAULT.y + 30 + rand() * 50 },
        { x: 300 + rand() * 400, y: 200 + rand() * 240 },
        { x: ENTRANCE.x + (rand() - 0.5) * 120, y: ENTRANCE.y - 50 },
      ]);
    }
    return { x: ENTRANCE.x, y: ENTRANCE.y };
  }
  if (p.role === "staff") {
    if (p.nearBooth) {
      const b = boothsRef.find((bb) => bb.id === p.nearBooth);
      if (b && rand() < 0.8) {
        return { x: b.x + 20 + rand() * (b.w - 40), y: b.y + b.h / 2 + (rand() - 0.5) * 34 };
      }
    }
    return pick([
      { x: 200 + rand() * 600, y: 320 + (rand() - 0.5) * 60 }, // central aisle
      { x: BACKROOM.x - 30, y: BACKROOM.y + 40 + rand() * 40 },
    ]);
  }
  // attendees / vip / blacklist: browse zones, linger at high-value ones
  if (rand() < 0.62) {
    const b = pick(boothsRef);
    const front = b.y + b.h + 16 + rand() * 26;
    return { x: b.x + 14 + rand() * (b.w - 28), y: Math.min(front, FLOOR_H - 30) };
  }
  return { x: 100 + rand() * 800, y: 150 + rand() * 400 };
}

/* ------------------------------------------------------------------ */
/* Alerts                                                              */
/* ------------------------------------------------------------------ */

let alertSeq = 1;
function makeAlert(
  tick: number,
  severity: Severity,
  type: AlertType,
  title: string,
  detail: string,
  location: string,
  cam: string,
): Alert {
  return {
    id: `AL-${String(alertSeq++).padStart(4, "0")}`,
    tick,
    severity,
    type,
    title,
    detail,
    location,
    cam,
    devices: severity === "P3" ? ["phone"] : ["watch", "phone"],
    clipSec: 4 + Math.floor(rand() * 8),
    status: "new",
    silent: true,
  };
}

/* ------------------------------------------------------------------ */
/* Engine                                                              */
/* ------------------------------------------------------------------ */

let boothsRef: Booth[] = [];
let accessSeq = 1;
let lastLoiterTick = -999;

const zoneLabel = (b: Booth) => `${b.id} · ${b.name}`;

function seedAlerts(tpl: Template): Alert[] {
  return tpl.copy.seeds.map((sd, i) => {
    const a = makeAlert(-214 + i * 84, sd.sev, sd.type, sd.title, sd.detail, sd.loc, sd.cam);
    a.status = "acked";
    return a;
  });
}

function seedAccess(tpl: Template) {
  const ev: import("@/types").AccessEvent[] = [];
  for (let i = 0; i < 6; i++) {
    ev.push({
      id: `AC-${String(accessSeq++).padStart(3, "0")}`,
      tick: -300 + i * 47,
      zone: pick(tpl.accessZones),
      person: pick(STAFF_NAMES),
      method: pick(["FACE WHITELIST", "BADGE + FACE"] as const),
      result: "GRANTED",
    });
  }
  return ev;
}

function seedVips(tpl: Template, people: Person[]): VipGuest[] {
  const [name, tier, spendBand, interest] = tpl.vip.names[3 % tpl.vip.names.length];
  people.push(makePerson("vip", 480, 350, { name }));
  return [
    {
      id: "V-1",
      name,
      tier,
      spendBand,
      interest,
      director: tpl.vip.greeters[1 % tpl.vip.greeters.length],
      tick: -160,
      greeted: true,
    },
  ];
}

export function createWorld(tpl: Template): WorldState {
  boothsRef = makeBooths(tpl);
  const people = spawnPopulation(tpl);
  const state: WorldState = {
    tick: 0,
    mode: "show",
    template: tpl,
    people,
    booths: boothsRef,
    alerts: seedAlerts(tpl),
    access: seedAccess(tpl),
    vips: seedVips(tpl, people),
    blacklist: [],
    threatScore: 8,
    counts: { staff: 0, attendees: 0, vip: 0, unknown: 0 },
    classMix: {
      "UNIFORM COLOR": 0,
      "LANYARD / BADGE": 0,
      "FACE WHITELIST": 0,
      "BEHAVIORAL PATH": 0,
    },
    staffingGap: null,
  };
  recompute(state);
  return state;
}

function recompute(s: WorldState) {
  let staff = 0,
    attendees = 0,
    vip = 0,
    unknown = 0;
  const mix: Record<ClassMethod, number> = {
    "UNIFORM COLOR": 0,
    "LANYARD / BADGE": 0,
    "FACE WHITELIST": 0,
    "BEHAVIORAL PATH": 0,
  };
  for (const p of s.people) {
    if (p.role === "staff" || p.role === "contractor") staff++;
    else if (p.role === "vip") vip++;
    else if (p.role === "blacklist") unknown++;
    else attendees++;
    mix[p.classifiedBy]++;
  }
  s.counts = { staff, attendees, vip, unknown };
  s.classMix = mix;

  // zone densities (attendees only — staff are filtered from analytics)
  for (const b of s.booths) b.density = 0;
  for (const p of s.people) {
    if (p.role === "staff" || p.role === "contractor") continue;
    for (const b of s.booths) {
      if (p.x > b.x - 24 && p.x < b.x + b.w + 24 && p.y > b.y - 8 && p.y < b.y + b.h + 48) {
        b.density++;
      }
    }
  }
  // coverage gap: busiest zone with weakest coverage
  let gap: WorldState["staffingGap"] = null;
  for (const b of s.booths) {
    const ratio = b.density / Math.max(1, b.staffCount);
    if (!gap || ratio > gap.ratio) gap = { booth: `${b.id} · ${b.name}`, ratio };
  }
  s.staffingGap = gap;

  // threat score from open alerts
  const open = s.alerts.filter((a) => a.status !== "acked");
  const score =
    open.filter((a) => a.severity === "P1").length * 22 +
    open.filter((a) => a.severity === "P2").length * 9 +
    s.blacklist.filter((b) => b.status === "TRACKING").length * 12 +
    6;
  s.threatScore = Math.max(4, Math.min(96, score));
}

/* --------------------------------- main tick --------------------------------- */

export function tickWorld(prev: WorldState): WorldState {
  const tpl = prev.template;
  const C = tpl.copy;
  const s: WorldState = {
    ...prev,
    tick: prev.tick + 1,
    people: prev.people.map((p) => ({ ...p, path: p.path.slice(-24) })),
    booths: prev.booths.map((b) => ({ ...b, lastVisit: { ...b.lastVisit } })),
    alerts: prev.alerts.map((a) => ({ ...a })),
    access: [...prev.access],
    vips: prev.vips.map((v) => ({ ...v })),
    blacklist: prev.blacklist.map((b) => ({ ...b })),
  };
  boothsRef = s.booths;
  const t = s.tick;

  /* --- movement --- */
  for (const p of s.people) {
    const dx = p.tx - p.x;
    const dy = p.ty - p.y;
    const d = Math.hypot(dx, dy);
    if (d < 4) {
      const nt = wanderTarget(p, s.mode);
      p.tx = nt.x;
      p.ty = nt.y;
    } else {
      const v = p.speed * (s.mode === "after" && (p.role === "staff" || p.role === "contractor") ? 1.6 : 1);
      p.x += (dx / d) * v;
      p.y += (dy / d) * v;
    }
    p.path.push({ x: p.x, y: p.y });

    // dwell near zones
    let near: Booth | null = null;
    for (const b of s.booths) {
      if (p.x > b.x - 20 && p.x < b.x + b.w + 20 && p.y > b.y - 6 && p.y < b.y + b.h + 46) {
        near = b;
      }
    }
    if (near && (p.role === "attendee" || p.role === "blacklist" || p.role === "vip")) {
      p.dwell++;
      if (near.lastVisit[p.id] === undefined || t - near.lastVisit[p.id] > 40) {
        near.traffic++;
        near.lastVisit[p.id] = t;
      }
      near.dwellSum++;
    } else {
      p.dwell = Math.max(0, p.dwell - 2);
      if (p.dwell === 0 && p.flagged && p.role !== "blacklist") p.flagged = false;
    }
    p.nearBooth = near ? near.id : null;
  }

  /* --- alert lifecycle --- */
  for (const a of s.alerts) {
    if (a.status === "new" && t - a.tick > 2) a.status = "dispatched";
  }
  if (s.alerts.length > 42) s.alerts = s.alerts.slice(-42);

  const push = (sev: Severity, type: AlertType, et: { title: string; detail: string }, loc: string, cam: string) =>
    s.alerts.push(makeAlert(t, sev, type, et.title, et.detail, loc, cam));

  if (s.mode === "show") {
    /* casing / loiter (rate-limited) */
    if (t - lastLoiterTick > 14) {
      for (const p of s.people) {
        if ((p.role === "attendee" || p.role === "blacklist") && !p.flagged && p.dwell > 30 && p.nearBooth) {
          const b = s.booths.find((bb) => bb.id === p.nearBooth)!;
          if (b.tier === "high") {
            p.flagged = true;
            lastLoiterTick = t;
            push("P2", "CASING / LOITER", C.loiter(zoneLabel(b), p.id, p.dwell), zoneLabel(b), "CAM-03");
            break;
          }
        }
      }
    }

    /* sleight of hand — rare, critical */
    if (rand() < 0.012) {
      const b = pick(s.booths.filter((bb) => bb.tier === "high"));
      push("P1", "SLEIGHT OF HAND", C.sleight(zoneLabel(b), (88 + rand() * 10).toFixed(1)), zoneLabel(b), "CAM-03");
    }

    /* reach-in */
    if (rand() < 0.018) {
      const b = pick(s.booths);
      push("P1", "REACH-IN", C.reachin(zoneLabel(b), (0.7 + rand() * 0.9).toFixed(1)), zoneLabel(b), "CAM-02");
    }

    /* asset tether breach */
    if (rand() < 0.009) {
      const b = pick(s.booths.filter((bb) => bb.tier === "high"));
      push("P1", "TETHER BREACH", C.tether(zoneLabel(b), `${b.id}-${Math.floor(100 + rand() * 800)}`), zoneLabel(b), "CAM-03");
    }

    /* blacklist arrival */
    if (rand() < 0.011 && s.blacklist.filter((b) => b.status === "TRACKING").length < 2) {
      const [alias, knownFor] = pick(tpl.blacklist.aliases);
      const conf = 91 + rand() * 8;
      const hit: BlacklistHit = {
        id: `BL-${String(s.blacklist.length + 1).padStart(2, "0")}`,
        alias,
        confidence: conf,
        cam: "CAM-01",
        tick: t,
        status: "TRACKING",
        knownFor,
      };
      s.blacklist.push(hit);
      const person = makePerson("blacklist", ENTRANCE.x + (rand() - 0.5) * 80, ENTRANCE.y - 10);
      s.people.push(person);
      push("P1", "BLACKLIST MATCH", C.blacklist(alias, conf.toFixed(1), knownFor), "Main Entrance", "CAM-01");
    }
    for (const b of s.blacklist) {
      if (b.status === "TRACKING" && t - b.tick > 55 && rand() < 0.05) b.status = "CONTAINED";
    }

    /* VIP arrival */
    if (rand() < 0.016) {
      const [name, tier, spendBand, interest] = pick(tpl.vip.names);
      if (!s.vips.some((v) => v.name === name)) {
        const greeter = pick(tpl.vip.greeters);
        const v: VipGuest = {
          id: `V-${s.vips.length + 1}`,
          name,
          tier,
          spendBand,
          interest,
          director: greeter,
          tick: t,
          greeted: false,
        };
        s.vips.unshift(v);
        const person = makePerson("vip", ENTRANCE.x + (rand() - 0.5) * 60, ENTRANCE.y - 8, { name });
        s.people.push(person);
        push("P3", "VIP ARRIVAL", C.vipArrival(name, tier, interest, greeter, `99.${Math.floor(rand() * 9)}`), "Main Entrance", "CAM-01");
      }
    }

    /* coverage pressure */
    if (s.staffingGap && s.staffingGap.ratio > 4.5 && rand() < 0.02) {
      push("P3", "STAFFING", C.staffing(s.staffingGap.booth, s.staffingGap.ratio.toFixed(1)), s.staffingGap.booth, "CAM-02");
    }
  } else {
    /* after-hours: perimeter + internal shrinkage watch */
    if (rand() < 0.02) {
      push("P1", "PERIMETER", C.perimeter, `${tpl.rooms.vault} Corridor`, "CAM-04");
    }
  }

  /* restricted-zone access events (both modes) */
  if (rand() < (s.mode === "after" ? 0.05 : 0.02)) {
    const denied = rand() < 0.16;
    const person = denied ? "UNVERIFIED — credential match only" : pick(STAFF_NAMES);
    const zone = pick(tpl.accessZones);
    s.access.unshift({
      id: `AC-${String(accessSeq++).padStart(3, "0")}`,
      tick: t,
      zone,
      person,
      method: denied ? "BADGE + FACE" : pick(["FACE WHITELIST", "BADGE + FACE", "CONTRACTOR PASS"] as const),
      result: denied ? "DENIED" : "GRANTED",
      note: denied ? "Face not on whitelist — imposter rule fired" : undefined,
    });
    if (s.access.length > 9) s.access = s.access.slice(0, 9);
    if (denied) {
      push("P2", "IMPOSTER", C.imposter(zone), zone, "CAM-04");
    } else if (s.mode === "after") {
      push("P2", "VAULT ACCESS", C.vaultAccess(zone, person), zone, "CAM-04");
    }
  }

  /* population maintenance */
  if (s.mode === "show" && s.people.filter((p) => p.role === "attendee").length < 30 && rand() < 0.2) {
    s.people.push(makePerson("attendee", ENTRANCE.x + (rand() - 0.5) * 100, ENTRANCE.y - 6));
  }
  if (s.people.length > 72) {
    const idx = s.people.findIndex((p) => p.role === "attendee" && !p.flagged);
    if (idx >= 0) s.people.splice(idx, 1);
  }

  recompute(s);
  return s;
}

export function toggleMode(prev: WorldState, mode: ShowMode): WorldState {
  const tpl = prev.template;
  const s: WorldState = { ...prev, mode, people: [...prev.people], alerts: [...prev.alerts] };
  if (mode === "after") {
    s.people = s.people.filter((p) => p.role === "staff" || p.role === "contractor");
    s.people.push(makePerson("contractor", 400, 300, { name: "Contractor · AV crew" }));
    s.people.push(makePerson("contractor", 600, 420, { name: "Contractor · Cleaning" }));
    s.alerts.push(makeAlert(s.tick, "P2", "PERIMETER", tpl.copy.arm.title, tpl.copy.arm.detail, "All zones", "ALL"));
  } else {
    s.alerts.push(makeAlert(s.tick, "P3", "PERIMETER", tpl.copy.disarm.title, tpl.copy.disarm.detail, "All zones", "ALL"));
  }
  recompute(s);
  return s;
}
