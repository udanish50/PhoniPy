import { analyzeSamples } from "./engine.mjs";
self.onmessage = ({ data }) => {
  try {
    const result = analyzeSamples(data.samples, data.config, {
      ...data.options,
      progress: (value) => self.postMessage({ type: "progress", value }),
    });
    self.postMessage({ type: "result", result });
  } catch (error) {
    self.postMessage({
      type: "error",
      message: error.message || "Analysis could not be completed.",
    });
  }
};
