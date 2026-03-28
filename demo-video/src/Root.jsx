import { Composition } from "remotion";
import { KairosDemo } from "./TronTrustDemo.jsx";

export const RemotionRoot = () => {
  return (
    <Composition
      id="KairosDemo"
      component={KairosDemo}
      durationInFrames={1800} // 60s at 30fps
      fps={30}
      width={1920}
      height={1080}
    />
  );
};
