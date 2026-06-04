import React from "react";
import { AbsoluteFill, Audio, Series, staticFile } from "remotion";
import {
  ConstructionScene,
  CriticScene,
  IntroScene,
  LinkScene,
  OutroScene,
  PipelineScene,
  RequestScene,
  TurntableScene,
  TvRequestScene,
  TV_STAGES,
  ViewerScene,
} from "./scenes";

/** Each scene: a rendered node + its length in frames (30 fps). */
export const SCENES: { node: React.ReactNode; dur: number }[] = [
  { node: <IntroScene />, dur: 60 },
  { node: <RequestScene />, dur: 120 },
  { node: <PipelineScene />, dur: 120 },
  { node: <ConstructionScene />, dur: 240 },
  { node: <CriticScene />, dur: 120 },
  { node: <TurntableScene />, dur: 150 },
  { node: <LinkScene />, dur: 120 },
  { node: <ViewerScene />, dur: 150 },
  // --- second object: a television, same pipeline ---
  { node: <TvRequestScene />, dur: 90 },
  {
    node: (
      <ConstructionScene
        stages={TV_STAGES}
        title="And it builds anything"
        sub="a flat-screen TV — bezel, display, stand"
      />
    ),
    dur: 240,
  },
  {
    node: (
      <TurntableScene
        src="tv.mp4"
        title="Another game-ready model"
        sub="from one text message"
      />
    ),
    dur: 120,
  },
  { node: <OutroScene />, dur: 60 },
];

export const TOTAL_FRAMES = SCENES.reduce((n, s) => n + s.dur, 0);

export const Walkthrough: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: "#0b0f1a" }}>
    <Audio src={staticFile("music.mp3")} volume={0.32} />
    <Series>
      {SCENES.map(({ node, dur }, i) => (
        <Series.Sequence key={i} durationInFrames={dur}>
          {node}
        </Series.Sequence>
      ))}
    </Series>
  </AbsoluteFill>
);
