import React, { useState, useEffect } from "react";
import { getItemCategories, getItemLastAppearance, getImageUrl } from "../api/itemApi";
import "../App.css";

function ItemTracking() {
  const [categories, setCategories] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [categoriesLoading, setCategoriesLoading] = useState(true);
  const [imageLoading, setImageLoading] = useState(false);
  const [imageZoom, setImageZoom] = useState(1);

  const MIN_ZOOM = 0.5;
  const MAX_ZOOM = 2;
  const ZOOM_STEP = 0.25;

  useEffect(() => {
    setImageZoom(1);
  }, [result?.image_path]);

  useEffect(() => {
    getItemCategories()
      .then((list) => {
        setCategories(Array.isArray(list) ? list : []);
        if (!selectedCategory && list?.length) setSelectedCategory(list[0]);
      })
      .catch((e) => {
        setError("加载物品列表失败：" + (e.message || "网络错误"));
      })
      .finally(() => setCategoriesLoading(false));
  }, []);

  const handleSearch = (isRetry = false) => {
    if (!selectedCategory?.trim()) return;
    setError(null);
    setResult(null);
    setLoading(true);
    getItemLastAppearance(selectedCategory.trim(), { cacheBust: isRetry })
      .then((data) => {
        if (!data || !data.image_path) {
          setError(
            isRetry
              ? "仍无法加载，请检查网络后重试"
              : "未返回有效结果，请重试"
          );
          return;
        }
        setResult({
          category: data.category ?? selectedCategory,
          image_path: data.image_path,
          processed_image_path: data.processed_image_path ?? null,
          timestamp: data.timestamp ?? "",
        });
        setImageLoading(true);
      })
      .catch((e) => {
        setError(
          isRetry ? "仍无法加载，请检查网络后重试" : (e.message || "查询失败")
        );
      })
      .finally(() => setLoading(false));
  };

  // 只显示带框的图：有 processed 用 processed，否则用原图
  const displayPath = result?.processed_image_path || result?.image_path;
  const imageUrl = displayPath ? getImageUrl(displayPath) : "";

  const handleRetry = () => {
    setError(null);
    handleSearch(true);
  };

  const zoomIn = () => {
    setImageZoom((z) => Math.min(MAX_ZOOM, z + ZOOM_STEP));
  };
  const zoomOut = () => {
    setImageZoom((z) => Math.max(MIN_ZOOM, z - ZOOM_STEP));
  };
  const zoomReset = () => {
    setImageZoom(1);
  };

  return (
    <div className="app">
      <header className="app-header">
        <div className="logo">家庭寻物系统</div>
        <div className="subtitle">按物品类别查询最后出现位置</div>
      </header>

      <main className="app-main">
        <section className="search-panel" aria-label="物品查询">
          <h2 className="panel-title">物品查询</h2>
          <p className="panel-desc">
            该物品在家庭场景中最后一次出现的照片
          </p>

          <div className="form-group">
            <label htmlFor="item-select">物品类别</label>
            <select
              id="item-select"
              className="select"
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              disabled={categoriesLoading}
              aria-busy={categoriesLoading}
              aria-label="选择要查询的物品类别"
            >
              <option value="">请选择一个物品</option>
              {categories.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          </div>

          <button
            type="button"
            className="primary-btn"
            onClick={handleSearch}
            disabled={!selectedCategory?.trim() || loading}
            aria-busy={loading}
            aria-label={loading ? "查询中" : "查询最后出现位置"}
          >
            {loading && <span className="btn-spinner" aria-hidden />}
            <span className="btn-text">
              {loading ? "查询中…" : "查询最后出现位置"}
            </span>
          </button>
        </section>

        <section
          className="result-panel"
          aria-label="查询结果"
          aria-live="polite"
          aria-atomic="true"
        >
          <h2 className="panel-title">
            {result ? `${result.category} · 最后出现` : "查询结果预览"}
          </h2>
          <div className="result-card">
            <div
              className={`image-container image-container-1920x1080 ${imageUrl && !imageLoading ? "image-container-zoomable" : ""}`}
            >
              {imageUrl ? (
                <>
                  <div className="image-container-scroll">
                    {imageLoading && (
                      <div className="image-loading" aria-hidden>
                        <span className="image-loading-spinner" />
                        <span>加载图片中…</span>
                      </div>
                    )}
                    <div
                      className="image-zoom-wrapper"
                      style={{
                        width: `${100 * imageZoom}%`,
                        height: `${100 * imageZoom}%`,
                      }}
                    >
                      <img
                        src={imageUrl}
                        alt={`${result?.category ?? "物品"} 最后出现`}
                        className="result-image"
                        onLoad={() => setImageLoading(false)}
                        onError={() => setImageLoading(false)}
                        style={{ opacity: imageLoading ? 0 : 1 }}
                        draggable={false}
                      />
                    </div>
                  </div>
                  {!imageLoading && (
                    <div className="image-zoom-controls" aria-label="图片缩放">
                      <button
                        type="button"
                        className="image-zoom-btn"
                        onClick={zoomOut}
                        disabled={imageZoom <= MIN_ZOOM}
                        title="缩小"
                        aria-label="缩小"
                      >
                        −
                      </button>
                      <button
                        type="button"
                        className="image-zoom-btn image-zoom-btn-value"
                        onClick={zoomReset}
                        title="还原 100%"
                        aria-label={`当前 ${Math.round(imageZoom * 100)}%，点击还原`}
                      >
                        {Math.round(imageZoom * 100)}%
                      </button>
                      <button
                        type="button"
                        className="image-zoom-btn"
                        onClick={zoomIn}
                        disabled={imageZoom >= MAX_ZOOM}
                        title="放大"
                        aria-label="放大"
                      >
                        +
                      </button>
                    </div>
                  )}
                </>
              ) : (
                <div className="image-placeholder">
                  <span className="placeholder-icon" aria-hidden>📷</span>
                  <span>
                    {loading
                      ? "正在查询…"
                      : "选择物品并点击「查询最后出现位置」"}
                  </span>
                </div>
              )}
            </div>
            <div className="result-info">
              <div className="info-row">
                <span className="info-label">物品</span>
                <span className="info-value">
                  {result?.category ?? "—"}
                </span>
              </div>
              <div className="info-row">
                <span className="info-label">最后出现时间</span>
                <span className="info-value">
                  {result?.timestamp ?? "—"}
                </span>
              </div>
            </div>
          </div>
          {error && (
            <div className="error-box">
              <p className="error-msg">{error}</p>
              <button
                type="button"
                className="retry-btn"
                onClick={handleRetry}
                aria-label="重试查询"
              >
                重试
              </button>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

export default ItemTracking;
