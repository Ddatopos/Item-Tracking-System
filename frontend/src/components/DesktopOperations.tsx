import React, { useEffect, useState } from "react";
import { getDesktopApi } from "../api/desktopApi";
import type { DesktopOperationResult } from "../api/types";

function DesktopOperations() {
  const [available, setAvailable] = useState(false);
  const [pending, setPending] = useState(false);
  const [feedback, setFeedback] = useState<DesktopOperationResult | null>(null);

  useEffect(() => {
    const updateAvailability = () => setAvailable(getDesktopApi() !== null);
    updateAvailability();
    window.addEventListener("pywebviewready", updateAvailability);
    return () => window.removeEventListener("pywebviewready", updateAvailability);
  }, []);

  const runOperation = async (
    operation: () => Promise<DesktopOperationResult>
  ): Promise<DesktopOperationResult | null> => {
    if (pending) return null;
    setPending(true);
    setFeedback(null);
    try {
      const result = await operation();
      setFeedback(result);
      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : "桌面操作失败";
      const result = { ok: false, message };
      setFeedback(result);
      return result;
    } finally {
      setPending(false);
    }
  };

  const chooseDataDirectory = async () => {
    const api = getDesktopApi();
    if (!api) return;
    const selection = await runOperation(() => api.select_data_dir());
    const path = selection?.data?.path;
    if (selection?.ok && typeof path === "string" && path) {
      await runOperation(() => api.set_data_dir(path));
    }
  };

  const exportLogs = async () => {
    const api = getDesktopApi();
    if (!api) return;
    const selection = await runOperation(() => api.select_export_destination());
    const destination = selection?.data?.path;
    if (selection?.ok && typeof destination === "string" && destination) {
      await runOperation(() => api.export_logs(destination));
    }
  };

  const shutdownDesktop = async () => {
    const desktopApi = getDesktopApi();
    if (!desktopApi) return;
    const result = await runOperation(() => desktopApi.shutdown());
    if (result?.ok) {
      window.close();
    }
  };

  if (!available) return null;

  const api = getDesktopApi();
  if (!api) return null;

  return (
    <section className="settings-card desktop-operations" aria-labelledby="desktop-operations-title">
      <header className="settings-header">
        <div>
          <h2 className="panel-title" id="desktop-operations-title">桌面操作</h2>
          <p className="panel-desc">
            数据目录变更在下次启动时生效；预览和识别控制仍由后端 API 管理。
          </p>
        </div>
      </header>
      <div className="desktop-operations-actions">
        <button type="button" className="control-btn" onClick={chooseDataDirectory} disabled={pending}>
          选择数据目录
        </button>
        <button
          type="button"
          className="control-btn"
          onClick={() => void runOperation(() => api.open_data_dir())}
          disabled={pending}
        >
          打开数据目录
        </button>
        <button type="button" className="control-btn" onClick={exportLogs} disabled={pending}>
          导出日志
        </button>
        <button
          type="button"
          className="control-btn control-btn-start"
          onClick={() => void runOperation(() => api.start())}
          disabled={pending}
        >
          启动后台
        </button>
        <button
          type="button"
          className="control-btn control-btn-stop"
          onClick={() => void runOperation(() => api.stop())}
          disabled={pending}
        >
          停止后台
        </button>
        <button
          type="button"
          className="control-btn control-btn-stop"
          onClick={() => void shutdownDesktop()}
          disabled={pending}
        >
          安全退出
        </button>
      </div>
      {feedback && (
        <p
          className={feedback.ok ? "settings-notice" : "events-error"}
          role={feedback.ok ? "status" : "alert"}
        >
          {feedback.message}
        </p>
      )}
    </section>
  );
}

export default DesktopOperations;
