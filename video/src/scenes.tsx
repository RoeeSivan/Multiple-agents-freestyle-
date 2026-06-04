import React from "react";
import {
  AbsoluteFill,
  Img,
  Loop,
  OffthreadVideo,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Backdrop, Bubble, Caption, Phone, StepPill, Typing, theme } from "./ui";

const fadeIn = (frame: number, dur = 15) =>
  interpolate(frame, [0, dur], [0, 1], { extrapolateRight: "clamp" });

/** 1 · Title card. */
export const IntroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame, fps, config: { damping: 200 }, durationInFrames: 30 });
  return (
    <AbsoluteFill>
      <Backdrop />
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        <div style={{ textAlign: "center", transform: `scale(${interpolate(p, [0, 1], [0.9, 1])})`, opacity: p }}>
          <div
            style={{
              fontFamily: theme.font,
              fontSize: 92,
              fontWeight: 800,
              color: theme.text,
              letterSpacing: -2,
            }}
          >
            Text → 3D
          </div>
          <div
            style={{
              fontFamily: theme.font,
              fontSize: 44,
              fontWeight: 500,
              color: theme.amberSoft,
              marginTop: 16,
            }}
          >
            an AI builds it live, over SMS
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

/** 2 · User texts a request. */
export const RequestScene: React.FC = () => (
  <AbsoluteFill>
    <Backdrop />
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", paddingTop: 40 }}>
      <Phone>
        <Bubble side="user" delay={10}>
          a wooden chair 🪑
        </Bubble>
        <Typing delay={45} />
      </Phone>
    </AbsoluteFill>
    <Caption text="You text a 3D scene" sub="just a plain description — to a phone number" />
  </AbsoluteFill>
);

/** 3 · The multi-agent pipeline lights up. */
export const PipelineScene: React.FC = () => {
  const frame = useCurrentFrame();
  const steps = ["Router", "Planner", "Web reference", "Builder", "Vision critic"];
  return (
    <AbsoluteFill>
      <Backdrop glow={theme.teal} />
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        <div style={{ opacity: fadeIn(frame), textAlign: "center" }}>
          <div
            style={{
              fontFamily: theme.font,
              fontSize: 40,
              fontWeight: 600,
              color: theme.textDim,
              marginBottom: 50,
            }}
          >
            PydanticAI multi-agent pipeline
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 28, alignItems: "center" }}>
            {steps.map((s, i) => (
              <StepPill key={s} label={`${i + 1} · ${s}`} active={frame > 20 + i * 14} />
            ))}
          </div>
        </div>
      </AbsoluteFill>
      <Caption text="A team of agents takes over" sub="plan · ground in real photos · model · critique" />
    </AbsoluteFill>
  );
};

type Stage = { src: string; label: string };

export const CHAIR_STAGES: Stage[] = [
  { src: "build_1.png", label: "Seat" },
  { src: "build_2.png", label: "+ Legs" },
  { src: "build_3.png", label: "+ Backrest" },
  { src: "build_4.png", label: "Wood finish" },
];

export const TV_STAGES: Stage[] = [
  { src: "tv_build_1.png", label: "Screen panel" },
  { src: "tv_build_2.png", label: "+ Display" },
  { src: "tv_build_3.png", label: "+ Stand" },
  { src: "tv_build_4.png", label: "Finish" },
];

