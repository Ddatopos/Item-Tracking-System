import React, { ChangeEvent, useCallback, useEffect, useRef, useState } from "react";
import { exportEvents, getCameras, getEvents } from "../api/cameraApi";
import { getImageUrl, getItemCategories } from "../api/itemApi";
import type { CameraOption, DetectionEvent } from "../api/types";

const PAGE_SIZE = 20;

function formatLocalDateTime(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function EventHistory() {
  const [events, setEvents] = useState<DetectionEvent[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [cameras, setCameras] = useState<CameraOption[]>([]);
  const [category, setCategory] = useState("");
  const [cameraId, setCameraId] = useState("");
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<DetectionEvent | null>(null);
  const [showAnnotation, setShowAnnotation] = useState(true);
  const [focusedTimeFilter, setFocusedTimeFilter] = useState<"since" | "until" | null>(null);
  const [currentTimePlaceholder] = useState(() => formatLocalDateTime(new Date()));
  const requestSequence = useRef(0);

  useEffect(() => {
    getItemCategories()
      .then(setCategories)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "类别加载失败"));
    getCameras()
      .then((result) => setCameras(result.cameras))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "摄像头列表加载失败"));
  }, []);

  const loadEvents = useCallback(async () => {
    const requestId = ++requestSequence.current;
    setLoading(true);
    setError(null);
    try {
      const result = await getEvents({
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        class_name: category || undefined,
        camera_id: cameraId || undefined,
        since: since ? new Date(since).toISOString() : undefined,
        until: until ? new Date(until).toISOString() : undefined,
      });
      if (requestId === requestSequence.current) {
        setEvents(result.events);
        setTotal(result.total);
      }
    } catch (e) {
      if (requestId === requestSequence.current) {
        setError(e instanceof Error ? e.message : "加载历史事件失败");
      }
    } finally {
      if (requestId === requestSequence.current) setLoading(false);
    }
  }, [cameraId, category, page, since, until]);

  useEffect(() => {
    void loadEvents();
  }, [loadEvents]);

  const changeFilter = (
    setter: (value: string) => void,
    event: ChangeEvent<HTMLSelectElement | HTMLInputElement>
  ) => {
    setter(event.target.value);
    setPage(0);
  };

  const handleExport = async () => {
    if (exporting) return;
    setExporting(true);
    setError(null);
    try {
      const blob = await exportEvents();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "events.csv";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "导出事件失败");
    } finally {
      setExporting(false);
    }
  };

  const imageUrl = selectedEvent
    ? (showAnnotation
      ? selectedEvent.annotated_image_url
      : selectedEvent.image_url) ||
      `/api/events/${encodeURIComponent(selectedEvent.event_id)}/${showAnnotation ? "annotation" : "image"}`
    : "";
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <section className="event-history">
      <div className="history-heading">
        <div>
          <h2 className="panel-title">检测历史</h2>
          <p className="panel-desc">查看检测事件、置信度和标注图片；同类别连续观测可能合并为一个事件。</p>
        </div>
        <button
          type="button"
          className="events-refresh-btn"
          onClick={() => void handleExport()}
          disabled={exporting}
        >
          {exporting ? "导出中…" : "导出 CSV"}
        </button>
      </div>

      <div className="history-filters">
        <label>
          类别
          <select className="select" value={category} onChange={(event) => changeFilter(setCategory, event)}>
            <option value="">全部类别</option>
            {categories.map((item) => <option value={item} key={item}>{item}</option>)}
          </select>
        </label>
        <label>
          摄像头
          <select className="select" value={cameraId} onChange={(event) => changeFilter(setCameraId, event)}>
            <option value="">全部摄像头</option>
            {cameras.map((camera) => (
              <option value={camera.camera_id} key={camera.camera_id}>
                {camera.room || camera.camera_id} · {camera.camera_id}
              </option>
            ))}
          </select>
        </label>
        <label>
          开始时间
          <div className="datetime-input-wrapper">
            <input
              className={`settings-input${!since && focusedTimeFilter !== "since" ? " datetime-input-empty" : ""}`}
              type="datetime-local"
              value={since}
              onChange={(event) => changeFilter(setSince, event)}
              onFocus={() => setFocusedTimeFilter("since")}
              onBlur={() => setFocusedTimeFilter(null)}
            />
            {!since && focusedTimeFilter !== "since" && (
              <span className="datetime-input-placeholder" aria-hidden="true">
                {currentTimePlaceholder}
              </span>
            )}
          </div>
        </label>
        <label>
          结束时间
          <div className="datetime-input-wrapper">
            <input
              className={`settings-input${!until && focusedTimeFilter !== "until" ? " datetime-input-empty" : ""}`}
              type="datetime-local"
              value={until}
              onChange={(event) => changeFilter(setUntil, event)}
              onFocus={() => setFocusedTimeFilter("until")}
              onBlur={() => setFocusedTimeFilter(null)}
            />
            {!until && focusedTimeFilter !== "until" && (
              <span className="datetime-input-placeholder" aria-hidden="true">
                {currentTimePlaceholder}
              </span>
            )}
          </div>
        </label>
      </div>

      {error && <div className="events-error" role="alert">{error}</div>}
      {loading ? (
        <div className="history-state" aria-live="polite">
          <div className="preview-loading-spinner" />
          <span>正在加载事件…</span>
        </div>
      ) : events.length === 0 ? (
        <div className="events-empty">
          <span>没有符合条件的检测事件</span>
          <span className="events-empty-hint">调整筛选条件，或在识别运行后刷新。</span>
        </div>
      ) : (
        <>
          <div className="history-event-list">
            {events.map((event) => (
              <article className="history-event-card" key={event.event_id}>
                <button
                  type="button"
                  className="history-event-image-button"
                  onClick={() => {
                    setSelectedEvent(event);
                    setShowAnnotation(true);
                  }}
                  aria-label={`查看 ${event.class_name} 的检测图片`}
                >
                  <EventImage event={event} />
                </button>
                <div className="history-event-details">
                  <div className="event-card-header">
                    <strong className="event-class">{event.class_name}</strong>
                    <span className="event-confidence">{Math.round(event.confidence * 100)}%</span>
                  </div>
                  <p>{event.room} · {event.camera_id}</p>
                  <p>{event.captured_at}</p>
                  <p>区域：{event.bbox.map((coordinate) => Math.round(coordinate)).join(", ")}</p>
                  <p>模型：{event.model_version}</p>
                  {typeof event.observations === "number" && <p>合并观测：{event.observations} 次</p>}
                </div>
              </article>
            ))}
          </div>
          <div className="history-pagination">
            <span>共 {total} 条 · 第 {page + 1} / {pageCount} 页</span>
            <div>
              <button
                type="button"
                className="control-btn"
                onClick={() => setPage((current) => Math.max(0, current - 1))}
                disabled={page === 0 || loading}
              >
                上一页
              </button>
              <button
                type="button"
                className="control-btn"
                onClick={() => setPage((current) => Math.min(pageCount - 1, current + 1))}
                disabled={page >= pageCount - 1 || loading}
              >
                下一页
              </button>
            </div>
          </div>
        </>
      )}

      {selectedEvent && (
        <div
          className="image-viewer-backdrop"
          role="presentation"
          onClick={(event) => {
            if (event.target === event.currentTarget) setSelectedEvent(null);
          }}
        >
          <section className="image-viewer" role="dialog" aria-modal="true" aria-labelledby="image-viewer-title">
            <header>
              <h3 id="image-viewer-title">{selectedEvent.class_name} · 检测图片</h3>
              <div>
                <button
                  type="button"
                  className="events-refresh-btn"
                  onClick={() => setShowAnnotation((current) => !current)}
                >
                  {showAnnotation ? "查看原图" : "查看标注图"}
                </button>
                <button type="button" className="events-refresh-btn" onClick={() => setSelectedEvent(null)}>
                  关闭
                </button>
              </div>
            </header>
            <EventImage
              event={selectedEvent}
              src={getImageUrl(imageUrl)}
              key={`${selectedEvent.event_id}-${showAnnotation}`}
            />
          </section>
        </div>
      )}
    </section>
  );
}

function EventImage({ event, src }: { event: DetectionEvent; src?: string }) {
  const [failed, setFailed] = useState(false);
  const imageSource = src ?? event.annotated_image_url ?? event.image_url;
  if (!imageSource || failed) {
    return <div className="event-image-fallback">图片无法加载</div>;
  }
  return (
    <img
      src={getImageUrl(imageSource)}
      alt={`${event.class_name} ${src ? "查看图片" : "标注图"}`}
      onError={() => setFailed(true)}
    />
  );
}

export default EventHistory;
