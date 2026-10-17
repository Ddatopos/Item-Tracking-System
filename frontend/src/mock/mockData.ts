import type {
  HealthResponse,
  DetectionEvent,
  SystemStatus,
  InferenceStatus,
  PreviewStatus,
} from "../api/types";

export const MOCK_PREVIEW_URL = "mock://camera/preview";

function randomId(): string {
  return Math.random().toString(36).substring(2, 10);
}

let healthToggles = 0;

export function mockHealth(): HealthResponse {
  healthToggles++;
  const statuses: SystemStatus[] = ["online", "connecting", "online", "online", "online"];
  const infStatuses: InferenceStatus[] = ["idle", "inferencing", "inferencing", "idle", "stopped"];
  const previewStatuses: PreviewStatus[] = ["playing", "playing", "playing", "stopped", "error"];

  const status = statuses[healthToggles % statuses.length];
  const inferenceStatus = infStatuses[healthToggles % infStatuses.length];
  const previewStatus = previewStatuses[healthToggles % previewStatuses.length];

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
      preview_url: "/api/stream/preview",
      status: previewStatus,
    },
    inference: {
      status: inferenceStatus,
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
      bbox: [100 + Math.random() * 400, 80 + Math.random() * 300, 200, 200],
      captured_at: capturedAt,
      model_version: MODEL_VERSIONS[i % MODEL_VERSIONS.length],
      raw_image_path: `/images/mock/capture_${i + 1}.jpg`,
      annotated_image_path: `/images/mock/annotated_${i + 1}.jpg`,
    });
  }
  return events;
}