/** 4 · The model is built up part by part (fixed camera). */
export const ConstructionScene: React.FC<{
  stages?: Stage[];
  title?: string;
  sub?: string;
}> = ({ stages = CHAIR_STAGES, title = "The agent models it, part by part", sub = "real geometry in a live Blender — nothing imported" }) => {
  const frame = useCurrentFrame();
  const each = 60;
  const idx = Math.min(stages.length - 1, Math.floor(frame / each));
  return (
    <AbsoluteFill>
      <Backdrop />
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", paddingBottom: 120 }}>
        <div
          style={{
            width: 940,
            height: 705,
            borderRadius: 40,
            overflow: "hidden",
            border: "1px solid rgba(255,255,255,0.10)",
            boxShadow: "0 30px 90px rgba(0,0,0,0.5)",
            position: "relative",
            background: "#2e3340",
          }}
        >
          {stages.map((s, i) => {
            const local = frame - i * each;
            const op = i === 0 ? 1 : interpolate(local, [-12, 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            return (
              <Img
                key={s.src}
                src={staticFile(s.src)}
                style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover", opacity: i <= idx ? op : 0 }}
              />
            );
          })}
          <div
            style={{
              position: "absolute",
              bottom: 26,
              left: 30,
              fontFamily: theme.font,
              fontSize: 40,
              fontWeight: 700,
              color: theme.bg0,
              background: theme.amber,
              padding: "10px 28px",
              borderRadius: 999,
            }}
          >
            {stages[idx].label}
          </div>
        </div>
      </AbsoluteFill>
      <Caption text={title} sub={sub} />
    </AbsoluteFill>
  );
};

const CRITIC_NOTES = [
  "Curve the backrest slightly",
  "Warmer, polished-oak finish",
  "Seat must rest on the legs — no floating parts",
];

/** 5 · Vision critic reviews the render and sends fixes back. */
export const CriticScene: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill>
      <Backdrop glow={theme.teal} />
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        <div style={{ display: "flex", gap: 40, alignItems: "center", opacity: fadeIn(frame) }}>
          <Img
            src={staticFile("build_4.png")}
            style={{ width: 430, height: 430, objectFit: "cover", borderRadius: 28, border: "1px solid rgba(255,255,255,0.12)" }}
          />
          <div style={{ display: "flex", flexDirection: "column", gap: 26, width: 560 }}>
            {CRITIC_NOTES.map((n, i) => {
              const local = frame - 20 - i * 22;
              const p = interpolate(local, [0, 14], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
              return (
                <div
                  key={n}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 20,
                    opacity: p,
                    transform: `translateX(${interpolate(p, [0, 1], [30, 0])}px)`,
                  }}
                >
                  <div
                    style={{
                      width: 52,
                      height: 52,
                      borderRadius: 999,
                      background: theme.teal,
                      color: theme.bg0,
                      fontSize: 34,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                    }}
                  >
                    ✓
                  </div>
                  <div style={{ fontFamily: theme.font, fontSize: 38, color: theme.text, fontWeight: 500 }}>
                    {n}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </AbsoluteFill>
      <Caption text="A vision agent critiques every render" sub="it sees 5 angles, then sends precise fixes back" />
    </AbsoluteFill>
  );
};

/** 6 · 360° turntable of the finished, game-ready model. */
export const TurntableScene: React.FC<{
  src?: string;
  title?: string;
  sub?: string;
}> = ({ src = "chair.mp4", title = "A finished, game-ready model", sub = "360° preview + a real .glb you can drop into a game" }) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill>
      <Backdrop />
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", paddingBottom: 120 }}>
        <div
          style={{
            width: 940,
            height: 705,
            borderRadius: 40,
            overflow: "hidden",
            border: "1px solid rgba(255,255,255,0.10)",
            boxShadow: "0 30px 90px rgba(0,0,0,0.5)",
            opacity: fadeIn(frame),
            position: "relative",
          }}
        >
          <Loop durationInFrames={60}>
            <OffthreadVideo src={staticFile(src)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
          </Loop>
        </div>
      </AbsoluteFill>
      <Caption text={title} sub={sub} />
    </AbsoluteFill>
  );
};

/** 7 · The agent texts back a link. */
export const LinkScene: React.FC = () => (
  <AbsoluteFill>
    <Backdrop />
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", paddingTop: 40 }}>
      <Phone>
        <Bubble side="user" delay={0}>
          a wooden chair 🪑
        </Bubble>
        <Bubble side="agent" delay={14}>
          Done! Your wooden chair is ready 🎉
        </Bubble>
        <Bubble side="agent" delay={40}>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ fontSize: 30, color: theme.amberSoft, fontWeight: 600 }}>View your 3D model ↗</div>
            <div style={{ fontSize: 28, color: theme.textDim }}>scene.studio/v/8f2a1c</div>
          </div>
        </Bubble>
      </Phone>
    </AbsoluteFill>
    <Caption text="You get an SMS link back" sub="reply to keep editing — by text" />
  </AbsoluteFill>
);

