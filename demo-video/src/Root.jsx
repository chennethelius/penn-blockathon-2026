import { Composition } from "remotion";
import { TronTrustDemo } from "./TronTrustDemo.jsx";

export const RemotionRoot = () => {
  return (
    <Composition
      id="TronTrustDemo"
      component={TronTrustDemo}
      durationInFrames={30 * 180} // 3 minutes at 30fps
      fps={30}
      width={1920}
      height={1080}
    />
  );
};
