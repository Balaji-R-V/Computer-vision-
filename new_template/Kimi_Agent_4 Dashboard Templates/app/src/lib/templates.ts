import type { CameraInfo, Template, TemplateId } from "@/types";

function cam(id: string, name: string, zone: string, kind: CameraInfo["kind"], seed: number): CameraInfo {
  return { id, name, zone, kind, seed, online: true };
}

/* ============================ EXPO ============================ */

const expo: Template = {
  id: "expo",
  tab: "EXPO",
  venue: "Gem & Jewellery International Expo",
  venueSub: "Hall B · Day 2 of 4 · 12 zones · 8 exhibitor rows",
  floorName: "Hall B · situational map",
  entranceLabel: "MAIN ENTRANCE · FACE CAPTURE",
  rooms: { vault: "VAULT A", backroom: "BACKROOM" },
  accessZones: ["Vault A", "Backroom", "Safe Room 2"],
  zones: [
    { id: "A1", name: "Aurelia Diamonds", tier: "standard" },
    { id: "B1", name: "Maison Kagami — Vitrine", tier: "high" },
    { id: "C1", name: "Or & Argent", tier: "standard" },
    { id: "D1", name: "Celeste Gem Co.", tier: "standard" },
    { id: "A2", name: "House of Veda", tier: "standard" },
    { id: "B2", name: "Novogold Atelier", tier: "standard" },
    { id: "C2", name: "Rexford & Vale — Vitrine", tier: "high" },
    { id: "D2", name: "Lumière Pearls", tier: "standard" },
  ],
  cameras: [
    cam("CAM-01", "ENTRANCE GATE", "Main Entrance", "entrance", 11),
    cam("CAM-02", "AISLE NORTH", "Aisle N / Row 1", "aisle", 47),
    cam("CAM-03", "HIGH-VALUE ROW", "Vitrines B1 · C2", "highvalue", 83),
    cam("CAM-04", "VAULT CORRIDOR", "Vault A / Backroom", "vault", 129),
  ],
  visitorNoun: "attendees on floor",
  visitorsLabel: "ATTENDEES",
  featuredCamNote: "vitrine tether grid active",
  vip: {
    title: "VIP arrival alerts",
    subtitle: "face-recognized at gate",
    emptyText:
      "No VIPs on floor yet — the same recognition stack that flags offenders also spots your best buyers the moment they walk in.",
    names: [
      ["Adelina Rothschild-Vey", "PLATINUM", "$2M–$5M", "high-jewellery suites"],
      ["Marcus Tham", "PLATINUM", "$1M–$2M", "coloured diamonds"],
      ["Princess Noor A.", "PLATINUM", "$5M+", "estate pieces"],
      ["Dmitri Volkov", "GOLD", "$500K–$1M", "investment-grade stones"],
      ["Chen Wei-Lin", "GOLD", "$500K–$1M", "signed vintage"],
      ["Sofia Al-Rashid", "PLATINUM", "$2M–$5M", "bespoke commissions"],
      ["Jonathan Pryce", "GOLD", "$250K–$500K", "rare pearls"],
    ],
    greeters: ["E. Fontaine", "K. Ashford", "M. Delacroix", "R. Sterling"],
  },
  blacklist: {
    title: "Inter-show watchlist · face matching",
    emptyText:
      "No matches this session — entrance feed cross-referencing every face against the travelling-offender database.",
    aliases: [
      ["“The Vienna Gentleman”", "Sleight-of-hand swap, Basel '24"],
      ["“Pink Panther Cell 7”", "Smash-and-grab ring, EU-wide warrant"],
      ["“Dubai Switch Crew”", "Counterfeit substitution, 3 shows"],
      ["“Antwerp Ghost”", "Vault infiltration, insider tactics"],
    ],
  },
  access: {
    logTitle: "Vault / backroom · biometric access log",
    note: "Doors release only on face-whitelist match — a stolen uniform or badge alone never opens the vault. Every entry is logged for the shrinkage audit.",
  },
  analytics: {
    panelTitle: "Organizer analytics · booth valuation",
    visitLabel: "ATTENDEE VISITS",
    staffingTitle: "STAFF ALLOCATION · LIVE RECOMMENDATION",
    staffing: (zone, ratio) =>
      `${zone} is running ${ratio} visitors per associate — high-value clients may be waiting. Shift one associate from the quietest row for the next hour.`,
    balanced: "Coverage is balanced across all booths. No redeployment needed right now.",
    footer:
      "ROI grade prices next year's floor plan: A+ booths justify premium rates backed by verified footfall + dwell data.",
  },
  classification: {
    whyTitle: "WHY IT MATTERS",
    whyText:
      "Staff are stripped from traffic, dwell and heatmap metrics — otherwise three associates behind one counter all day would make that booth look artificially popular and corrupt exhibitor ROI data.",
  },
  modes: {
    show: "● SHOW HOURS",
    after: "◐ AFTER HOURS",
    showBadge: "● SHOW MODE — BASELINE LEARNING ACTIVE",
    afterBadge: "◐ PERIMETER ARMED — ALL MOTION ANOMALOUS",
  },
  copy: {
    tether: (zone, tag) => ({
      title: "Item moved outside digital boundary",
      detail: `Inventory tag ${tag} left its tethered zone at ${zone}. Anchor loss confirmed by 2 cameras.`,
    }),
    sleight: (zone, conf) => ({
      title: "Swap motion detected at vitrine",
      detail: `Hand-occlusion + object-swap signature (${conf}% match) at ${zone}. Tray contents under verification — case auto-locked.`,
    }),
    reachin: (zone, secs) => ({
      title: "Unauthorized hand across staff line",
      detail: `Non-whitelisted hand crossed into the staff-controlled zone of case ${zone} for ${secs}s. Nearest guard vectoring.`,
    }),
    loiter: (zone, personId, dwell) => ({
      title: `Prolonged hover at ${zone.split(" ")[0]} vitrine`,
      detail: `${personId} has lingered ${dwell}s at a high-value case without staff contact. Baseline dwell for this aisle is 11s. 3rd pass by this case in 20 min.`,
    }),
    blacklist: (alias, conf, knownFor) => ({
      title: `Known offender at entrance — ${conf}%`,
      detail: `${alias} matched the inter-show watchlist (${knownFor}). Silent alert to floor team — do not approach; track and block exits on signal.`,
    }),
    imposter: (zone) => ({
      title: "Uniform without whitelist face",
      detail: `Person in staff colours attempted ${zone} access but failed continuous face verification. Door stayed locked; guard dispatched.`,
    }),
    vaultAccess: (zone, person) => ({
      title: `${zone} opened after hours`,
      detail: `${person} entered ${zone} on biometric release. Session is being recorded for shrinkage audit.`,
    }),
    perimeter: {
      title: "After-hours motion near vault approach",
      detail:
        "Movement vector detected in the vault corridor outside authorized rounds. Contractor whitelist cross-check running.",
    },
    vipArrival: (name, tier, interest, greeter, conf) => ({
      title: `${tier} client recognized — ${name}`,
      detail: `Face-matched at the gate (${conf}%). Known interest: ${interest}. ${greeter} notified to greet by name.`,
    }),
    staffing: (zone, ratio) => ({
      title: "Clients waiting without coverage",
      detail: `${zone} is at ${ratio} visitors per staffer. Recommend redeploying 1 associate from the quietest adjacent booth.`,
    }),
    arm: {
      title: "Digital perimeter armed",
      detail:
        "Show floor closed. Virtual fence active around all vitrines, safes and the vault corridor. All motion is now anomalous by default.",
    },
    disarm: {
      title: "Perimeter disarmed — show open",
      detail: "Doors open. Behavioural baselines re-learning for the first 15 minutes.",
    },
    seeds: [
      {
        sev: "P3",
        type: "STAFFING",
        title: "Clients waiting without coverage",
        detail: "B1 · Maison Kagami — Vitrine ran 5.2 visitors per associate for 12 minutes. One associate redeployed from D-row.",
        loc: "B1 · Maison Kagami — Vitrine",
        cam: "CAM-02",
      },
      {
        sev: "P2",
        type: "CASING / LOITER",
        title: "Prolonged hover at C2 vitrine",
        detail: "T-087 lingered 41s at a high-value case without staff contact. Subject moved on after guard walk-by; kept on soft track.",
        loc: "C2 · Rexford & Vale — Vitrine",
        cam: "CAM-03",
      },
      {
        sev: "P1",
        type: "REACH-IN",
        title: "Unauthorized hand across staff line",
        detail: "Non-whitelisted hand crossed into the staff-controlled zone of case B1 for 1.1s. Guard intercepted — accidental lean-in, case verified intact.",
        loc: "B1 · Maison Kagami — Vitrine",
        cam: "CAM-03",
      },
    ],
  },
};

