export type Role = "staff" | "attendee" | "vip" | "blacklist" | "contractor";
export type Severity = "P1" | "P2" | "P3";
export type ShowMode = "show" | "after";
export type ClassMethod =
  | "UNIFORM COLOR"
  | "LANYARD / BADGE"
  | "FACE WHITELIST"
  | "BEHAVIORAL PATH";

export interface Person {
  id: string;
  role: Role;
  name?: string;
  x: number;
  y: number;
  tx: number;
  ty: number;
  speed: number;
  dwell: number; // seconds spent near current high-value booth
  nearBooth: string | null;
  classifiedBy: ClassMethod;
  path: { x: number; y: number }[];
  flagged: boolean;
}

export interface Booth {
  id: string;
  name: string;
  tier: "high" | "standard";
  x: number;
  y: number;
  w: number;
  h: number;
  traffic: number; // unique attendee visits
  dwellSum: number; // attendee seconds
  staffCount: number;
  density: number; // current people nearby
  lastVisit: Record<string, number>; // personId -> tick of last counted visit
}

export type AlertType =
  | "TETHER BREACH"
  | "SLEIGHT OF HAND"
  | "REACH-IN"
  | "CASING / LOITER"
  | "BLACKLIST MATCH"
  | "IMPOSTER"
  | "VAULT ACCESS"
  | "PERIMETER"
  | "VIP ARRIVAL"
  | "STAFFING";

export interface Alert {
  id: string;
  tick: number;
  severity: Severity;
  type: AlertType;
  title: string;
  detail: string;
  location: string;
  cam: string;
  devices: ("watch" | "phone")[];
  clipSec: number;
  status: "new" | "dispatched" | "acked";
  silent: boolean;
}

export interface AccessEvent {
  id: string;
  tick: number;
  zone: string;
  person: string;
  method: "FACE WHITELIST" | "BADGE + FACE" | "CONTRACTOR PASS";
  result: "GRANTED" | "DENIED";
  note?: string;
}

export interface VipGuest {
  id: string;
  name: string;
  tier: "PLATINUM" | "GOLD";
  spendBand: string;
  interest: string;
  director: string;
  tick: number;
  greeted: boolean;
}

export interface BlacklistHit {
  id: string;
  alias: string;
  confidence: number;
  cam: string;
  tick: number;
  status: "TRACKING" | "CONTAINED" | "EXITED";
  knownFor: string;
}

export interface CameraInfo {
  id: string;
  name: string;
  zone: string;
  online: boolean;
  kind: "entrance" | "aisle" | "highvalue" | "vault";
  seed: number;
}

export interface WorldState {
  tick: number;
  mode: ShowMode;
  template: Template;
  people: Person[];
  booths: Booth[];
  alerts: Alert[];
  access: AccessEvent[];
  vips: VipGuest[];
  blacklist: BlacklistHit[];
  threatScore: number; // 0-100
  counts: { staff: number; attendees: number; vip: number; unknown: number };
  classMix: Record<ClassMethod, number>;
  staffingGap: { booth: string; ratio: number } | null;
}

/* ------------------------------------------------------------------ */
/* Deployment template (expo / retail / restaurant / office)           */
/* ------------------------------------------------------------------ */

export type TemplateId = "expo" | "retail" | "restaurant" | "office";

export interface EventText {
  title: string;
  detail: string;
}

export interface Template {
  id: TemplateId;
  tab: string;
  venue: string;
  venueSub: string;
  floorName: string;
  entranceLabel: string;
  rooms: { vault: string; backroom: string };
  accessZones: string[];
  zones: { id: string; name: string; tier: "high" | "standard" }[];
  cameras: CameraInfo[];
  visitorNoun: string; // "shoppers on floor"
  visitorsLabel: string; // "SHOPPERS"
  featuredCamNote: string;
  vip: {
    title: string;
    subtitle: string;
    emptyText: string;
    names: Array<[string, "PLATINUM" | "GOLD", string, string]>;
    greeters: string[];
  };
  blacklist: {
    title: string;
    emptyText: string;
    aliases: Array<[string, string]>;
  };
  access: { logTitle: string; note: string };
  analytics: {
    panelTitle: string;
    visitLabel: string;
    staffingTitle: string;
    staffing: (zone: string, ratio: string) => string;
    balanced: string;
    footer: string;
  };
  classification: { whyTitle: string; whyText: string };
  modes: { show: string; after: string; showBadge: string; afterBadge: string };
  copy: {
    tether: (zone: string, tag: string) => EventText;
    sleight: (zone: string, conf: string) => EventText;
    reachin: (zone: string, secs: string) => EventText;
    loiter: (zone: string, personId: string, dwell: number) => EventText;
    blacklist: (alias: string, conf: string, knownFor: string) => EventText;
    imposter: (zone: string) => EventText;
    vaultAccess: (zone: string, person: string) => EventText;
    perimeter: EventText;
    vipArrival: (name: string, tier: string, interest: string, greeter: string, conf: string) => EventText;
    staffing: (zone: string, ratio: string) => EventText;
    arm: EventText;
    disarm: EventText;
    seeds: Array<{ sev: Severity; type: AlertType; title: string; detail: string; loc: string; cam: string }>;
  };
}
