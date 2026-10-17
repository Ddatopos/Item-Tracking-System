import React, { useEffect, useState, useCallback } from "react";
import MJPEGPreview from "./MJPEGPreview";
import StatusBar from "./StatusBar";
import RecentEvents from "./RecentEvents";
import { getHealth, getPreviewUrl } from "../api/cameraApi";
import type {
  HealthResponse,
  SystemStatus,
  PreviewStatus,
} from "../api/types";

function OverviewPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [systemStatus, setSystemStatus] = useState<SystemStatus>("connecting");
  const [previewStatus, setPreviewStatus] = useState<PreviewStatus>("loading");

  const fetchHealth = useCallback(() => {
    getHealth()
      .then((data) => {
        setHealth(data);
        setSystemStatus(data.status);
        setPreviewStatus(data.stream.status);
        setError(null);
      })
      .catch((e: Error) => {
        setError("无法连接后端：" + (e.message || "网络错误"));
        setSystemStatus("offline");
        setPreviewStatus("error");
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 5000);
    return () => clearInterval(interval);
  }, [fetchHealth]);

  const displayHealth = health ?? {
    status: systemStatus,
    cameras: [{ camera_id: "cam-001", room: "客厅", status: systemStatus, source_type: "UVC", resolution: "1920x1080" }],
    stream: { preview_url: getPreviewUrl(), status: previewStatus },
    inference: { status: "idle" as const, model_version: "yolov8n.pt", fps: 5 },
  };

  return (
    <div className="overview-page">
      {loading && (
        <div className="overview-loading" aria-live="polite">
          <div className="preview-loading-spinner" />
          <span>正在连接系统…</span>
        </div>
      )}
      {error && (
        <div className="overview-error" aria-live="assertive">
          <div className="overview-error-content">
            <span className="error-icon">⚠</span>
            <div>
              <p className="overview-error-title">系统连接失败</p>
              <p className="overview-error-detail">{error}</p>
            </div>
            <button type="button" className="retry-btn" onClick={fetchHealth}>
              重试连接
            </button>
          </div>
        </div>
      )}
      {!loading && (
        <>
          <StatusBar
            systemStatus={displayHealth.status}
            inference={displayHealth.inference}
            previewStatus={previewStatus}
            cameras={displayHealth.cameras}
          />
          <MJPEGPreview
            previewUrl={displayHealth.stream.preview_url}
            status={previewStatus}
          />
          <RecentEvents />
        </>
      )}
    </div>
  );
}

export default OverviewPage;