import React, { useState, useEffect } from "react";
import { getItemCategories, getItemLastAppearance, getImageUrl } from "./api/itemApi";
import "./App.css";

function App() {
  const [categories, setCategories] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [categoriesLoading, setCategoriesLoading] = useState(true);

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

  const handleSearch = () => {
    if (!selectedCategory?.trim()) return;
    setError(null);
    setResult(null);
    setLoading(true);
    getItemLastAppearance(selectedCategory.trim())
      .then((data) => {
        setResult({
          category: data.category ?? selectedCategory,
          image_path: data.image_path,
          timestamp: data.timestamp ?? "",
        });
      })
      .catch((e) => {
        setError(e.message || "查询失败");
      })
      .finally(() => setLoading(false));
  };

  const imageUrl = result?.image_path ? getImageUrl(result.image_path) : "";

  return (
    <div className="app">
      <header className="app-header">
        <div className="logo">家庭寻物系统</div>
        <div className="subtitle">按物品类别查询最后出现位置</div>
      </header>

      <main className="app-main">
        <section className="search-panel">
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
            className="primary-btn"
            onClick={handleSearch}
            disabled={!selectedCategory?.trim() || loading}
          >
            {loading ? "查询中…" : "查询最后出现位置"}
          </button>
        </section>

        <section className="result-panel">
          <h2 className="panel-title">查询结果预览</h2>
          <div className="result-card">
            <div className="image-container image-container-1920x1080">
              {imageUrl ? (
                <img
                  src={imageUrl}
                  alt={`${result?.category ?? "物品"} 最后出现`}
                  className="result-image"
                />
              ) : (
                <div className="image-placeholder">
                  <span>
                    {loading
                      ? "加载中…"
                      : "选择物品并点击查询后，这里会显示照片"}
                  </span>
                </div>
              )}
            </div>
            <div className="result-info">
              <div className="info-row">
                <span className="info-label">物品：</span>
                <span className="info-value">
                  {result?.category ?? "—"}
                </span>
              </div>
              <div className="info-row">
                <span className="info-label">最后出现时间：</span>
                <span className="info-value">
                  {result?.timestamp ?? "—"}
                </span>
              </div>
            </div>
          </div>
          {error && <p className="error-msg">{error}</p>}
        </section>
      </main>
    </div>
  );
}

export default App;
