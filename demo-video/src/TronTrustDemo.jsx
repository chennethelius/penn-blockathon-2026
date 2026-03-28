import {
  AbsoluteFill,
  useCurrentFrame,
  interpolate,
  Sequence,
} from "remotion";

// 1800 frames = 60s at 30fps

const BG     = "#06000a";
const RED    = "#e8261a";
const GREEN  = "#22c55e";
const BLUE   = "#3b82f6";
const AMBER  = "#facc15";
const PURPLE = "#8b5cf6";
const WHITE  = "#ffffff";
const DIM    = "#c8bcd8";

const clamp = { extrapolateRight: "clamp", extrapolateLeft: "clamp" };
const fade  = (f, s, d = 10) => interpolate(f, [s, s + d], [0, 1], clamp);
const up    = (f, s, d = 12) => interpolate(f, [s, s + d], [40, 0], clamp);
const slam  = (f, s, d = 10) => interpolate(f, [s, s + d], [1.3, 1], clamp);
const barW  = (f, s, e, mx)  => `${interpolate(f, [s, e], [0, mx], clamp)}%`;
const roll  = (f, s, e, target, dec = 0) => {
  const v = interpolate(f, [s, e], [0, target], clamp);
  return dec > 0 ? v.toFixed(dec) : Math.round(v).toLocaleString();
};

// Character-by-character split animation
const splitWord = (word, frame, start, color = WHITE, stagger = 3) =>
  [...word].map((ch, i) => {
    const sf = start + i * stagger;
    return (
      <span key={i} style={{
        display: "inline-block",
        opacity: interpolate(frame, [sf, sf + 8], [0, 1], clamp),
        transform: `translateY(${interpolate(frame, [sf, sf + 9], [30, 0], clamp)}px)`,
        color,
      }}>{ch === " " ? "\u00A0" : ch}</span>
    );
  });

const base = { fontFamily: "'Inter','SF Pro Display',system-ui,sans-serif", color: WHITE };

// ── Particle network (computed outside component for stable refs) ──
const PARTICLES = Array.from({ length: 24 }, (_, i) => ({
  bx: ((Math.cos(i * 2.399963) + 1) / 2) * 1820 + 50,
  by: ((Math.sin(i * 2.399963 * 0.618) + 1) / 2) * 950 + 65,
  sx: 0.22 + (i % 5) * 0.055,
  sy: 0.17 + (i % 7) * 0.048,
  ph: i * 1.1,
  r:  1.5 + (i % 3) * 0.7,
}));

const Particles = () => {
  const f = useCurrentFrame();
  const pts = PARTICLES.map(p => ({
    x: p.bx + Math.sin(f * p.sx * 0.02 + p.ph) * 100,
    y: p.by + Math.cos(f * p.sy * 0.02 + p.ph * 0.7) * 78,
    r: p.r,
  }));
  const lines = [];
  for (let i = 0; i < pts.length; i++)
    for (let j = i + 1; j < pts.length; j++) {
      const d = Math.hypot(pts[i].x - pts[j].x, pts[i].y - pts[j].y);
      if (d < 320) lines.push({ x1: pts[i].x, y1: pts[i].y, x2: pts[j].x, y2: pts[j].y, o: (1 - d / 320) * 0.27 });
    }
  return (
    <svg style={{ position: "absolute", inset: 0, width: 1920, height: 1080, zIndex: 2, pointerEvents: "none" }}>
      {lines.map((l, i) => <line key={i} x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2} stroke={RED} strokeWidth={0.7} opacity={l.o} />)}
      {pts.map((p, i) => <circle key={i} cx={p.x} cy={p.y} r={p.r} fill={RED} opacity={0.5} />)}
    </svg>
  );
};

// ── Film grain ──
const FilmGrain = () => {
  const f = useCurrentFrame();
  return (
    <div style={{
      position: "absolute", inset: 0, zIndex: 50, pointerEvents: "none",
      opacity: 0.042, mixBlendMode: "overlay",
      backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='256' height='256'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")`,
      backgroundPosition: `${(f * 37) % 256}px ${(f * 53) % 256}px`,
    }} />
  );
};

// ── Vignette ──
const Vignette = () => (
  <div style={{
    position: "absolute", inset: 0, zIndex: 5, pointerEvents: "none",
    background: "radial-gradient(ellipse at center, transparent 42%, rgba(0,0,0,0.72) 100%)",
  }} />
);