/* ============================ RETAIL ============================ */

const retail: Template = {
  id: "retail",
  tab: "RETAIL",
  venue: "Meridian Flagship — Department Store",
  venueSub: "Ground floor · 8 departments · 12 zones · 4 entrances",
  floorName: "Ground floor · department map",
  entranceLabel: "MAIN ENTRANCE · EAS GATES 1–2",
  rooms: { vault: "STOCKROOM", backroom: "CASH OFFICE" },
  accessZones: ["Stockroom", "Cash Office", "Receiving Dock"],
  zones: [
    { id: "A1", name: "Cosmetics", tier: "standard" },
    { id: "B1", name: "Fine Watches", tier: "high" },
    { id: "C1", name: "Women's Apparel", tier: "standard" },
    { id: "D1", name: "Footwear", tier: "standard" },
    { id: "A2", name: "Men's Apparel", tier: "standard" },
    { id: "B2", name: "Home & Living", tier: "standard" },
    { id: "C2", name: "Electronics", tier: "high" },
    { id: "D2", name: "Accessories", tier: "standard" },
  ],
  cameras: [
    cam("CAM-01", "MAIN ENTRANCE", "Doors 1–2 · EAS pedestals", "entrance", 11),
    cam("CAM-02", "GROUND FLOOR N", "North aisle / Apparel", "aisle", 47),
    cam("CAM-03", "HIGH-VALUE WALL", "Fine Watches · Electronics", "highvalue", 83),
    cam("CAM-04", "STOCKROOM CORRIDOR", "Stockroom · Cash Office", "vault", 129),
  ],
  visitorNoun: "shoppers on floor",
  visitorsLabel: "SHOPPERS",
  featuredCamNote: "RFID tether grid + EAS sync active",
  vip: {
    title: "Loyalty & VIP arrivals",
    subtitle: "recognized at the doors",
    emptyText:
      "No loyalty-tier shoppers recognized yet — entrance cameras match every face against the top-spender register.",
    names: [
      ["Helena Marchetti", "PLATINUM", "$80K/yr", "fine watches"],
      ["Robert Ashwell", "GOLD", "$35K/yr", "designer menswear"],
      ["Yuki Tanabe", "PLATINUM", "$120K/yr", "limited electronics"],
      ["Fatima El-Amin", "GOLD", "$28K/yr", "haute cosmetics"],
      ["George Papadopoulos", "PLATINUM", "$95K/yr", "home collections"],
      ["Isabelle Fournier", "GOLD", "$40K/yr", "luxury accessories"],
    ],
    greeters: ["S. Laurent", "D. Mercer", "A. Castillo", "J. Whitfield"],
  },
  blacklist: {
    title: "ORC watchlist · face matching",
    emptyText:
      "No matches this session — entrance feed cross-referencing every face against the organized-retail-crime register shared by 40 stores.",
    aliases: [
      ["“The Booster Bag Crew”", "ORC shelf sweeps, 6 stores hit"],
      ["“Milano Grab Team”", "Grab-and-run, watches & electronics"],
      ["“Tag-Switch Duo”", "Price-tag swapping, refund fraud"],
      ["“Grey Hoodie Regular”", "Repeat offender, banned chain-wide"],
    ],
  },
  access: {
    logTitle: "Stockroom / cash office · access log",
    note: "Stockroom and cash office release only on face-whitelist match — a borrowed lanyard alone never opens the door. Every entry feeds the shrinkage audit.",
  },
  analytics: {
    panelTitle: "Department performance · footfall & dwell",
    visitLabel: "SHOPPER VISITS",
    staffingTitle: "FLOOR COVERAGE · LIVE RECOMMENDATION",
    staffing: (zone, ratio) =>
      `${zone} is running ${ratio} shoppers per associate — queue risk building. Float one associate from the quietest department and open a second till nearby.`,
    balanced: "Associate coverage is balanced across all departments. No floats needed right now.",
    footer:
      "Grades drive space planning: A+ departments earn premium placement and staffing, backed by verified footfall + dwell — staff filtered out.",
  },
  classification: {
    whyTitle: "WHY IT MATTERS",
    whyText:
      "Associates are stripped from traffic, dwell and heatmap metrics — otherwise two staff folding stock all day would make that department look artificially busy and corrupt conversion data.",
  },
  modes: {
    show: "● STORE OPEN",
    after: "◐ STORE CLOSED",
    showBadge: "● TRADING — BASELINE LEARNING ACTIVE",
    afterBadge: "◐ EAS + AI PERIMETER ARMED",
  },
  copy: {
    tether: (zone, tag) => ({
      title: "High-value item left display tether",
      detail: `RFID tag ${tag} crossed its tethered display boundary in ${zone}. EAS pedestal pair confirms direction of travel — LP vectoring.`,
    }),
    sleight: (zone, conf) => ({
      title: "Concealment motion at shelf",
      detail: `Hand-to-bag occlusion signature (${conf}% match) at ${zone}. Item count delta under verification — plain-clothes LP notified.`,
    }),
    reachin: (zone, secs) => ({
      title: "Reach into staff-only POS zone",
      detail: `Non-whitelisted hand crossed the staff line at ${zone} for ${secs}s. Till drawer state verified — nearest associate alerted.`,
    }),
    loiter: (zone, personId, dwell) => ({
      title: `Prolonged hover at ${zone.split(" ")[0]} shelf`,
      detail: `${personId} has lingered ${dwell}s at a high-value shelf without staff contact. Department baseline is 14s. 3rd pass this visit.`,
    }),
    blacklist: (alias, conf, knownFor) => ({
      title: `Known ORC offender at entrance — ${conf}%`,
      detail: `${alias} matched the shared retail watchlist (${knownFor}). Silent alert to LP — do not approach; track and stage at exits on signal.`,
    }),
    imposter: (zone) => ({
      title: "Staff lanyard without whitelist face",
      detail: `Person wearing a staff lanyard attempted ${zone} access but failed continuous face verification. Door stayed locked; LP dispatched.`,
    }),
    vaultAccess: (zone, person) => ({
      title: `${zone} opened after hours`,
      detail: `${person} entered ${zone} on biometric release. Session recorded for the shrinkage audit trail.`,
    }),
    perimeter: {
      title: "After-hours motion on sales floor",
      detail: "Movement vector detected near the high-value wall outside cleaning-crew schedule. Whitelist cross-check running.",
    },
    vipArrival: (name, tier, interest, greeter, conf) => ({
      title: `Loyalty ${tier} recognized — ${name}`,
      detail: `Face-matched at Doors 1–2 (${conf}%). Usually shops: ${interest}. Client advisor ${greeter} notified to greet by name.`,
    }),
    staffing: (zone, ratio) => ({
      title: "Queue risk — coverage gap",
      detail: `${zone} is at ${ratio} shoppers per associate. Recommend floating 1 associate from the quietest adjacent department.`,
    }),
    arm: {
      title: "Store closed — AI perimeter armed",
      detail: "Gates locked. Virtual fence active around the high-value wall, stockroom and cash office. All floor motion is anomalous by default.",
    },
    disarm: {
      title: "Perimeter disarmed — store open",
      detail: "Doors open for trading. Behavioural baselines re-learning for the first 15 minutes.",
    },
    seeds: [
      {
        sev: "P3",
        type: "STAFFING",
        title: "Queue risk — coverage gap",
        detail: "B1 · Fine Watches ran 4.8 shoppers per associate for 15 minutes. One associate floated from Footwear.",
        loc: "B1 · Fine Watches",
        cam: "CAM-02",
      },
      {
        sev: "P2",
        type: "CASING / LOITER",
        title: "Prolonged hover at C2 shelf",
        detail: "T-064 lingered 52s at the Electronics wall without staff contact. Subject left with one item — POS cross-check passed.",
        loc: "C2 · Electronics",
        cam: "CAM-03",
      },
      {
        sev: "P1",
        type: "TETHER BREACH",
        title: "High-value item left display tether",
        detail: "RFID tag C2-412 crossed its tether boundary. Located at the returns desk — customer forgot the security tag. Closed.",
        loc: "C2 · Electronics",
        cam: "CAM-03",
      },
    ],
  },
};

