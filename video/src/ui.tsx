import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export const theme = {
  bg0: "#0b0f1a",
  bg1: "#141b2d",
  amber: "#e0a458",
  amberSoft: "#f0c896",
  teal: "#4fd1c5",
  text: "#f5f7fb",
  textDim: "#9aa6c0",
  bubbleUser: "#2f6bff",
  bubbleAgent: "#262e44",
  font: '-apple-system, "SF Pro Display", "Segoe UI", Roboto, system-ui, sans-serif',
};

/** Full-screen dark gradient backdrop with a soft amber glow. */
export const Backdrop: React.FC<{ glow?: string }> = ({ glow = theme.amber }) => (
  <AbsoluteFill
    style={{
      background: `radial-gradient(120% 80% at 50% 8%, ${theme.bg1} 0%, ${theme.bg0} 60%)`,
    }}
  >
    <AbsoluteFill
      style={{
        background: `radial-gradient(40% 26% at 50% 42%, ${glow}22 0%, transparent 70%)`,
      }}
    />
  </AbsoluteFill>
);

/** Lower-third narration caption. Slides up + fades in. */
export const Caption: React.FC<{ text: string; sub?: string }> = ({ text, sub }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = spring({ frame, fps, config: { damping: 200 }, durationInFrames: 18 });
  const y = interpolate(enter, [0, 1], [40, 0]);
  return (
    <div
      style={{
        position: "absolute",
        bottom: 150,
        left: 0,
        right: 0,
        textAlign: "center",
        opacity: enter,
        transform: `translateY(${y}px)`,
        padding: "0 90px",
      }}
    >
      <div
        style={{
          fontFamily: theme.font,
          fontSize: 56,
          fontWeight: 700,
          color: theme.text,
          letterSpacing: -1,
          lineHeight: 1.15,
          textShadow: "0 2px 24px rgba(0,0,0,0.6)",
        }}
      >
        {text}
      </div>
      {sub ? (
        <div
          style={{
            fontFamily: theme.font,
            fontSize: 34,
            fontWeight: 500,
            color: theme.textDim,
            marginTop: 14,
          }}
        >
          {sub}
        </div>
      ) : null}
    </div>
  );
};

/** A small step pill (e.g. "1 · Plan"). */
export const StepPill: React.FC<{ label: string; active?: boolean }> = ({ label, active }) => (
  <div
    style={{
      fontFamily: theme.font,
      fontSize: 30,
      fontWeight: 600,
      padding: "12px 26px",
      borderRadius: 999,
      color: active ? theme.bg0 : theme.textDim,
      background: active ? theme.amber : "rgba(255,255,255,0.06)",
      border: `1px solid ${active ? theme.amber : "rgba(255,255,255,0.12)"}`,
      transition: "all 0.2s",
    }}
  >
    {label}
  </div>
);

/** An iMessage-style phone shell. */
export const Phone: React.FC<{ children: React.ReactNode; title?: string }> = ({
  children,
  title = "AI 3D Studio",
}) => (
  <div
    style={{
      width: 760,
      height: 1480,
      borderRadius: 72,
      background: "#05070d",
      border: "12px solid #1b2233",
      boxShadow: "0 40px 120px rgba(0,0,0,0.6)",
      overflow: "hidden",
      position: "relative",
    }}
  >
    {/* notch */}
    <div
      style={{
        position: "absolute",
        top: 22,
        left: "50%",
        transform: "translateX(-50%)",
        width: 220,
        height: 34,
        borderRadius: 20,
        background: "#05070d",
        zIndex: 3,
      }}
    />
    {/* header */}
    <div
      style={{
        height: 150,
        backgroundColor: "#0d1322",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "flex-end",
        paddingBottom: 18,
        borderBottom: "1px solid rgba(255,255,255,0.06)",
      }}
    >
      <div
        style={{
          width: 70,
          height: 70,
          borderRadius: 999,
          background: `linear-gradient(135deg, ${theme.amber}, ${theme.teal})`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 38,
        }}
      >
        🪑
      </div>
      <div
        style={{
          fontFamily: theme.font,
          color: theme.text,
          fontSize: 30,
          fontWeight: 600,
          marginTop: 8,
        }}
      >
        {title}
      </div>
    </div>
    {/* thread */}
    <div style={{ padding: "28px 28px", display: "flex", flexDirection: "column", gap: 22 }}>
      {children}
    </div>
  </div>
);

/** One chat bubble that springs in. `delay` in frames. */
export const Bubble: React.FC<{
  side: "user" | "agent";
  delay: number;
  children: React.ReactNode;
}> = ({ side, delay, children }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: frame - delay, fps, config: { damping: 14, stiffness: 120 } });
  const isUser = side === "user";
  return (
    <div
      style={{
        alignSelf: isUser ? "flex-end" : "flex-start",
        maxWidth: "78%",
        transform: `scale(${p}) translateY(${interpolate(p, [0, 1], [20, 0])}px)`,
        opacity: p,
        transformOrigin: isUser ? "bottom right" : "bottom left",
      }}
    >
      <div
        style={{
          fontFamily: theme.font,
          fontSize: 36,
          lineHeight: 1.35,
          color: theme.text,
          background: isUser ? theme.bubbleUser : theme.bubbleAgent,
          padding: "22px 30px",
          borderRadius: 36,
          borderBottomRightRadius: isUser ? 10 : 36,
          borderBottomLeftRadius: isUser ? 36 : 10,
        }}
      >
        {children}
      </div>
    </div>
  );
};

/** Animated three-dot typing indicator inside an agent bubble. */
export const Typing: React.FC<{ delay: number }> = ({ delay }) => {
  const frame = useCurrentFrame();
  const dot = (i: number) => {
    const t = (frame - delay) % 30;
    const o = interpolate((t + i * 8) % 30, [0, 8, 16, 30], [0.3, 1, 0.3, 0.3]);
    return (
      <div
        key={i}
        style={{ width: 16, height: 16, borderRadius: 999, background: theme.textDim, opacity: o }}
      />
    );
  };
  return (
    <Bubble side="agent" delay={delay}>
      <div style={{ display: "flex", gap: 10, padding: "4px 6px" }}>{[0, 1, 2].map(dot)}</div>
    </Bubble>
  );
};