// ── Transaction ticker (always-on bottom strip) ──
const TX = [
  "TX: TXk3mP9r...→ TLyqzRJ... · $42,100 USDT",
  "TX: TMal9x2k...→ TQJrxetk... · $8,750 USDT",
  "TX: TNpENknR...→ TWash4Lp... · $127,400 USDT",
  "TX: TFrz7Kq1...→ TBlck8d2... · $3,200 USDT",
  "TX: TPois3n8...→ TGate7ff... · $55,000 USDT",
  "TX: TSent1r4...→ TCom8rx5... · $19,900 USDT",
  "TX: TLnjvkwm...→ TScam9xK... · $1,000 USDT  ⚠ BLOCKED by Kairos",
  "TX: TJtw1YMJ...→ TVaultXX... · $230,000 USDT",
].join("   ·   ");
const TX5 = (TX + "   ·   ").repeat(5);

const Ticker = () => {
  const f = useCurrentFrame();
  return (
    <div style={{
      position: "absolute", bottom: 0, left: 0, right: 0, height: 40,
      background: "rgba(3,0,8,0.95)", borderTop: "1px solid rgba(232,38,26,0.3)",
      display: "flex", alignItems: "center", zIndex: 40, overflow: "hidden",
    }}>
      <span style={{ fontSize: 12, fontWeight: 900, color: RED, letterSpacing: "0.14em", padding: "0 16px", flexShrink: 0, borderRight: "1px solid rgba(232,38,26,0.35)" }}>
        LIVE
      </span>
      <div style={{ flex: 1, overflow: "hidden" }}>
        <div style={{
          transform: `translateX(${-(f * 3)}px)`,
          whiteSpace: "nowrap", fontFamily: "monospace", fontSize: 14, color: DIM, letterSpacing: "0.025em",
        }}>{TX5}</div>
      </div>
    </div>
  );
};

// ── Laser streaks ──
const STREAKS = [
  { s: 55,   d: 24, y: 0.27, c: RED   },
  { s: 165,  d: 20, y: 0.61, c: RED   },
  { s: 310,  d: 22, y: 0.18, c: WHITE },
  { s: 460,  d: 20, y: 0.74, c: RED   },
  { s: 600,  d: 18, y: 0.44, c: RED   },
  { s: 780,  d: 22, y: 0.55, c: WHITE },
  { s: 960,  d: 20, y: 0.33, c: RED   },
  { s: 1110, d: 18, y: 0.68, c: RED   },
  { s: 1270, d: 22, y: 0.22, c: WHITE },
  { s: 1430, d: 20, y: 0.49, c: RED   },
  { s: 1560, d: 18, y: 0.82, c: RED   },
  { s: 1700, d: 22, y: 0.36, c: RED   },
];

const LaserStreaks = () => {
  const f = useCurrentFrame();
  return (
    <div style={{ position: "absolute", inset: 0, zIndex: 15, pointerEvents: "none", overflow: "hidden" }}>
      {STREAKS.map((s, i) => {
        if (f < s.s || f >= s.s + s.d) return null;
        const t = (f - s.s) / s.d;
        const op = Math.sin(t * Math.PI) * 0.52;
        const pct = `${t * 100}%`;
        return (
          <div key={i} style={{
            position: "absolute", top: `${s.y * 100}%`, left: 0, right: 0, height: 1,
            background: `linear-gradient(90deg,transparent ${Math.max(0, t * 100 - 18)}%,${s.c}cc ${pct},transparent ${Math.min(100, t * 100 + 18)}%)`,
            opacity: op,
          }} />
        );
      })}
    </div>
  );
};

// ── SVG score ring ──
const ScoreRing = ({ score, color, size = 300 }) => {
  const r = size / 2 - 16;
  const circ = 2 * Math.PI * r;
  const offset = circ - (Math.min(score, 100) / 100) * circ;
  return (
    <svg width={size} height={size} style={{ position: "absolute", transform: "rotate(-90deg)", filter: `drop-shadow(0 0 12px ${color}99)` }}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={11} />
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth={11}
        strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round" />
    </svg>
  );
};

// ── Typing line ──
const Typed = ({ text, frame, start, color = WHITE, speed = 1.6 }) => {
  const chars = Math.floor(interpolate(frame, [start, start + text.length / speed], [0, text.length + 1], clamp));
  const done  = chars > text.length;
  const blink = Math.floor(frame / 9) % 2 === 0;
  return (
    <span style={{ color }}>
      {text.slice(0, Math.min(chars, text.length))}
      {!done && blink && <span style={{ opacity: 0.85 }}>▋</span>}
    </span>
  );
};

// ── Shared layout atoms ──
const Grid = ({ opacity = 0.04 }) => (
  <div style={{
    position: "absolute", inset: 0, pointerEvents: "none", zIndex: 1,
    backgroundImage: `linear-gradient(rgba(232,38,26,${opacity}) 1px,transparent 1px),linear-gradient(90deg,rgba(232,38,26,${opacity}) 1px,transparent 1px)`,
    backgroundSize: "80px 80px",
  }} />
);

