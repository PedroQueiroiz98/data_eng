import "@testing-library/jest-dom/vitest";

// React Flow (e outros) esperam ResizeObserver, ausente no jsdom.
if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  } as unknown as typeof ResizeObserver;
}

// jsdom não implementa scrollIntoView (usado pelo LogTerminal para auto-scroll).
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
