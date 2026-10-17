import http from "./http";
import type {
  HealthResponse,
  Settings,
  DetectionEvent,
} from "./types";
import { mockHealth, mockEvents, setMockPreviewStatus, MOCK_PREVIEW_URL } from "../mock/mockData";

const USE_MOCK = process.env.REACT_APP_USE_MOCK === "true" || true;

export async function getHealth(): Promise<HealthResponse> {
  if (USE_MOCK) return mockHealth();
  const { data } = await http.get<HealthResponse>("/api/health");
  return data;
}

export function getPreviewUrl(): string {
  if (USE_MOCK) return MOCK_PREVIEW_URL;
  return "/api/stream/preview";
}

export async function startPreview(): Promise<void> {
  if (USE_MOCK) {
    setMockPreviewStatus("playing");
    return;
  }
  await http.post("/api/stream/start");
}

export async function stopPreview(): Promise<void> {
  if (USE_MOCK) {
    setMockPreviewStatus("stopped");
    return;
  }
  await http.post("/api/stream/stop");
}

export async function startInference(): Promise<void> {
  if (USE_MOCK) return;
  await http.post("/api/inference/start");
}

export async function stopInference(): Promise<void> {
  if (USE_MOCK) return;
  await http.post("/api/inference/stop");
}

export async function getSettings(): Promise<Settings> {
  if (USE_MOCK) {
    return {
      category: "all",
      confidence: 0.5,
      model: "yolov8n",
      inference_frequency: 5,
      camera_id: "cam-001",
    };
  }
  const { data } = await http.get<Settings>("/api/settings");
  return data;
}

export async function updateSettings(settings: Partial<Settings>): Promise<Settings> {
  if (USE_MOCK) return { ...await getSettings(), ...settings };
  const { data } = await http.put<Settings>("/api/settings", settings);
  return data;
}

export async function getEvents(params?: {
  limit?: number;
  offset?: number;
  category?: string;
}): Promise<DetectionEvent[]> {
  if (USE_MOCK) return mockEvents(params?.limit ?? 5);
  const { data } = await http.get<DetectionEvent[]>("/api/events", { params });
  return data;
}