const Glow = ({ opacity = 1, color = RED, size = 700 }) => (
  <div style={{
    position: "absolute", top: "50%", left: "50%", transform: "translate(-50%,-50%)",
    width: size, height: size * 0.58,
    background: `radial-gradient(ellipse,${color}28 0%,transparent 65%)`,
    opacity, pointerEvents: "none",
  }} />
);

const TopLine = ({ color = RED }) => (
  <div style={{
    position: "absolute", top: 0, left: 0, right: 0, height: 3, zIndex: 20,
    background: `linear-gradient(90deg,transparent,${color} 25%,${color} 75%,transparent)`,
  }} />
);

const Corners = ({ color = RED, opacity = 0.6 }) => {
  const c = (pos) => ({ position: "absolute", width: 34, height: 34, borderColor: color, borderStyle: "solid", opacity, ...pos });
  return (
    <>
      <div style={c({ top: 28, left: 28, borderWidth: "2px 0 0 2px" })} />
      <div style={c({ top: 28, right: 28, borderWidth: "2px 2px 0 0" })} />
      <div style={c({ bottom: 68, left: 28, borderWidth: "0 0 2px 2px" })} />
      <div style={c({ bottom: 68, right: 28, borderWidth: "0 2px 2px 0" })} />
    </>
  );
};

const ScanLines = () => (
  <div style={{
    position: "absolute", inset: 0, pointerEvents: "none", zIndex: 10,
    backgroundImage: "repeating-linear-gradient(0deg,rgba(0,0,0,0.11) 0px,rgba(0,0,0,0.11) 1px,transparent 1px,transparent 4px)",
  }} />
);

const Label = ({ children, style = {} }) => (
  <div style={{ fontSize: 28, fontWeight: 800, letterSpacing: "0.18em", color: RED, textTransform: "uppercase", ...style }}>
    {children}
  </div>
);

