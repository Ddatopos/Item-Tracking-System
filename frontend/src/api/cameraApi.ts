import http, { getApiErrorMessage } from "./http";
import type {
  CameraListResponse,
  EventPage,
  EventQuery,
  HealthResponse,
  Settings,
  DetectionEvent,
} from "./types";
import {
  mockHealth,
  mockEvents,
  setMockInferenceStatus,
  setMockPreviewStatus,
  MOCK_PREVIEW_URL,
} from "../mock/mockData";
import { getImageUrl } from "./itemApi";

const USE_MOCK = process.env.REACT_APP_USE_MOCK === "true";
let mockSettings: Settings = {
  inference_fps: 2,
  confidence_threshold: 0.25,
  selected_classes: [],
  dedup_seconds: 30,
  input_size: 640,
  model: "mock-detector",
  camera_id: "cam-001",
};

export async function getHealth(): Promise<HealthResponse> {
  if (USE_MOCK) return mockHealth();
  const { data } = await http.get<HealthResponse>("/api/health").catch((error: unknown) => {
    throw new Error(getApiErrorMessage(error));
  });
  return {
    ...data,
    stream: {
      ...data.stream,
      preview_url: getImageUrl(data.stream.preview_url),
    },
  };
}

export function getPreviewUrl(): string {
  if (USE_MOCK) return MOCK_PREVIEW_URL;
  return getImageUrl("/api/stream/preview");
}

export async function startPreview(): Promise<void> {
  if (USE_MOCK) {
    setMockPreviewStatus("playing");
    return;
  }
  await http.post("/api/stream/start").catch((error: unknown) => {
    throw new Error(getApiErrorMessage(error));
  });
}

export async function stopPreview(): Promise<void> {
  if (USE_MOCK) {
    setMockPreviewStatus("stopped");
    return;
  }
  await http.post("/api/stream/stop").catch((error: unknown) => {
    throw new Error(getApiErrorMessage(error));
  });
}

export async function startInference(): Promise<void> {
  if (USE_MOCK) {
    setMockInferenceStatus("inferencing");
    return;
  }
  await http.post("/api/inference/start").catch((error: unknown) => {
    throw new Error(getApiErrorMessage(error));
  });
}

export async function stopInference(): Promise<void> {
  if (USE_MOCK) {
    setMockInferenceStatus("stopped");
    return;
  }
  await http.post("/api/inference/stop").catch((error: unknown) => {
    throw new Error(getApiErrorMessage(error));
  });
}

export async function getSettings(): Promise<Settings> {
  if (USE_MOCK) return { ...mockSettings, selected_classes: [...mockSettings.selected_classes] };
  const { data } = await http.get<Settings>("/api/settings").catch((error: unknown) => {
    throw new Error(getApiErrorMessage(error));
  });
  return data;
}

export async function updateSettings(settings: Partial<Settings>): Promise<Settings> {
  if (USE_MOCK) {
    mockSettings = {
      ...mockSettings,
      ...settings,
      selected_classes: settings.selected_classes
        ? [...settings.selected_classes]
        : [...mockSettings.selected_classes],
    };
    return getSettings();
  }
  const { data } = await http.patch<Settings>("/api/settings", settings).catch((error: unknown) => {
    throw new Error(getApiErrorMessage(error));
  });
  return data;
}

export async function getEvents(params: EventQuery = {}): Promise<EventPage> {
  const query = { ...params, envelope: 1 };
  if (USE_MOCK) {
    const sinceTime = params.since ? new Date(params.since).getTime() : undefined;
    const untilTime = params.until ? new Date(params.until).getTime() : undefined;
    const list = mockEvents(60)
      .filter((event) => !params.class_name && !params.category
        ? true
        : event.class_name === (params.class_name ?? params.category))
      .filter((event) => !params.camera_id || event.camera_id === params.camera_id)
      .filter((event) => sinceTime === undefined
        || new Date(`${event.captured_at.replace(" ", "T")}Z`).getTime() >= sinceTime)
      .filter((event) => untilTime === undefined
        || new Date(`${event.captured_at.replace(" ", "T")}Z`).getTime() <= untilTime)
      .sort((a, b) => Date.parse(b.captured_at) - Date.parse(a.captured_at));
    const offset = params.offset ?? 0;
    const limit = params.limit ?? 20;
    return {
      events: list.slice(offset, offset + limit),
      total: list.length,
      offset,
      limit,
    };
  }
  const { data } = await http.get<EventPage | DetectionEvent[]>("/api/events", { params: query })
    .catch((error: unknown) => {
      throw new Error(getApiErrorMessage(error));
    });
  if (Array.isArray(data)) {
    return {
      events: data,
      total: data.length,
      limit: params.limit ?? data.length,
      offset: params.offset ?? 0,
    };
  }
  return data;
}

export async function getCameras(): Promise<CameraListResponse> {
  if (USE_MOCK) {
    const health = mockHealth();
    return {
      cameras: health.cameras,
      active_camera_id: health.cameras[0]?.camera_id ?? "",
      state: health.status,
    };
  }
  const { data } = await http.get<CameraListResponse>("/api/cameras").catch((error: unknown) => {
    throw new Error(getApiErrorMessage(error));
  });
  return data;
}

export interface RuntimeStatus {
  inference_state: string;
  [key: string]: unknown;
}

export async function getRuntimeStatus(): Promise<RuntimeStatus> {
  if (USE_MOCK) return { inference_state: mockHealth().inference.status };
  const { data } = await http.get<RuntimeStatus>("/api/status").catch((error: unknown) => {
    throw new Error(getApiErrorMessage(error));
  });
  return data;
}

export async function exportEvents(): Promise<Blob> {
  if (USE_MOCK) {
    const { events } = await getEvents({ limit: 100 });
    const columns = ["timestamp", "class_name", "location", "image_id", "event_id", "confidence"];
    const rows = events.map((event) => [
      event.captured_at,
      event.class_name,
      JSON.stringify(event.bbox),
      event.raw_image_path,
      event.event_id,
      event.confidence,
    ]);
    const csv = [columns, ...rows]
      .map((row) => row.map((value) => `"${String(value).replace(/"/g, '""')}"`).join(","))
      .join("\r\n");
    return new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8" });
  }
  const { data } = await http.get<Blob>("/api/events/export", { responseType: "blob" })
    .catch((error: unknown) => {
      throw new Error(getApiErrorMessage(error));
    });
  return data;
}