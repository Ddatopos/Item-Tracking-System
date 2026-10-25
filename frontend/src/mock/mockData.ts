import type {
  HealthResponse,
  DetectionEvent,
  SystemStatus,
  InferenceStatus,
  PreviewStatus,
} from "../api/types";

export const MOCK_PREVIEW_URL = "mock://camera/preview";
let inferenceState: InferenceStatus = "idle";

function randomId(): string {
  return Math.random().toString(36).substring(2, 10);
}

let healthToggles = 0;
let previewState: PreviewStatus = "playing";

export function setMockPreviewStatus(status: PreviewStatus) {
  previewState = status;
}

export function setMockInferenceStatus(status: InferenceStatus) {
  inferenceState = status;
}

export function mockHealth(): HealthResponse {
  healthToggles++;
  const statuses: SystemStatus[] = ["online", "connecting", "online", "online", "online"];

  const status = statuses[healthToggles % statuses.length];
  const previewStatus = previewState;

  return {
    status: status,
    cameras: [
      {
        camera_id: "cam-001",
        room: "客厅",
        status: status,
        source_type: "UVC",
        resolution: "1920x1080",
      },
    ],
    stream: {
      preview_url: MOCK_PREVIEW_URL,
      status: previewStatus,
    },
    inference: {
      status: inferenceState,
      model_version: "yolov8n.pt",
      fps: 5,
    },
  };
}

const CLASS_NAMES = ["backpack", "phone", "keyboard", "cup", "chair", "laptop", "book", "bottle"];
const ROOMS = ["客厅", "厨房", "卧室", "书房"];
const MODEL_VERSIONS = ["yolov8n.pt", "yolov8s.pt"];

export function mockEvents(limit = 5): DetectionEvent[] {
  const events: DetectionEvent[] = [];
  for (let i = 0; i < limit; i++) {
    const minutesAgo = i * 3 + Math.floor(Math.random() * 5);
    const date = new Date(Date.now() - minutesAgo * 60000);
    const capturedAt = date.toISOString().replace("T", " ").substring(0, 19);

    events.push({
      event_id: `evt-${randomId()}`,
      frame_id: `frm-${randomId()}`,
      camera_id: "cam-001",
      room: ROOMS[i % ROOMS.length],
      class_name: CLASS_NAMES[i % CLASS_NAMES.length],
      confidence: 0.65 + Math.random() * 0.3,
      bbox: [100, 80, 300, 280],
      captured_at: capturedAt,
      model_version: MODEL_VERSIONS[i % MODEL_VERSIONS.length],
      raw_image_path: `/images/mock/capture_${i + 1}.jpg`,
      annotated_image_path: `/images/mock/annotated_${i + 1}.jpg`,
      image_url: `data:image/svg+xml,${encodeURIComponent(
        `<svg xmlns="http://www.w3.org/2000/svg" width="480" height="270"><rect width="100%" height="100%" fill="#e2e8f0"/><rect x="140" y="55" width="180" height="150" fill="#14b8a6" fill-opacity=".18" stroke="#0f766e" stroke-width="4"/><text x="20" y="35" font-size="18" fill="#334155">${CLASS_NAMES[i % CLASS_NAMES.length]} · mock</text></svg>`
      )}`,
      annotated_image_url: `data:image/svg+xml,${encodeURIComponent(
        `<svg xmlns="http://www.w3.org/2000/svg" width="480" height="270"><rect width="100%" height="100%" fill="#e2e8f0"/><rect x="140" y="55" width="180" height="150" fill="#14b8a6" fill-opacity=".18" stroke="#0f766e" stroke-width="4"/><text x="20" y="35" font-size="18" fill="#334155">${CLASS_NAMES[i % CLASS_NAMES.length]} · annotation</text></svg>`
      )}`,
    });
  }
  return events;
}