// ═══════════════════════════════════════════════════════
// SCENE 1 — HOOK  0–3s  (90f)
// ═══════════════════════════════════════════════════════
const HookScene = () => {
  const f = useCurrentFrame();
  const miniStats = [
    { label: "WALLETS MONITORED", val: roll(f, 20, 75, 14545) },
    { label: "USDT VOLUME / DAY",  val: `$${interpolate(f, [20, 75], [0, 21.6], clamp).toFixed(1)}B` },
    { label: "THREATS BLOCKED",    val: roll(f, 20, 75, 8847) },
  ];
  return (
    <AbsoluteFill style={{ ...base, background: BG, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", paddingBottom: 40 }}>
      <TopLine />
      <Grid opacity={0.07} />
      <Particles />
      <Vignette />
      <Glow opacity={fade(f, 0, 35)} size={1400} />
      <Corners opacity={0.45} />

      {/* Top mini-stats bar */}
      <div style={{ display: "flex", gap: 0, marginBottom: 60, opacity: fade(f, 18, 12) }}>
        {miniStats.map((s, i) => (
          <div key={s.label} style={{
            padding: "14px 52px", textAlign: "center",
            borderRight: i < 2 ? "1px solid rgba(232,38,26,0.2)" : "none",
          }}>
            <div style={{ fontSize: 36, fontWeight: 900, color: RED, letterSpacing: "-0.02em" }}>{s.val}</div>
            <div style={{ fontSize: 13, fontWeight: 700, color: DIM, letterSpacing: "0.14em", marginTop: 4 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Character-split main headline */}
      <div style={{ fontSize: 152, fontWeight: 900, letterSpacing: "-0.05em", lineHeight: 0.88, textAlign: "center" }}>
        {splitWord("EVERY SECOND", f, 0, WHITE, 3)}
      </div>
      <div style={{ fontSize: 152, fontWeight: 900, letterSpacing: "-0.05em", lineHeight: 0.88, textAlign: "center", marginTop: 8 }}>
        {splitWord("ON TRON—", f, 12, RED, 4)}
      </div>

      {/* Subtitle */}
      <div style={{ opacity: fade(f, 52, 10), fontSize: 24, color: DIM, marginTop: 38, letterSpacing: "0.04em", textAlign: "center" }}>
        Someone is getting scammed. No one knows. Until now.
      </div>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════
// SCENE 2 — STAT SHOCK  3–13s  (300f)
// ═══════════════════════════════════════════════════════
const StatShockScene = () => {
  const f = useCurrentFrame();
  const stats = [
    { prefix: "$", suffix: "M", target: 31.5, dec: 1, label: "STOLEN", sub: "Energy drain attacks", source: "Chainalysis Q4 2024" },
    { prefix: "+", suffix: "%", target: 1400, dec: 0, label: "SURGE",  sub: "Impersonation scam growth", source: "Chainalysis 2026" },
    { prefix: "",  suffix: "%", target: 58,   dec: 0, label: "ILLICIT", sub: "of all illicit crypto",    source: "Elliptic 2024" },
  ];
  return (
    <AbsoluteFill style={{ ...base, background: BG, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", paddingBottom: 40 }}>
      <TopLine />
      <Grid />
      <Particles />
      <Vignette />
      <Glow opacity={0.65} />
      <ScanLines />
      <Corners opacity={0.35} />

      <Label style={{ marginBottom: 36, opacity: fade(f, 0, 8) }}>The Threat Is Real</Label>

      <div style={{ display: "flex", width: "100%" }}>
        {stats.map((s, i) => {
          const numStr = s.dec > 0
            ? `${s.prefix}${interpolate(f, [15 + i * 50, 120 + i * 50], [0, s.target], clamp).toFixed(s.dec)}${s.suffix}`
            : `${s.prefix}${Math.round(interpolate(f, [15 + i * 50, 120 + i * 50], [0, s.target], clamp)).toLocaleString()}${s.suffix}`;
          return (
            <div key={s.label} style={{
              flex: 1,
              opacity: fade(f, 12 + i * 40, 12),
              transform: `translateY(${up(f, 12 + i * 40, 12)}px) scale(${slam(f, 12 + i * 40, 10)})`,
              padding: "44px 44px",
              borderRight: i < 2 ? "1px solid rgba(232,38,26,0.18)" : "none",
              textAlign: "center",
            }}>
              <div style={{ fontSize: 108, fontWeight: 900, letterSpacing: "-0.04em", color: RED, lineHeight: 1 }}>{numStr}</div>
              <div style={{ fontSize: 16, fontWeight: 900, letterSpacing: "0.2em", color: WHITE, marginTop: 14 }}>{s.label}</div>
              <div style={{ fontSize: 20, color: DIM, marginTop: 10, whiteSpace: "nowrap" }}>{s.sub}</div>
              <div style={{ fontSize: 13, color: "rgba(200,188,216,0.45)", marginTop: 8, letterSpacing: "0.08em", fontStyle: "italic" }}>{s.source}</div>
            </div>
          );
        })}
      </div>

      {/* Divider line */}
      <div style={{ opacity: fade(f, 200, 12), width: "80%", height: 1, background: "linear-gradient(90deg,transparent,rgba(232,38,26,0.4),transparent)", margin: "24px 0" }} />

      <div style={{ opacity: fade(f, 210, 14), fontSize: 28, color: DIM, textAlign: "center", maxWidth: 920, lineHeight: 1.45 }}>
        Without trust infrastructure, every TRON wallet is flying blind.
      </div>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════
// SCENE 3 — SOLUTION DROP  13–21s  (240f)
// ═══════════════════════════════════════════════════════
const SolutionDropScene = () => {
  const f = useCurrentFrame();
  const glow = 0.5 + 0.28 * Math.sin(f * 0.1);
  const quickFeats = [
    { label: "ML Engine",    val: "XGBoost · 50 features", c: AMBER },
    { label: "On-Chain",     val: "5 smart contracts",      c: BLUE  },
    { label: "Real-Time",    val: "Sentinel · 30s poll",    c: RED   },
    { label: "Monetised",    val: "x402 pay-per-call",      c: GREEN },
  ];
  return (
    <AbsoluteFill style={{ ...base, background: BG, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", paddingBottom: 40 }}>
      <TopLine />
      <Grid />
      <Particles />
      <Vignette />
      <Glow opacity={glow} size={1200} />
      <Corners />

      <Label style={{ marginBottom: 20, opacity: fade(f, 8, 8) }}>Introducing</Label>

      {/* Logo slam */}
      <div style={{ opacity: fade(f, 0, 12), transform: `scale(${slam(f, 0, 14)})`, display: "flex", alignItems: "baseline", marginBottom: 18 }}>
        <span style={{ fontSize: 148, fontWeight: 900, letterSpacing: "-0.05em", color: RED, lineHeight: 0.9 }}>KAI</span>
        <span style={{ fontSize: 148, fontWeight: 900, letterSpacing: "-0.05em", color: WHITE, lineHeight: 0.9 }}>ROS</span>
      </div>

      <div style={{ opacity: fade(f, 38, 12), transform: `translateY(${up(f, 38, 12)}px)`, fontSize: 30, color: DIM, textAlign: "center", maxWidth: 820, lineHeight: 1.45, marginBottom: 36 }}>
        The trust layer TRON never had — for AI agents, DeFi, and B2B commerce.
      </div>

      {/* Feature quick-grid */}
      <div style={{ display: "flex", gap: 14, marginBottom: 24 }}>
        {quickFeats.map((feat, i) => (
          <div key={feat.label} style={{
            opacity: fade(f, 80 + i * 16, 10),
            transform: `translateY(${up(f, 80 + i * 16, 10)}px)`,
            background: `${feat.c}0d`, borderTop: `2px solid ${feat.c}`,
            padding: "16px 28px", minWidth: 200, textAlign: "center",
          }}>
            <div style={{ fontSize: 15, fontWeight: 800, color: feat.c, letterSpacing: "0.1em", marginBottom: 6 }}>{feat.label}</div>
            <div style={{ fontSize: 17, color: WHITE }}>{feat.val}</div>
          </div>
        ))}
      </div>

      {/* Verdict chips */}
      <div style={{ display: "flex", gap: 10, opacity: fade(f, 160, 12) }}>
        {[
          { l: "TRUSTED", c: GREEN }, { l: "REPUTABLE", c: BLUE },
          { l: "CAUTION", c: AMBER }, { l: "RISKY", c: "#f87171" }, { l: "BLACKLISTED", c: RED },
        ].map(v => (
          <div key={v.l} style={{ background: `${v.c}18`, border: `1px solid ${v.c}44`, padding: "8px 18px", fontSize: 16, fontWeight: 800, color: v.c, borderRadius: 3 }}>{v.l}</div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════
// SCENE 4 — HOW IT WORKS  21–33s  (360f)
// ═══════════════════════════════════════════════════════
const HowItWorksScene = () => {
  const f = useCurrentFrame();
  const steps = [
    {
      n: "01", color: BLUE, title: "Submit a wallet",
      bullets: ["REST API · MCP server · Web UI", "Any TRON address or token contract", "Response in < 200ms"],
    },
    {
      n: "02", color: AMBER, title: "Anubis ML scores it",
      bullets: ["XGBoost classifier · 50 features", "Monte Carlo confidence intervals", "6 threat types detected"],
    },
    {
      n: "03", color: GREEN, title: "Act on the verdict",
      bullets: ["TRUSTED → proceed instantly", "BLACKLISTED → block before signing", "5-band verdict scale"],
    },
  ];
  return (
    <AbsoluteFill style={{ ...base, background: BG, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "0 80px", paddingBottom: 40 }}>
      <TopLine />
      <Grid />
      <Particles />
      <Vignette />
      <Glow opacity={0.28} />

      <Label style={{ marginBottom: 18, opacity: fade(f, 0, 8) }}>How Kairos Works</Label>

      <div style={{ opacity: fade(f, 8, 10), fontSize: 68, fontWeight: 900, textAlign: "center", lineHeight: 1.1, marginBottom: 44 }}>
        Three steps. <span style={{ color: RED }}>Zero blind spots.</span>
      </div>

      <div style={{ display: "flex", gap: 20, width: "100%" }}>
        {steps.map((s, i) => (
          <div key={s.n} style={{
            flex: 1,
            opacity: fade(f, 52 + i * 42, 14),
            transform: `translateY(${up(f, 52 + i * 42, 14)}px)`,
            background: `${s.color}0d`, borderTop: `3px solid ${s.color}`,
            padding: "32px 32px",
          }}>
            <div style={{ fontSize: 54, fontWeight: 900, color: "rgba(255,255,255,0.5)", lineHeight: 1, marginBottom: 14 }}>{s.n}</div>
            <div style={{ fontSize: 28, fontWeight: 900, marginBottom: 18 }}>{s.title}</div>
            {s.bullets.map((b, j) => (
              <div key={j} style={{ display: "flex", alignItems: "flex-start", gap: 10, marginBottom: 10 }}>
                <span style={{ color: s.color, fontSize: 14, marginTop: 3, flexShrink: 0 }}>▸</span>
                <span style={{ fontSize: 18, color: DIM, lineHeight: 1.5 }}>{b}</span>
              </div>
            ))}
          </div>
        ))}
      </div>

      {/* Verdict pills */}
      <div style={{ opacity: fade(f, 285, 14), display: "flex", gap: 10, marginTop: 30 }}>
        {[
          { l: "TRUSTED", c: GREEN }, { l: "REPUTABLE", c: BLUE },
          { l: "CAUTION", c: AMBER }, { l: "RISKY", c: "#f87171" }, { l: "BLACKLISTED", c: RED },
        ].map((v, i) => (
          <div key={v.l} style={{
            opacity: fade(f, 292 + i * 10, 8),
            background: `${v.c}18`, border: `1px solid ${v.c}44`,
            padding: "10px 22px", fontSize: 17, fontWeight: 800, color: v.c, borderRadius: 3,
          }}>{v.l}</div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════
// SCENE 5 — LIVE DEMO  33–48s  (450f)
// ═══════════════════════════════════════════════════════
const LiveDemoScene = () => {
  const f = useCurrentFrame();
  const score     = Math.round(interpolate(f, [80, 178], [0, 88], clamp));
  const ringScore = interpolate(f, [80, 178], [0, 88], clamp);
  const sc        = score >= 80 ? GREEN : score >= 60 ? BLUE : score > 20 ? AMBER : RED;
  const verdict   = score >= 80 ? "TRUSTED" : score >= 60 ? "REPUTABLE" : score > 0 ? "ANALYZING..." : "";

  return (
    <AbsoluteFill style={{ ...base, background: BG, display: "flex", alignItems: "stretch" }}>
      <TopLine />
      <Grid />
      <Particles />
      <Vignette />
      <ScanLines />

      <div style={{ position: "absolute", top: 36, left: 0, right: 0, textAlign: "center", opacity: fade(f, 0, 8), zIndex: 20 }}>
        <Label>Live Demo</Label>
      </div>

      <div style={{ display: "flex", gap: 20, padding: "88px 70px 50px", width: "100%" }}>

        {/* LEFT — scam terminal */}
        <div style={{
          flex: 1, opacity: fade(f, 12, 10),
          background: "rgba(232,38,26,0.04)", borderTop: `2px solid ${RED}`,
          padding: "28px 32px",
          fontFamily: "'JetBrains Mono','Courier New',monospace", fontSize: 18, lineHeight: 1.9,
        }}>
          <Label style={{ marginBottom: 18, color: RED, fontSize: 22 }}>Scam Detected</Label>

          {/* Typed lines (no tags) */}
          <div style={{ opacity: fade(f, 15, 5) }}>
            <Typed text="// AI agent initiates USDT transfer to unknown wallet" frame={f} start={15} color={DIM} speed={1.8} />
          </div>
          <div style={{ opacity: fade(f, 44, 5) }}>
            <Typed text='kairos.check("TScam9xK4j3...")' frame={f} start={44} color={WHITE} speed={2.0} />
          </div>

          {/* Tagged lines — fade in whole */}
          {[
            { d: 68,  c: WHITE, t: '→ honeypot_prob:  <R>0.9997</R>   freeze_fn: <R>true</R>' },
            { d: 92,  c: WHITE, t: '→ rug_probability: <R>0.9981</R>   verdict:  <R>BLACKLISTED</R>' },
            { d: 120, c: RED,   t: '✗ AGENT BLOCKED · 1,000 USDT protected' },
          ].map((l, i) => (
            <div key={i} style={{ opacity: fade(f, l.d, 8) }}>
              {l.t.split(/<R>|<\/R>/).map((p, j) =>
                j % 2 === 1
                  ? <span key={j} style={{ color: RED, fontWeight: 700 }}>{p}</span>
                  : <span key={j} style={{ color: l.c }}>{p}</span>
              )}
            </div>
          ))}

          {/* Additional detail */}
          <div style={{ opacity: fade(f, 150, 12), marginTop: 20, paddingTop: 18, borderTop: "1px solid rgba(255,255,255,0.07)" }}>
            <div style={{ fontSize: 15, color: DIM, lineHeight: 1.7 }}>
              <div>Contract age: <span style={{ color: RED }}>3 days</span></div>
              <div>Liquidity lock: <span style={{ color: RED }}>None</span></div>
              <div>Similar scam pattern: <span style={{ color: RED }}>ANUBIS-001 family</span></div>
            </div>
          </div>
        </div>

        {/* RIGHT — trust score with ring */}
        <div style={{
          flex: 1, opacity: fade(f, 55, 12),
          display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
          background: `${sc}09`, borderTop: `2px solid ${sc}`,
          padding: "28px 32px",
        }}>
          <Label style={{ marginBottom: 20, color: sc, fontSize: 22 }}>Trusted Counterparty</Label>

          {/* Ring + number overlay */}
          <div style={{ position: "relative", width: 300, height: 300, display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 16 }}>
            <ScoreRing score={ringScore} color={sc} size={300} />
            <div style={{ position: "absolute", textAlign: "center" }}>
              <div style={{
                fontSize: 108, fontWeight: 900, color: sc, lineHeight: 1, letterSpacing: "-0.05em",
                textShadow: `0 0 50px ${sc}55`,
                transform: `scale(${1 + 0.016 * Math.sin(f * 0.15)})`,
              }}>{score}</div>
              <div style={{ fontSize: 22, fontWeight: 800, color: sc, marginTop: 4, letterSpacing: "0.08em" }}>{verdict}</div>
            </div>
          </div>

          <div style={{ fontSize: 16, color: DIM, fontFamily: "monospace", marginBottom: 20 }}>TLyqz...PRJZY</div>

          {/* Score bars */}
          <div style={{ width: "100%", opacity: fade(f, 135, 10) }}>
            {[
              { l: "On-Chain Behavior", v: 94, w: "50%" },
              { l: "Anubis ML Engine",  v: 82, w: "30%" },
              { l: "Community",         v: 71, w: "20%" },
            ].map((b) => (
              <div key={b.l} style={{ marginBottom: 14 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 17, color: WHITE, marginBottom: 7 }}>
                  <span>{b.l} <span style={{ color: DIM }}>({b.w})</span></span>
                  <span style={{ fontWeight: 700 }}>{b.v}</span>
                </div>
                <div style={{ height: 7, background: "rgba(255,255,255,0.06)", borderRadius: 4 }}>
                  <div style={{ width: barW(f, 145, 192, b.v), height: "100%", background: sc, borderRadius: 4 }} />
                </div>
              </div>
            ))}
          </div>

          <div style={{ opacity: fade(f, 215, 10), marginTop: 16, fontSize: 22, color: GREEN, fontWeight: 800 }}>
            ✓ 500 USDT payment signed
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════
// SCENE 6 — FEATURES  48–56s  (240f)
// ═══════════════════════════════════════════════════════
const FeaturesScene = () => {
  const f = useCurrentFrame();
  const features = [
    { icon: "⚡", title: "Anubis ML Engine",  sub: "XGBoost · 50 on-chain features · Monte Carlo CI bands", color: AMBER },
    { icon: "🔴", title: "Sentinel Monitor",   sub: "Real-time threat alerts every 30s · auto-blacklist",    color: RED   },
    { icon: "📜", title: "5 Smart Contracts",  sub: "Oracle · Passport · Gate · Escrow · CommercialTrust",   color: BLUE  },
    { icon: "🛡",  title: "TrustPassport NFT", sub: "Soul-bound on-chain identity · TTPAS standard",          color: PURPLE},
    { icon: "💳", title: "x402 Protocol",      sub: "Pay-per-call API monetisation · USDT-TRC20",            color: GREEN },
    { icon: "🔗", title: "MCP Server",         sub: "Drop-in trust tool for Claude · GPT · any AI agent",    color: BLUE  },
  ];
  return (
    <AbsoluteFill style={{ ...base, background: BG, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "0 72px", paddingBottom: 40 }}>
      <TopLine />
      <Grid />
      <Particles />
      <Vignette />
      <Glow opacity={0.26} />

      <Label style={{ marginBottom: 18, opacity: fade(f, 0, 8) }}>Built Different</Label>

      <div style={{ opacity: fade(f, 8, 10), fontSize: 58, fontWeight: 900, textAlign: "center", lineHeight: 1.1, marginBottom: 40 }}>
        Everything trust needs.<br /><span style={{ color: RED }}>Nothing it doesn't.</span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14, width: "100%" }}>
        {features.map((feat, i) => (
          <div key={feat.title} style={{
            opacity: fade(f, 38 + i * 20, 12),
            transform: `translateY(${up(f, 38 + i * 20, 14)}px)`,
            display: "flex", alignItems: "flex-start", gap: 18,
            background: `${feat.color}09`, borderLeft: `3px solid ${feat.color}`,
            padding: "24px 26px",
          }}>
            <div style={{ fontSize: 32, lineHeight: 1, flexShrink: 0 }}>{feat.icon}</div>
            <div>
              <div style={{ fontSize: 22, fontWeight: 800, marginBottom: 8 }}>{feat.title}</div>
              <div style={{ fontSize: 16, color: DIM, lineHeight: 1.6 }}>{feat.sub}</div>
            </div>
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════
// SCENE 7 — CTA  56–60s  (120f)
// ═══════════════════════════════════════════════════════
const CTAScene = () => {
  const f = useCurrentFrame();
  const glow     = 0.55 + 0.38 * Math.sin(f * 0.13);
  const btnPulse = 1 + 0.024 * Math.sin(f * 0.2);
  const techStack = ["Anubis ML", "XGBoost", "Monte Carlo", "Nile Testnet", "x402", "TTPAS", "MCP"];
  return (
    <AbsoluteFill style={{ ...base, background: BG, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", paddingBottom: 40 }}>
      <TopLine />
      <Grid opacity={0.07} />
      <Particles />
      <Vignette />
      <Glow opacity={glow} size={1500} />
      <Corners opacity={fade(f, 6, 12)} />

      <Label style={{ marginBottom: 16, opacity: fade(f, 0, 8) }}>PennBlockathon 2026</Label>

      <div style={{ opacity: fade(f, 0, 10), transform: `scale(${slam(f, 0, 12)})`, display: "flex", marginBottom: 20 }}>
        <span style={{ fontSize: 110, fontWeight: 900, letterSpacing: "-0.05em", color: RED, lineHeight: 0.9 }}>KAI</span>
        <span style={{ fontSize: 110, fontWeight: 900, letterSpacing: "-0.05em", color: WHITE, lineHeight: 0.9 }}>ROS</span>
      </div>

      <div style={{ opacity: fade(f, 14, 10), transform: `translateY(${up(f, 14, 12)}px)`, fontSize: 56, fontWeight: 900, textAlign: "center", lineHeight: 1.1, maxWidth: 1000, marginBottom: 16 }}>
        The trust primitive<br /><span style={{ color: RED }}>the agent economy needs.</span>
      </div>

      <div style={{ opacity: fade(f, 30, 10), fontSize: 22, color: DIM, textAlign: "center", marginBottom: 32 }}>
        First trust infrastructure on TRON · Built in 48 hours
      </div>

      <div style={{
        opacity: fade(f, 46, 10),
        transform: `scale(${slam(f, 46, 10) * btnPulse})`,
        background: RED, color: WHITE,
        padding: "20px 56px", fontSize: 22, fontWeight: 800, borderRadius: 4, letterSpacing: "0.04em",
        marginBottom: 36,
        boxShadow: `0 0 40px ${RED}55`,
      }}>
        Try Kairos → kairos.tron
      </div>

      {/* Tech stack pills */}
      <div style={{ opacity: fade(f, 66, 12), display: "flex", gap: 10, flexWrap: "wrap", justifyContent: "center", maxWidth: 900 }}>
        {techStack.map((t, i) => (
          <div key={t} style={{
            opacity: fade(f, 70 + i * 5, 8),
            background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.12)",
            padding: "7px 18px", fontSize: 15, fontWeight: 600, borderRadius: 3, color: DIM,
          }}>{t}</div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════
// GLITCH OVERLAY
// ═══════════════════════════════════════════════════════
const CUT_FRAMES = [90, 390, 630, 990, 1440, 1680];
const GLITCH_DUR = 9;

const GlitchOverlay = () => {
  const f = useCurrentFrame();
  const T = CUT_FRAMES.find(t => f >= t - 2 && f < t + GLITCH_DUR - 2);
  if (T === undefined) return null;
  const tf        = f - (T - 2);
  const intensity = interpolate(tf, [0, 2, GLITCH_DUR], [0, 1, 0], clamp);
  const bar       = (seed) => Math.sin(f * seed) * 0.5 + 0.5;
  const shift     = intensity * 18;
  const bars = [
    { top: bar(127.3) * 88, h: 2 + bar(53.7) * 8,  col: `rgba(232,38,26,${0.7 * intensity})` },
    { top: bar(89.7)  * 88, h: 1 + bar(211.1) * 5, col: `rgba(255,255,255,${0.5 * intensity})` },
    { top: bar(213.1) * 88, h: 3 + bar(73.9) * 6,  col: `rgba(0,220,220,${0.45 * intensity})` },
    { top: bar(61.9)  * 88, h: 1 + bar(139.3) * 4, col: `rgba(255,255,255,${0.35 * intensity})` },
  ];
  return (
    <div style={{ position: "absolute", inset: 0, zIndex: 200, pointerEvents: "none", overflow: "hidden" }}>
      <div style={{ position: "absolute", inset: 0, background: `rgba(232,38,26,${0.18 * intensity})`, transform: `translateX(${-shift * 1.1}px) skewX(${intensity * 0.3}deg)`, mixBlendMode: "screen" }} />
      <div style={{ position: "absolute", inset: 0, background: `rgba(0,220,210,${0.14 * intensity})`, transform: `translateX(${shift * 0.85}px) skewX(${-intensity * 0.2}deg)`, mixBlendMode: "screen" }} />
      {bars.map((b, i) => (
        <div key={i} style={{ position: "absolute", top: `${b.top}%`, left: 0, right: 0, height: b.h, background: b.col, transform: `translateX(${(bar(b.top * 7.3) - 0.5) * shift * 3}px)` }} />
      ))}
      <div style={{ position: "absolute", inset: 0, background: "white", opacity: interpolate(tf, [1, 2, 4], [0, 0.35, 0], clamp) }} />
    </div>
  );
};

// ═══════════════════════════════════════════════════════
// ROOT — 1800 frames = 60s at 30fps
// ═══════════════════════════════════════════════════════
export const KairosDemo = () => (
  <AbsoluteFill style={{ background: BG }}>
    <Sequence from={0}    durationInFrames={90}><HookScene /></Sequence>
    <Sequence from={90}   durationInFrames={300}><StatShockScene /></Sequence>
    <Sequence from={390}  durationInFrames={240}><SolutionDropScene /></Sequence>
    <Sequence from={630}  durationInFrames={360}><HowItWorksScene /></Sequence>
    <Sequence from={990}  durationInFrames={450}><LiveDemoScene /></Sequence>
    <Sequence from={1440} durationInFrames={240}><FeaturesScene /></Sequence>
    <Sequence from={1680} durationInFrames={120}><CTAScene /></Sequence>

    {/* Global overlays — always on top of all scenes */}
    <FilmGrain />
    <LaserStreaks />
    <Ticker />
    <GlitchOverlay />
  </AbsoluteFill>
);
