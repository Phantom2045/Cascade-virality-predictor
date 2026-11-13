import "@testing-library/jest-dom";

// Polyfill ResizeObserver for Recharts ResponsiveContainer in jsdom tests
if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = class ResizeObserver {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  };
}
