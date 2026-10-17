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
  status: SystemStatus;
  cameras: CameraInfo[];
  stream: StreamInfo;
  inference: InferenceInfo;
}

export interface Settings {
  category: string;
  confidence: number;
  model: string;
  inference_frequency: number;
  camera_id: string;
}

export interface ApiError {
  message: string;
  code?: string;
}

export type AppTab = "overview" | "history" | "settings";