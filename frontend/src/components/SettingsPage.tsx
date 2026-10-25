import React, { FormEvent, useEffect, useState } from "react";
import {
  getHealth,
  getRuntimeStatus,
  getSettings,
  startInference,
  stopInference,
  updateSettings,
} from "../api/cameraApi";
import { getItemCategories } from "../api/itemApi";
import type { InferenceStatus, Settings } from "../api/types";

const INITIAL_SETTINGS: Settings = {
  inference_fps: 2,
  confidence_threshold: 0.25,
  selected_classes: [],
  dedup_seconds: 30,
  input_size: 640,
};

function SettingsPage() {
  const [settings, setSettings] = useState<Settings>(INITIAL_SETTINGS);
  const [categories, setCategories] = useState<string[]>([]);
  const [newCategory, setNewCategory] = useState("");
  const [inferenceStatus, setInferenceStatus] = useState<InferenceStatus>("idle");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [controlPending, setControlPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([getSettings(), getItemCategories(), getHealth(), getRuntimeStatus()])
      .then(([currentSettings, availableCategories, health, runtimeStatus]) => {
        if (!active) return;
        setSettings(currentSettings);
        setCategories(Array.from(new Set([
          ...availableCategories,
          ...currentSettings.selected_classes,
        ])));
        const inferenceActive = ["running", "starting", "waiting_for_frame", "stopping"]
          .includes(runtimeStatus.inference_state);
        setInferenceStatus(inferenceActive ? "inferencing" : health.inference.status);
      })
      .catch((e: unknown) => {
        if (active) setError(e instanceof Error ? e.message : "加载设置失败");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const updateNumber = (key: "inference_fps" | "confidence_threshold" | "dedup_seconds" | "input_size", value: string) => {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      setSettings((current) => ({ ...current, [key]: parsed }));
      setNotice(null);
    }
  };

  const toggleCategory = (category: string) => {
    setSettings((current) => {
      const selected = new Set(current.selected_classes);
      if (selected.has(category)) selected.delete(category);
      else selected.add(category);
      return { ...current, selected_classes: Array.from(selected) };
    });
    setNotice(null);
  };

  const addCategory = () => {
    const category = newCategory.trim();
    if (!category) return;
    if (category.length > 100) {
      setError("类别名称不能超过 100 个字符。");
      return;
    }
    setSettings((current) => ({
      ...current,
      selected_classes: Array.from(new Set([...current.selected_classes, category])),
    }));
    setCategories((current) => current.includes(category) ? current : [...current, category]);
    setNewCategory("");
    setError(null);
    setNotice(null);
  };

  const saveSettings = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (saving) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const saved = await updateSettings({
        inference_fps: settings.inference_fps,
        confidence_threshold: settings.confidence_threshold,
        selected_classes: settings.selected_classes,
        dedup_seconds: settings.dedup_seconds,
        input_size: settings.input_size,
      });
      setSettings(saved);
      setNotice("设置已保存并由后端确认。");
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存设置失败");
    } finally {
      setSaving(false);
    }
  };

  const toggleInference = async () => {
    if (controlPending) return;
    setControlPending(true);
    setError(null);
    setNotice(null);
    try {
      if (inferenceStatus === "inferencing") {
        await stopInference();
        setInferenceStatus("stopped");
      } else {
        await startInference();
        setInferenceStatus("inferencing");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "识别控制失败");
    } finally {
      setControlPending(false);
    }
  };

  if (loading) {
    return (
      <div className="settings-page" aria-live="polite">
        <div className="preview-loading-spinner" />
        <span>正在读取后端设置…</span>
      </div>
    );
  }

  return (
    <div className="settings-page">
      <section className="settings-card">
        <header className="settings-header">
          <div>
            <h2 className="panel-title">识别设置</h2>
            <p className="panel-desc">设置通过后端 API 保存；模型和摄像头由后端启动配置管理。</p>
          </div>
          <span className={`status-badge status-badge-${inferenceStatus}`}>
            <span className={`status-dot status-dot-${inferenceStatus}`} />
            {inferenceStatus === "inferencing" ? "识别中" : inferenceStatus === "error" ? "异常" : "未识别"}
          </span>
        </header>

        <form onSubmit={saveSettings}>
          <div className="settings-grid">
            <div className="form-group">
              <label htmlFor="confidence-threshold">
                置信度阈值 <span>{Math.round(settings.confidence_threshold * 100)}%</span>
              </label>
              <input
                id="confidence-threshold"
                type="range"
                min="0"
                max="1"
                step="0.01"
                value={settings.confidence_threshold}
                onChange={(event) => updateNumber("confidence_threshold", event.target.value)}
              />
            </div>
            <div className="form-group">
              <label htmlFor="inference-fps">推理频率（帧/秒）</label>
              <input
                id="inference-fps"
                className="settings-input"
                type="number"
                min="0.1"
                max="30"
                step="0.1"
                value={settings.inference_fps}
                onChange={(event) => updateNumber("inference_fps", event.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="dedup-seconds">事件合并间隔（秒）</label>
              <input
                id="dedup-seconds"
                className="settings-input"
                type="number"
                min="0"
                max="3600"
                step="1"
                value={settings.dedup_seconds}
                onChange={(event) => updateNumber("dedup_seconds", event.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="input-size">模型输入尺寸</label>
              <input
                id="input-size"
                className="settings-input"
                type="number"
                min="32"
                max="2048"
                step="32"
                value={settings.input_size}
                onChange={(event) => updateNumber("input_size", event.target.value)}
                required
              />
              <span className="settings-hint">必须是 32 的倍数（32–2048）。</span>
            </div>
          </div>

          <fieldset className="category-fieldset">
            <legend>检测类别</legend>
            <label className="category-option">
              <input
                type="checkbox"
                checked={settings.selected_classes.length === 0}
                onChange={() => {
                  setSettings((current) => ({ ...current, selected_classes: [] }));
                  setNotice(null);
                }}
              />
              全部类别
            </label>
            {categories.length > 0 && (
              <div className="category-options">
                {categories.map((category) => (
                  <label className="category-option" key={category} title={category}>
                    <input
                      type="checkbox"
                      checked={settings.selected_classes.includes(category)}
                      onChange={() => toggleCategory(category)}
                    />
                    <span>{category}</span>
                  </label>
                ))}
              </div>
            )}
            <div className="add-category-control">
              <input
                className="settings-input"
                type="text"
                maxLength={100}
                value={newCategory}
                onChange={(event) => setNewCategory(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    addCategory();
                  }
                }}
                placeholder="输入类别名称"
                aria-label="输入自定义检测类别"
              />
              <button type="button" className="control-btn" onClick={addCategory}>
                添加类别
              </button>
            </div>
            {categories.length === 0 && (
              <p className="settings-hint">尚无历史类别，可输入类别名后添加。</p>
            )}
          </fieldset>

          <div className="settings-readonly">
            <div className="info-row">
              <span className="info-label">模型</span>
              <span className="info-value">{settings.model || "由后端启动配置决定"}</span>
            </div>
            <div className="info-row">
              <span className="info-label">摄像头</span>
              <span className="info-value">{settings.camera_id || "由后端启动配置决定"}</span>
            </div>
          </div>

          {error && <div className="events-error" role="alert">{error}</div>}
          {notice && <p className="settings-notice" role="status">{notice}</p>}
          <div className="settings-actions">
            <button type="submit" className="primary-btn" disabled={saving}>
              {saving ? "保存中…" : "保存设置"}
            </button>
            <button
              type="button"
              className={inferenceStatus === "inferencing" ? "control-btn control-btn-stop" : "control-btn control-btn-start"}
              onClick={() => void toggleInference()}
              disabled={controlPending}
            >
              {controlPending ? "处理中…" : inferenceStatus === "inferencing" ? "停止识别" : "启动识别"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

export default SettingsPage;
