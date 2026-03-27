import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Sequence,
} from "remotion";

// ── Colors ──
const BG = "#0a0212";
const RED = "#e8261a";
const GREEN = "#22c55e";
const BLUE = "#3b82f6";
const AMBER = "#facc15";
const DIM = "#888";
const WHITE = "#f0f0f0";

// ── Helpers ──
const fadeIn = (frame, start, dur = 15) =>
  interpolate(frame, [start, start + dur], [0, 1], { extrapolateRight: "clamp" });

const slideUp = (frame, start, dur = 20) =>
  interpolate(frame, [start, start + dur], [40, 0], { extrapolateRight: "clamp" });

// ── Shared styles ──
const centered = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  fontFamily: "'Inter', 'SF Pro Display', system-ui, sans-serif",
  color: WHITE,
};

const codeBlock = {
  background: "rgba(255,255,255,0.05)",
  border: `1px solid rgba(255,255,255,0.1)`,
  borderRadius: 12,
  padding: "24px 32px",
  fontFamily: "'JetBrains Mono', 'Courier New', monospace",
  fontSize: 22,
  lineHeight: 1.6,
  textAlign: "left",
  maxWidth: 900,
};

// ═══════════════════════════════════════════
// SCENE 1: Title (0s – 10s = frames 0–300)
// ═══════════════════════════════════════════
const TitleScene = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ ...centered, background: BG }}>
      {/* Glow */}
      <div
        style={{
          position: "absolute",
          top: "30%",
          left: "50%",
          transform: "translate(-50%,-50%)",
          width: 800,
          height: 400,
          background: `radial-gradient(ellipse, rgba(232,38,26,0.15) 0%, transparent 70%)`,
          opacity: fadeIn(frame, 0, 30),
        }}
      />
      <div
        style={{
          opacity: fadeIn(frame, 15),
          transform: `translateY(${slideUp(frame, 15)}px)`,
          fontSize: 18,
          fontWeight: 600,
          letterSpacing: "0.15em",
          color: RED,
          marginBottom: 20,
          textTransform: "uppercase",
        }}
      >
        PennBlockathon 2026 · AI & Agentic Commerce
      </div>
      <div
        style={{
          opacity: fadeIn(frame, 30),
          transform: `translateY(${slideUp(frame, 30)}px)`,
          fontSize: 90,
          fontWeight: 900,
          letterSpacing: "-0.03em",
          lineHeight: 1.05,
          textAlign: "center",
        }}
      >
        Tron<span style={{ color: RED }}>Trust</span>
      </div>
      <div
        style={{
          opacity: fadeIn(frame, 50),
          transform: `translateY(${slideUp(frame, 50)}px)`,
          fontSize: 28,
          color: DIM,
          marginTop: 20,
          textAlign: "center",
        }}
      >
        The trust layer for the Tron agent economy.
      </div>
      <div
        style={{
          opacity: fadeIn(frame, 80),
          marginTop: 40,
          display: "flex",
          gap: 16,
        }}
      >
        {["5 Contracts on Nile", "50 ML Features", "6 MCP Tools", "Real-time Sentinel"].map(
          (t, i) => (
            <div
              key={t}
              style={{
                opacity: fadeIn(frame, 90 + i * 12),
                background: "rgba(232,38,26,0.1)",
                border: "1px solid rgba(232,38,26,0.3)",
                padding: "8px 18px",
                fontSize: 16,
                fontWeight: 600,
                borderRadius: 4,
              }}
            >
              {t}
            </div>
          )
        )}
      </div>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════