/** 8 · Open the link: viewer page with image + download. */
export const ViewerScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pulse = 1 + 0.04 * Math.sin((frame / fps) * Math.PI * 2);
  return (
    <AbsoluteFill>
      <Backdrop glow={theme.teal} />
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        <div
          style={{
            width: 980,
            borderRadius: 28,
            overflow: "hidden",
            backgroundColor: "#0f1626",
            border: "1px solid rgba(255,255,255,0.12)",
            boxShadow: "0 40px 110px rgba(0,0,0,0.6)",
            opacity: fadeIn(frame),
            transform: `translateY(${interpolate(fadeIn(frame, 18), [0, 1], [40, 0])}px)`,
          }}
        >
          {/* browser chrome */}
          <div style={{ height: 70, background: "#0a0f1c", display: "flex", alignItems: "center", padding: "0 28px", gap: 14 }}>
            {["#ff5f57", "#febc2e", "#28c840"].map((c) => (
              <div key={c} style={{ width: 22, height: 22, borderRadius: 999, background: c }} />
            ))}
            <div
              style={{
                marginLeft: 22,
                flex: 1,
                height: 40,
                borderRadius: 12,
                background: "#1a2336",
                color: theme.textDim,
                fontFamily: theme.font,
                fontSize: 26,
                display: "flex",
                alignItems: "center",
                padding: "0 22px",
              }}
            >
              🔒 scene.studio/v/8f2a1c
            </div>
          </div>
          <Img src={staticFile("hero.png")} style={{ width: "100%", height: 660, objectFit: "cover", background: "#2e3340" }} />
          <div style={{ padding: "34px 40px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div>
              <div style={{ fontFamily: theme.font, fontSize: 44, fontWeight: 700, color: theme.text }}>Wooden chair</div>
              <div style={{ fontFamily: theme.font, fontSize: 30, color: theme.textDim, marginTop: 6 }}>built by AI · 208 KB · glTF</div>
            </div>
            <div
              style={{
                fontFamily: theme.font,
                fontSize: 36,
                fontWeight: 700,
                color: theme.bg0,
                background: theme.amber,
                padding: "20px 40px",
                borderRadius: 18,
                transform: `scale(${pulse})`,
              }}
            >
              ⬇ Download .glb
            </div>
          </div>
        </div>
      </AbsoluteFill>
      <Caption text="Open it → view and download" sub="the game-ready .glb, straight from a text" />
    </AbsoluteFill>
  );
};

/** TV bridge: "now text it something else". */
export const TvRequestScene: React.FC = () => (
  <AbsoluteFill>
    <Backdrop glow={theme.teal} />
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", paddingTop: 40 }}>
      <Phone>
        <Bubble side="user" delay={10}>
          now a flat-screen television 📺
        </Bubble>
        <Typing delay={45} />
      </Phone>
    </AbsoluteFill>
    <Caption text="Text it anything else" sub="same pipeline — a brand-new object" />
  </AbsoluteFill>
);

/** 9 · Outro. */
export const OutroScene: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill>
      <Backdrop />
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        <div style={{ textAlign: "center", opacity: fadeIn(frame, 20) }}>
          <div style={{ fontFamily: theme.font, fontSize: 80, fontWeight: 800, color: theme.text, letterSpacing: -2 }}>
            Text → 3D, over SMS
          </div>
          <div style={{ fontFamily: theme.font, fontSize: 36, color: theme.textDim, marginTop: 24 }}>
            PydanticAI · Saperly · Blender
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
