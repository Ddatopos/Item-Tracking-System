import React, { useEffect, useState } from "react";
import type { DetectionEvent } from "../api/types";
import { getEvents } from "../api/cameraApi";

function RecentEvents() {
  const [events, setEvents] = useState<DetectionEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadEvents = () => {
    setLoading(true);
    setError(null);
    getEvents({ limit: 5 })
      .then((list) => {
        setEvents(Array.isArray(list) ? list : []);
      })
      .catch((e: Error) => {
        setError("加载检测事件失败：" + (e.message || "网络错误"));
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadEvents();
  }, []);

  const confidenceColor = (v: number) => {
    if (v >= 0.8) return "#0f766e";
    if (v >= 0.6) return "#f59e0b";
    return "#ef4444";
  };

  return (
    <div className="recent-events" aria-label="最近检测事件" aria-live="polite">
      <div className="events-header">
        <h3 className="events-title">最近检测</h3>
        <button
          type="button"
          className="events-refresh-btn"
          onClick={loadEvents}
          disabled={loading}
          aria-label="刷新事件列表"
        >
          {loading ? "刷新中…" : "刷新"}
        </button>
      </div>

      {error && (
        <div className="events-error">{error}</div>
      )}

      {!error && !loading && events.length === 0 && (
        <div className="events-empty">
          <span>暂无检测记录</span>
          <span className="events-empty-hint">启动识别后，检测到物品会在此显示</span>
        </div>
      )}

      {!error && (
        <div className="events-list">
          {events.map((evt) => (
            <div key={evt.event_id} className="event-card">
              <div className="event-card-main">
                <div className="event-card-header">
                  <span className="event-class">{evt.class_name}</span>
                  <span
                    className="event-confidence"
                    style={{ color: confidenceColor(evt.confidence) }}
                  >
                    {Math.round(evt.confidence * 100)}%
                  </span>
                </div>
                <div className="event-card-meta">
                  <span>{evt.room}</span>
                  <span>{evt.captured_at}</span>
                  <span>{evt.model_version}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default RecentEvents;