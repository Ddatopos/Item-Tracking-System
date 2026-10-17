import React, { useRef, useEffect, useState, useCallback } from "react";
import { createMockCamera, MockCameraRef } from "../mock/mockCamera";
import type { PreviewStatus } from "../api/types";

interface MJPEGPreviewProps {
  previewUrl: string;
  status: PreviewStatus;
}

function MJPEGPreview({ previewUrl, status: externalStatus }: MJPEGPreviewProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const mockRef = useRef<MockCameraRef | null>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const [imgError, setImgError] = useState(false);
  const isMock = previewUrl.startsWith("mock://");

  const cleanup = useCallback(() => {
    if (mockRef.current) {
      mockRef.current.stop();
      mockRef.current = null;
    }
  }, []);

  const initMock = useCallback(() => {
    if (!canvasRef.current) return;
    cleanup();
    const canvas = canvasRef.current;
    canvas.width = 1920;
    canvas.height = 1080;
    mockRef.current = createMockCamera(canvas, 15);
  }, [cleanup]);

  useEffect(() => {
    if (isMock && externalStatus === "playing") {
      initMock();
    }
    return cleanup;
  }, [isMock, externalStatus, initMock, cleanup]);

  const handleImgError = () => {
    setImgError(true);
  };

  const handleRetry = () => {
    setImgError(false);
    if (imgRef.current && !isMock) {
      imgRef.current.src = previewUrl + "?_t=" + Date.now();
    }
  };

  const renderContent = () => {
    if (externalStatus === "loading") {
      return (
        <div className="preview-placeholder">
          <div className="preview-loading-spinner" />
          <span>正在连接摄像头…</span>
        </div>
      );
    }

    if (externalStatus === "stopped") {
      return (
        <div className="preview-placeholder">
          <span className="preview-placeholder-icon">⏸</span>
          <span>预览已停止</span>
          <span className="preview-placeholder-hint">点击"启动预览"开始</span>
        </div>
      );
    }

    if (externalStatus === "error" || (imgError && !isMock)) {
      return (
        <div className="preview-placeholder preview-placeholder-error">
          <span className="preview-placeholder-icon">⚠</span>
          <span>视频流加载失败</span>
          <span className="preview-placeholder-hint">摄像头离线或后端未运行</span>
          <button type="button" className="retry-btn" onClick={handleRetry}>
            重试
          </button>
        </div>
      );
    }

    if (isMock) {
      return (
        <canvas
          ref={canvasRef}
          className="preview-canvas"
          style={{ width: "100%", aspectRatio: "1920 / 1080", display: "block" }}
        />
      );
    }

    return (
      <img
        ref={imgRef}
        src={previewUrl}
        alt="摄像头实时预览"
        className="preview-img"
        onError={handleImgError}
      />
    );
  };

  const isError = externalStatus === "error" || (imgError && !isMock);
  const isActive = externalStatus === "playing" && !imgError;

  return (
    <div className={`preview-container ${isError ? "preview-container-error" : ""} ${isActive ? "preview-container-active" : ""}`}>
      <div className="preview-header">
        <span className="preview-label">实时预览</span>
        <span className={`preview-indicator preview-indicator-${externalStatus}`}>
          {externalStatus === "playing" ? "● 实时" : externalStatus === "loading" ? "◌ 连接中" : externalStatus === "stopped" ? "■ 已停止" : "▲ 异常"}
        </span>
        {isMock && externalStatus === "playing" && (
          <span className="preview-mock-tag">MOCK</span>
        )}
      </div>
      <div className="preview-frame">
        {renderContent()}
      </div>
    </div>
  );
}

export default MJPEGPreview;