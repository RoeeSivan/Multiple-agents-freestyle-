import React from "react";
import { Composition } from "remotion";
import { TOTAL_FRAMES, Walkthrough } from "./Walkthrough";

export const RemotionRoot: React.FC = () => (
  <Composition
    id="Walkthrough"
    component={Walkthrough}
    durationInFrames={TOTAL_FRAMES}
    fps={30}
    width={1080}
    height={1920}
  />
);
