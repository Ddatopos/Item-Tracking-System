export interface CameraFrame {
  frame_id: string;
  camera_id: string;
  room: string;
  captured_at: string;
  width: number;
  height: number;
  source_type: string;
  image: string;
}

export interface DetectionEvent {
  event_id: string;
  frame_id: string;
  camera_id: string;
  room: string;
  class_name: string;
  confidence: number;
  bbox: number[];
  captured_at: string;
  model_version: string;
  raw_image_path: string;
  annotated_image_path: string;
  first_seen?: string;
  last_seen?: string;
  observations?: number;
  inference_params?: Record<string, unknown>;
  image_url?: string | null;
  annotated_image_url?: string | null;
}

export type SystemStatus = "online" | "connecting" | "offline" | "error";
export type InferenceStatus = "idle" | "inferencing" | "stopped" | "error";
export type PreviewStatus = "loading" | "playing" | "stopped" | "error";

export interface CameraInfo {
  camera_id: string;
  room: string;
  status: SystemStatus;
  source_type: string;
  resolution: string;
}

export interface StreamInfo {
  preview_url: string;
  status: PreviewStatus;
}

export interface InferenceInfo {
  status: InferenceStatus;
  model_version: string;
  fps: number;
}

export interface HealthResponse {
  name?: string;
  version?: string;
  service_status?: string;
  state?: string;
  status: SystemStatus;
  cameras: CameraInfo[];
  stream: StreamInfo;
  inference: InferenceInfo;
}

export interface Settings {
  inference_fps: number;
  confidence_threshold: number;
  selected_classes: string[];
  dedup_seconds: number;
  input_size: number;
  category?: string;
  confidence?: number;
  inference_frequency?: number;
  model?: string;
  camera_id?: string;
}

export interface EventPage {
  events: DetectionEvent[];
  total: number;
  limit: number;
  offset: number;
}

export interface EventQuery {
  limit?: number;
  offset?: number;
  class_name?: string;
  category?: string;
  camera_id?: string;
  since?: string;
  until?: string;
}

export interface CameraListResponse {
  cameras: CameraOption[];
  active_camera_id: string;
  state: string;
}

export interface CameraOption {
  camera_id: string;
  room: string;
  source_type?: string;
  status?: SystemStatus;
  resolution?: string;
}

export interface ApiError {
  message: string;
  code?: string;
}

export type AppTab = "overview" | "history" | "settings";