// SCENE 2: The Problem (10s – 25s)
// ═══════════════════════════════════════════
const ProblemScene = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ ...centered, background: BG, padding: 80 }}>
      <div
        style={{
          opacity: fadeIn(frame, 0),
          fontSize: 18,
          color: RED,
          fontWeight: 700,
          letterSpacing: "0.1em",
          textTransform: "uppercase",
          marginBottom: 16,
        }}
      >
        The Problem
      </div>
      <div
        style={{
          opacity: fadeIn(frame, 15),
          transform: `translateY(${slideUp(frame, 15)}px)`,
          fontSize: 52,
          fontWeight: 900,
          textAlign: "center",
          lineHeight: 1.2,
          maxWidth: 1000,
        }}
      >
        AI agents transact on Tron
        <br />
        <span style={{ color: RED }}>with zero trust infrastructure.</span>
      </div>
      <div
        style={{
          opacity: fadeIn(frame, 60),
          marginTop: 50,
          display: "flex",
          gap: 30,
        }}
      >
        {[
          { num: "50%+", label: "of all USDT on Tron" },
          { num: "0", label: "trust systems on Tron" },
          { num: "$B+", label: "at risk from scams" },
        ].map((s, i) => (
          <div
            key={s.label}
            style={{
              opacity: fadeIn(frame, 70 + i * 20),
              textAlign: "center",
              padding: "24px 40px",
              background: "rgba(255,255,255,0.03)",
              border: "1px solid rgba(255,255,255,0.08)",
              borderRadius: 8,
            }}
          >
            <div style={{ fontSize: 48, fontWeight: 900, color: i === 1 ? RED : WHITE }}>
              {s.num}
            </div>
            <div style={{ fontSize: 16, color: DIM, marginTop: 8 }}>{s.label}</div>
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════
// SCENE 3: How It Works (25s – 55s)
// ═══════════════════════════════════════════
const HowItWorksScene = () => {
  const frame = useCurrentFrame();
  const steps = [
    { icon: "🤖", title: "Agent queries trust", desc: "MCP tool: get_agent_trust(address)", delay: 30 },
    { icon: "📊", title: "Anubis scores with ML", desc: "50 features → XGBoost → rug probability", delay: 90 },
    { icon: "⛓️", title: "Score pushed on-chain", desc: "TronTrustOracle.updateScore() on Nile", delay: 150 },
    { icon: "✅", title: "Agent acts on verdict", desc: "TRUSTED → proceed · AVOID → refuse", delay: 210 },
  ];
  return (
    <AbsoluteFill style={{ ...centered, background: BG, padding: 80 }}>
      <div style={{ opacity: fadeIn(frame, 0), fontSize: 18, color: RED, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 16 }}>
        How It Works
      </div>
      <div style={{ opacity: fadeIn(frame, 10), fontSize: 48, fontWeight: 900, marginBottom: 50 }}>
        From wallet to verdict in seconds.
      </div>
      <div style={{ display: "flex", gap: 24 }}>
        {steps.map((s, i) => (
          <div
            key={s.title}
            style={{
              opacity: fadeIn(frame, s.delay),
              transform: `translateY(${slideUp(frame, s.delay)}px)`,
              background: "rgba(255,255,255,0.03)",
              border: "1px solid rgba(255,255,255,0.08)",
              borderTop: `2px solid ${RED}`,
              padding: "28px 24px",
              width: 220,
              borderRadius: 8,
            }}
          >
            <div style={{ fontSize: 36, marginBottom: 12 }}>{s.icon}</div>
            <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>{s.title}</div>
            <div style={{ fontSize: 14, color: DIM, lineHeight: 1.5 }}>{s.desc}</div>
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════
// SCENE 4: Live Demo — Scam Refused (55s – 80s)
// ═══════════════════════════════════════════
const ScamRefusedScene = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ ...centered, background: BG, padding: 80 }}>
      <div style={{ opacity: fadeIn(frame, 0), fontSize: 18, color: RED, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 16 }}>
        Live Demo
      </div>
      <div style={{ opacity: fadeIn(frame, 10), fontSize: 44, fontWeight: 900, marginBottom: 40 }}>
        Agent refuses a scam token
      </div>
      <div style={{ ...codeBlock, opacity: fadeIn(frame, 30) }}>
        <div style={{ color: DIM }}>// Agent asked to swap 500 USDT into unknown token</div>
        <div style={{ opacity: fadeIn(frame, 50) }}>
          <span style={{ color: BLUE }}>get_token_forensics</span>
          {"("}<span style={{ color: AMBER }}>"TScamToken..."</span>{")"}
        </div>
        <br />
        <div style={{ opacity: fadeIn(frame, 90) }}>
          {"→ rug_probability: "}<span style={{ color: RED, fontWeight: 700 }}>0.9997</span>
        </div>
        <div style={{ opacity: fadeIn(frame, 110) }}>
          {"→ verdict: "}<span style={{ color: RED, fontWeight: 700 }}>AVOID</span>
        </div>
        <div style={{ opacity: fadeIn(frame, 130) }}>
          {"→ freeze_function: "}<span style={{ color: RED }}>true</span>
        </div>
        <br />
        <div style={{ opacity: fadeIn(frame, 160), color: GREEN, fontWeight: 700, fontSize: 26 }}>
          AGENT REFUSES THE SWAP
        </div>
        <div style={{ opacity: fadeIn(frame, 180), color: GREEN }}>
          Saved user from potential loss of 500 USDT
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════
// SCENE 5: Trust Score (80s – 105s)
// ═══════════════════════════════════════════
const TrustScoreScene = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const score = Math.round(
    interpolate(frame, [30, 90], [0, 88], { extrapolateRight: "clamp" })
  );
  const color = score >= 80 ? GREEN : score >= 60 ? BLUE : score >= 40 ? AMBER : RED;
  return (
    <AbsoluteFill style={{ ...centered, background: BG, padding: 80 }}>
      <div style={{ opacity: fadeIn(frame, 0), fontSize: 18, color: RED, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 16 }}>
        Trust Check
      </div>
      <div style={{ opacity: fadeIn(frame, 10), fontSize: 44, fontWeight: 900, marginBottom: 40 }}>
        Agent trusts a good counterparty
      </div>
      <div style={{ display: "flex", gap: 60, alignItems: "center", opacity: fadeIn(frame, 25) }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 120, fontWeight: 900, color, lineHeight: 1 }}>{score}</div>
          <div style={{ fontSize: 24, fontWeight: 700, color, marginTop: 8 }}>
            {score >= 80 ? "TRUSTED" : score >= 60 ? "REPUTABLE" : "ANALYZING..."}
          </div>
          <div style={{ fontSize: 14, color: DIM, marginTop: 8 }}>TLyqzVGLV1srkB7d...PRJZY</div>
        </div>
        <div style={{ opacity: fadeIn(frame, 100) }}>
          <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 16 }}>Breakdown</div>
          {[
            { label: "Behavioral", val: 97, w: "50%" },
            { label: "Token Health", val: 82, w: "30%" },
            { label: "Community", val: 50, w: "20%" },
          ].map((b) => (
            <div key={b.label} style={{ marginBottom: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 14, color: DIM, marginBottom: 4 }}>
                <span>{b.label} ({b.w})</span>
                <span style={{ color: WHITE, fontWeight: 700 }}>{b.val}</span>
              </div>
              <div style={{ width: 300, height: 6, background: "rgba(255,255,255,0.05)", borderRadius: 3 }}>
                <div
                  style={{
                    width: `${interpolate(frame, [100, 140], [0, b.val], { extrapolateRight: "clamp" })}%`,
                    height: "100%",
                    background: color,
                    borderRadius: 3,
                  }}
                />
              </div>
            </div>
          ))}
          <div style={{ opacity: fadeIn(frame, 160), marginTop: 20, fontSize: 20, color: GREEN, fontWeight: 700 }}>
            ✓ Agent proceeds with 200 USDT payment
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════
// SCENE 6: Contracts (105s – 130s)
// ═══════════════════════════════════════════
const ContractsScene = () => {
  const frame = useCurrentFrame();
  const contracts = [
    { name: "TronTrustOracle", desc: "On-chain trust scores", addr: "TJtw1YMJ..." },
    { name: "TrustPassport", desc: "Soul-bound NFT identity", addr: "TNpENknR..." },
    { name: "TrustGateContract", desc: "DeFi pool access gating", addr: "TT7tFQCG..." },
    { name: "CommercialTrust", desc: "B2B payment reputation", addr: "TQJrxetk..." },
    { name: "TrustEscrow", desc: "Trust-gated fund release", addr: "TLnjvkwm..." },
  ];
  return (
    <AbsoluteFill style={{ ...centered, background: BG, padding: 80 }}>
      <div style={{ opacity: fadeIn(frame, 0), fontSize: 18, color: RED, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 16 }}>
        On-Chain · Nile Testnet
      </div>
      <div style={{ opacity: fadeIn(frame, 10), fontSize: 48, fontWeight: 900, marginBottom: 40 }}>
        5 deployed smart contracts
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 12, width: 800 }}>
        {contracts.map((c, i) => (
          <div
            key={c.name}
            style={{
              opacity: fadeIn(frame, 30 + i * 25),
              transform: `translateX(${interpolate(frame, [30 + i * 25, 45 + i * 25], [-40, 0], { extrapolateRight: "clamp" })}px)`,
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "18px 24px",
              background: "rgba(255,255,255,0.03)",
              border: "1px solid rgba(255,255,255,0.08)",
              borderLeft: `3px solid ${RED}`,
              borderRadius: 6,
            }}
          >
            <div>
              <div style={{ fontSize: 18, fontWeight: 700 }}>{c.name}</div>
              <div style={{ fontSize: 14, color: DIM }}>{c.desc}</div>
            </div>
            <div style={{ fontSize: 14, color: DIM, fontFamily: "monospace" }}>{c.addr}</div>
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════
// SCENE 7: CTA / Close (130s – 180s)
// ═══════════════════════════════════════════
const CTAScene = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ ...centered, background: BG }}>
      <div
        style={{
          position: "absolute",
          top: "50%",
          left: "50%",
          transform: "translate(-50%,-50%)",
          width: 900,
          height: 500,
          background: `radial-gradient(ellipse, rgba(232,38,26,0.12) 0%, transparent 65%)`,
        }}
      />
      <div style={{ opacity: fadeIn(frame, 0), transform: `translateY(${slideUp(frame, 0)}px)`, fontSize: 72, fontWeight: 900, textAlign: "center", lineHeight: 1.1 }}>
        Trust is the primitive
        <br />
        <span style={{ color: RED }}>the agent economy needs.</span>
      </div>
      <div style={{ opacity: fadeIn(frame, 40), fontSize: 24, color: DIM, marginTop: 24 }}>
        First trust infrastructure on Tron. Built at PennBlockathon 2026.
      </div>
      <div style={{ opacity: fadeIn(frame, 80), display: "flex", gap: 20, marginTop: 40 }}>
        <div style={{ background: RED, color: WHITE, padding: "14px 32px", fontSize: 18, fontWeight: 700, borderRadius: 6 }}>
          github.com/chennethelius/penn-blockathon-2026
        </div>
      </div>
      <div style={{ opacity: fadeIn(frame, 120), marginTop: 60, display: "flex", gap: 40 }}>
        {["XGBoost ML", "5 Smart Contracts", "6 MCP Tools", "Trust-gated Escrow", "Real-time Sentinel"].map(
          (t) => (
            <div key={t} style={{ fontSize: 14, color: DIM, fontWeight: 600 }}>
              {t}
            </div>
          )
        )}
      </div>
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════
// MAIN COMPOSITION
// ═══════════════════════════════════════════
export const TronTrustDemo = () => {
  return (
    <AbsoluteFill style={{ background: BG }}>
      {/* Scene 1: Title — 0s to 10s (frames 0–300) */}
      <Sequence from={0} durationInFrames={300}>
        <TitleScene />
      </Sequence>

      {/* Scene 2: Problem — 10s to 25s (frames 300–750) */}
      <Sequence from={300} durationInFrames={450}>
        <ProblemScene />
      </Sequence>

      {/* Scene 3: How It Works — 25s to 55s (frames 750–1650) */}
      <Sequence from={750} durationInFrames={900}>
        <HowItWorksScene />
      </Sequence>

      {/* Scene 4: Scam Refused — 55s to 80s (frames 1650–2400) */}
      <Sequence from={1650} durationInFrames={750}>
        <ScamRefusedScene />
      </Sequence>

      {/* Scene 5: Trust Score — 80s to 105s (frames 2400–3150) */}
      <Sequence from={2400} durationInFrames={750}>
        <TrustScoreScene />
      </Sequence>

      {/* Scene 6: Contracts — 105s to 130s (frames 3150–3900) */}
      <Sequence from={3150} durationInFrames={750}>
        <ContractsScene />
      </Sequence>

      {/* Scene 7: CTA — 130s to 180s (frames 3900–5400) */}
      <Sequence from={3900} durationInFrames={1500}>
        <CTAScene />
      </Sequence>
    </AbsoluteFill>
  );
};