/* ============================ RESTAURANT ============================ */

const restaurant: Template = {
  id: "restaurant",
  tab: "DINING",
  venue: "Maison Olive — Fine Dining Group",
  venueSub: "Flagship room · dinner service · 8 sections · full house",
  floorName: "Dining room · service map",
  entranceLabel: "HOST PODIUM · FACE CAPTURE",
  rooms: { vault: "WINE CELLAR", backroom: "KITCHEN" },
  accessZones: ["Kitchen", "Wine Cellar", "Office"],
  zones: [
    { id: "A1", name: "Bar & Lounge", tier: "standard" },
    { id: "B1", name: "Chef's Counter", tier: "high" },
    { id: "C1", name: "Main Dining N", tier: "standard" },
    { id: "D1", name: "Terrace", tier: "standard" },
    { id: "A2", name: "Main Dining S", tier: "standard" },
    { id: "B2", name: "Window Row", tier: "standard" },
    { id: "C2", name: "Private Room", tier: "high" },
    { id: "D2", name: "Sommelier Station", tier: "standard" },
  ],
  cameras: [
    cam("CAM-01", "HOST PODIUM", "Entrance · coat check", "entrance", 11),
    cam("CAM-02", "DINING HALL", "Main dining / bar", "aisle", 47),
    cam("CAM-03", "CHEF'S COUNTER · WINE", "Counter · cellar display", "highvalue", 83),
    cam("CAM-04", "KITCHEN CORRIDOR", "Kitchen · cellar door", "vault", 129),
  ],
  visitorNoun: "diners on floor",
  visitorsLabel: "DINERS",
  featuredCamNote: "wine display tether + POS watch active",
  vip: {
    title: "VIP reservations · door alerts",
    subtitle: "recognized at the podium",
    emptyText:
      "No VIP arrivals yet — the podium camera matches every walk-in against the reservation book and guest-history register.",
    names: [
      ["Contessa Bianca Ricci", "PLATINUM", "42 visits", "chef's table, Barolo"],
      ["Henry K. Lacroix", "GOLD", "18 visits", "window table, tasting menu"],
      ["Dr. Amara Osei", "PLATINUM", "35 visits", "private room, corporate"],
      ["Takeshi Mori", "GOLD", "12 visits", "omakase counter"],
      ["Elena Vasquez-Ruiz", "PLATINUM", "51 visits", "anniversary regular"],
      ["Sir Julian Ashe", "GOLD", "9 visits", "sommelier pairing"],
    ],
    greeters: ["Maître d' L. Beaumont", "Maître d' C. Rossi", "GM A. Fontana"],
  },
  blacklist: {
    title: "Dine-and-dash watchlist · face matching",
    emptyText:
      "No matches this session — podium feed cross-referencing every arrival against the shared serial-offender register for the group.",
    aliases: [
      ["“The Vanishing Couple”", "Walked 4 bills, city-wide pattern"],
      ["“Solo Sprinter”", "Dash-and-run at 3 group venues"],
      ["“Card Decliner”", "Fake payment attempts, 6 incidents"],
      ["“Reservation Ghost”", "No-show fraud + bar tab walks"],
    ],
  },
  access: {
    logTitle: "Kitchen / wine cellar · access log",
    note: "Kitchen and cellar doors release only for whitelisted staff faces — a borrowed apron or jacket never opens them. Every entry feeds the stock-variance audit.",
  },
  analytics: {
    panelTitle: "Service analytics · sections & table time",
    visitLabel: "TABLE SEATINGS",
    staffingTitle: "SECTION COVERAGE · LIVE RECOMMENDATION",
    staffing: (zone, ratio) =>
      `${zone} is running ${ratio} covers per server — ticket times will slip. Reassign one server from the quietest section for the next seating.`,
    balanced: "Server coverage is balanced across all sections. No reassignment needed right now.",
    footer:
      "Grades drive section planning: A+ sections justify premium table placement and your best servers, backed by verified seatings + table time — staff filtered out.",
  },
  classification: {
    whyTitle: "WHY IT MATTERS",
    whyText:
      "Servers are stripped from seating, table-time and heatmap metrics — otherwise two staff stationed at the pass all night would make that section look artificially busy and corrupt service data.",
  },
  modes: {
    show: "● SERVICE",
    after: "◐ OVERNIGHT",
    showBadge: "● IN SERVICE — BASELINE LEARNING ACTIVE",
    afterBadge: "◐ OVERNIGHT — CELLAR & KITCHEN ARMED",
  },
  copy: {
    tether: (zone, tag) => ({
      title: "Bottle left the cellar display tether",
      detail: `Bottle tag ${tag} left the tethered wine display at ${zone} without a POS pour entry. Sommelier notified to verify.`,
    }),
    sleight: (zone, conf) => ({
      title: "Card-swap motion at payment point",
      detail: `Hand-occlusion signature (${conf}% match) at the ${zone} POS — possible card skim or bill switch. Manager reviewing the clip.`,
    }),
    reachin: (zone, secs) => ({
      title: "Hand across the pass into kitchen line",
      detail: `Non-whitelisted hand crossed the pass at ${zone} for ${secs}s. Food-safety protocol — expo notified, line check triggered.`,
    }),
    loiter: (zone, personId, dwell) => ({
      title: `Unseated hover near ${zone.split(" ")[0]}`,
      detail: `${personId} has hovered ${dwell}s near ${zone} without being seated or served — consistent with casing a payment point. Floor manager has eyes.`,
    }),
    blacklist: (alias, conf, knownFor) => ({
      title: `Watchlist arrival at podium — ${conf}%`,
      detail: `${alias} matched the group register (${knownFor}). Silent alert to the floor — seat within camera arc, pre-authorize payment.`,
    }),
    imposter: (zone) => ({
      title: "Staff jacket without whitelist face",
      detail: `Person in staff uniform attempted ${zone} access but failed continuous face verification. Door stayed locked; manager dispatched.`,
    }),
    vaultAccess: (zone, person) => ({
      title: `${zone} opened overnight`,
      detail: `${person} entered ${zone} on biometric release. Session recorded against tonight's stock-variance audit.`,
    }),
    perimeter: {
      title: "Overnight motion near cellar door",
      detail: "Movement vector detected in the kitchen corridor outside the cleaning roster. Whitelist cross-check running.",
    },
    vipArrival: (name, tier, interest, greeter, conf) => ({
      title: `${tier} guest recognized — ${name}`,
      detail: `Face-matched at the podium (${conf}%). Preferences: ${interest}. ${greeter} notified to greet by name.`,
    }),
    staffing: (zone, ratio) => ({
      title: "Section running hot",
      detail: `${zone} is at ${ratio} covers per server. Recommend reassigning 1 server from the quietest section before the next seating.`,
    }),
    arm: {
      title: "Overnight watch armed",
      detail: "Last seating closed. Virtual fence active around the cellar, kitchen and POS stations. All motion is anomalous by default.",
    },
    disarm: {
      title: "Perimeter disarmed — service begins",
      detail: "Doors open for service. Behavioural baselines re-learning for the first 15 minutes.",
    },
    seeds: [
      {
        sev: "P3",
        type: "STAFFING",
        title: "Section running hot",
        detail: "C1 · Main Dining N ran 6.1 covers per server for 20 minutes. One server reassigned from Terrace.",
        loc: "C1 · Main Dining N",
        cam: "CAM-02",
      },
      {
        sev: "P2",
        type: "CASING / LOITER",
        title: "Unseated hover near D2",
        detail: "T-091 hovered 48s near the Sommelier Station POS. Seated shortly after at the bar — kept on soft track.",
        loc: "D2 · Sommelier Station",
        cam: "CAM-03",
      },
      {
        sev: "P1",
        type: "TETHER BREACH",
        title: "Bottle left the cellar display tether",
        detail: "Bottle tag B1-207 left the display without a POS entry. Located — sommelier moved it for a decant, entry logged. Closed.",
        loc: "B1 · Chef's Counter",
        cam: "CAM-03",
      },
    ],
  },
};

