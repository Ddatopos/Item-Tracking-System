import type { DesktopApi } from "./types";

declare global {
  interface Window {
    pywebview?: {
      api?: DesktopApi;
    };
  }
}

export function getDesktopApi(): DesktopApi | null {
  return window.pywebview?.api ?? null;
}
