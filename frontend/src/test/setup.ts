import "@testing-library/jest-dom/vitest";

// integration tests talk to a real API server (uvicorn backend.api.main:app --port 8000)
(window as any).__API_BASE__ = process.env.VITE_API_BASE || "http://127.0.0.1:8000/api";
// jsdom has no layout engine: give ResponsiveContainer / virtualisers a size so charts and tables render
class RO { observe() {} unobserve() {} disconnect() {} }
(globalThis as any).ResizeObserver = (globalThis as any).ResizeObserver || RO;
Object.defineProperty(HTMLElement.prototype, "offsetHeight", { configurable: true, value: 600 });
Object.defineProperty(HTMLElement.prototype, "offsetWidth", { configurable: true, value: 900 });
Element.prototype.getBoundingClientRect = function () { return { width: 900, height: 600, top: 0, left: 0, right: 900, bottom: 600, x: 0, y: 0, toJSON() {} } as any; };