/* ============================ IT OFFICE ============================ */

const office: Template = {
  id: "office",
  tab: "OFFICE",
  venue: "Nexbyte Technologies — HQ Level 7",
  venueSub: "Open floor · 8 team zones · 12 areas · badge-only entry",
  floorName: "Level 7 · workspace map",
  entranceLabel: "LOBBY TURNSTILES · FACE CAPTURE",
  rooms: { vault: "SERVER RM", backroom: "COMMS CLOSET" },
  accessZones: ["Server Room", "Comms Closet", "Exec Suite"],
  zones: [
    { id: "A1", name: "Platform Engineering", tier: "standard" },
    { id: "B1", name: "QA Hardware Lab", tier: "high" },
    { id: "C1", name: "Data Science", tier: "standard" },
    { id: "D1", name: "Support Hub", tier: "standard" },
    { id: "A2", name: "Product & Design", tier: "standard" },
    { id: "B2", name: "DevOps / SRE", tier: "standard" },
    { id: "C2", name: "Exec Suite", tier: "high" },
    { id: "D2", name: "Lobby Lounge", tier: "standard" },
  ],
  cameras: [
    cam("CAM-01", "LOBBY TURNSTILES", "Reception · turnstiles", "entrance", 11),
    cam("CAM-02", "OPEN FLOOR N", "Platform / Data Science", "aisle", 47),
    cam("CAM-03", "HW LAB · EXEC", "QA Lab · Exec Suite", "highvalue", 83),
    cam("CAM-04", "SERVER CORRIDOR", "Server Rm · Comms", "vault", 129),
  ],
  visitorNoun: "people on floor",
  visitorsLabel: "VISITORS",
  featuredCamNote: "asset tether + escort rules active",
  vip: {
    title: "Executive visitor alerts",
    subtitle: "recognized at turnstiles",
    emptyText:
      "No executive visitors yet — turnstile cameras match every arrival against the board, investor and client register.",
    names: [
      ["Alexandra Reeves", "PLATINUM", "Board", "Q3 review prep"],
      ["Rajiv Menon", "PLATINUM", "Series C lead", "due-diligence visit"],
      ["Karen Doyle", "GOLD", "Enterprise client", "renewal meeting"],
      ["Prof. Elias Grant", "GOLD", "Advisor", "research sync"],
      ["Mira Solberg", "PLATINUM", "Board observer", "audit committee"],
      ["Tomás Herrera", "GOLD", "Strategic partner", "integration workshop"],
    ],
    greeters: ["EA to CEO · P. Nair", "CFO Office · D. Sloan", "People Ops · J. Kim"],
  },
  blacklist: {
    title: "Flagged-person register · face matching",
    emptyText:
      "No matches this session — turnstile feed cross-referencing every face against revoked-badge and social-engineering registers.",
    aliases: [
      ["“Badge Cloner”", "Tailgating at 2 campuses"],
      ["“Terminated Eng. T.K.”", "Revoked badge, 3 entry attempts"],
      ["“Fake HVAC Contractor”", "Social engineering, facilities ruse"],
      ["“Recruiter Poacher”", "Restricted-floor soliciting"],
    ],
  },
  access: {
    logTitle: "Server room / comms · access log",
    note: "Restricted doors release only on face-whitelist match — a cloned badge alone never opens the server room. Every entry feeds the insider-risk audit.",
  },
  analytics: {
    panelTitle: "Workspace analytics · zone occupancy",
    visitLabel: "ZONE CHECK-INS",
    staffingTitle: "FACILITIES · LIVE RECOMMENDATION",
    staffing: (zone, ratio) =>
      `${zone} is running ${ratio} people per support point — expect ticket and desk-pressure. Shift floater coverage from the quietest zone.`,
    balanced: "Coverage is balanced across all zones. No facilities action needed right now.",
    footer:
      "Grades drive real-estate planning: A+ zones justify expansion and premium fit-out, backed by verified occupancy + dwell — staff movement filtered to true utilization.",
  },
  classification: {
    whyTitle: "WHY IT MATTERS",
    whyText:
      "Badged employees are separated from visitors and contractors — otherwise headcount, visitor-escort compliance and occupancy analytics would blend three populations into meaningless numbers.",
  },
  modes: {
    show: "● WORK HOURS",
    after: "◐ AFTER HOURS",
    showBadge: "● WORK HOURS — BASELINE LEARNING ACTIVE",
    afterBadge: "◐ AFTER HOURS — FLOOR PERIMETER ARMED",
  },
  copy: {
    tether: (zone, tag) => ({
      title: "Asset tether breach",
      detail: `Asset tag ${tag} (laptop / test rig) left ${zone} without an equipment-checkout entry. ITAM cross-check running.`,
    }),
    sleight: (zone, conf) => ({
      title: "Equipment swap at hot desk",
      detail: `Hand-occlusion + device-swap signature (${conf}% match) at ${zone}. Serial reconciliation running against the asset register.`,
    }),
    reachin: (zone, secs) => ({
      title: "Reach into restricted bench zone",
      detail: `Non-whitelisted hand crossed into the ${zone} restricted bench for ${secs}s. Lab owner notified; bench inventory check queued.`,
    }),
    loiter: (zone, personId, dwell) => ({
      title: `Unescorted hover near ${zone.split(" ")[0]}`,
      detail: `${personId} has lingered ${dwell}s near ${zone} without a registered escort — visitor-policy breach pattern. Reception notified.`,
    }),
    blacklist: (alias, conf, knownFor) => ({
      title: `Flagged individual at turnstiles — ${conf}%`,
      detail: `${alias} matched the flagged-person register (${knownFor}). Silent alert to security — hold turnstile, verify identity at reception.`,
    }),
    imposter: (zone) => ({
      title: "Contractor badge without whitelist face",
      detail: `Person badged as contractor attempted ${zone} access but failed continuous face verification. Door stayed locked; security dispatched.`,
    }),
    vaultAccess: (zone, person) => ({
      title: `${zone} badge-in after hours`,
      detail: `${person} entered ${zone} on biometric release. Session recorded for the insider-risk audit.`,
    }),
    perimeter: {
      title: "After-hours motion on open floor",
      detail: "Movement vector detected near the server corridor outside the approved on-call roster. Whitelist cross-check running.",
    },
    vipArrival: (name, tier, interest, greeter, conf) => ({
      title: `${tier} visitor recognized — ${name}`,
      detail: `Face-matched at the turnstiles (${conf}%). Context: ${interest}. ${greeter} notified to meet at reception.`,
    }),
    staffing: (zone, ratio) => ({
      title: "Zone pressure — support gap",
      detail: `${zone} is at ${ratio} people per support point. Recommend shifting floater coverage from the quietest zone.`,
    }),
    arm: {
      title: "After-hours perimeter armed",
      detail: "Floor closed. Virtual fence active around the server room, comms closet and hardware lab. All motion is anomalous by default.",
    },
    disarm: {
      title: "Perimeter disarmed — work hours",
      detail: "Floor open. Behavioural baselines re-learning for the first 15 minutes.",
    },
    seeds: [
      {
        sev: "P3",
        type: "STAFFING",
        title: "Zone pressure — support gap",
        detail: "D1 · Support Hub ran 5.4 people per support point for 25 minutes. Floater shifted from Lobby Lounge.",
        loc: "D1 · Support Hub",
        cam: "CAM-02",
      },
      {
        sev: "P2",
        type: "CASING / LOITER",
        title: "Unescorted hover near B1",
        detail: "Visitor T-042 lingered 39s by the QA Hardware Lab without a registered escort. Host located — escort rule re-briefed.",
        loc: "B1 · QA Hardware Lab",
        cam: "CAM-03",
      },
      {
        sev: "P1",
        type: "IMPOSTER",
        title: "Contractor badge without whitelist face",
        detail: "Cloned contractor badge presented at Server Room. Face verification failed, door stayed locked. Badge revoked, incident closed.",
        loc: "Server Room",
        cam: "CAM-04",
      },
    ],
  },
};

export const TEMPLATES: Record<TemplateId, Template> = {
  expo,
  retail,
  restaurant,
  office,
};

export const TEMPLATE_ORDER: TemplateId[] = ["expo", "retail", "restaurant", "office"];
