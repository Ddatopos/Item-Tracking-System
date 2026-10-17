import React from "react";
import type { SystemStatus, InferenceStatus, PreviewStatus, CameraInfo, InferenceInfo } from "../api/types";

interface StatusBarProps {
  systemStatus: SystemStatus;
  inference: InferenceInfo;
  previewStatus: PreviewStatus;
  cameras: CameraInfo[];
}

const statusLabel: Record<SystemStatus, string> = {
  online: "在线",
  connecting: "连接中",
  offline: "离线",
  error: "异常",
};

const inferenceLabel: Record<InferenceStatus, string> = {
  idle: "待机",
  inferencing: "推理中",
  stopped: "已停止",
  error: "异常",
};

const previewLabel: Record<PreviewStatus, string> = {
  loading: "加载中",
  playing: "播放中",
  stopped: "已停止",
  error: "异常",
};

function StatusBadge({ label, status }: { label: string; status: string }) {
  return (
    <span className={`status-badge status-badge-${status}`} aria-label={label}>
      <span className={`status-dot status-dot-${status}`} />
      {label}
    </span>
  );
}

function StatusBar({ systemStatus, inference, previewStatus, cameras }: StatusBarProps) {
  const activeCamera = cameras.find((c) => c.status !== "offline");

  return (
    <div className="status-bar" aria-label="系统状态" aria-live="polite">
      <div className="status-item">
        <span className="status-item-label">后端</span>
        <StatusBadge label={statusLabel[systemStatus]} status={systemStatus} />
      </div>
      <div className="status-item">
        <span className="status-item-label">摄像头</span>
        <StatusBadge
          label={activeCamera ? `${activeCamera.room} ${activeCamera.resolution}` : "无"}
          status={activeCamera ? activeCamera.status : "offline"}
        />
      </div>
      <div className="status-item">
        <span className="status-item-label">推理</span>
        <StatusBadge
          label={inferenceLabel[inference.status]}
          status={inference.status === "inferencing" ? "online" : inference.status}
        />
        {inference.status === "inferencing" && (
          <span className="status-item-extra">{inference.model_version} · {inference.fps} FPS</span>
        )}
      </div>
      <div className="status-item">
        <span className="status-item-label">预览</span>
        <StatusBadge label={previewLabel[previewStatus]} status={previewStatus === "playing" ? "online" : previewStatus} />
      </div>
    </div>
  );
}

export default StatusBar;