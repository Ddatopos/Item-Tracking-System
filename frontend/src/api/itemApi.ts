/**
 * 寻物接口：物品列表、某物品最后一次出现（图片地址 + 时间）
 * 后端约定：category / image_path / timestamp
 */

import http, { API_BASE, getApiErrorMessage } from "./http";

const USE_MOCK = process.env.REACT_APP_USE_MOCK === "true";
const MOCK_CATEGORIES = ["backpack", "phone", "keyboard", "cup", "chair", "laptop", "book", "bottle"];

export interface ItemLastAppearance {
  category: string;
  image_path: string;
  processed_image_path?: string | null;
  timestamp: string;
}

interface SearchOptions {
  cacheBust?: boolean;
}

/**
 * 获取所有物品类别列表（用于下拉选项）
 * @returns {Promise<string[]>}
 */
export async function getItemCategories(): Promise<string[]> {
  if (USE_MOCK) return [...MOCK_CATEGORIES];
  try {
    const { data } = await http.get<string[]>("/api/items");
    return Array.isArray(data) ? data : [];
  } catch (error: unknown) {
    throw new Error(getApiErrorMessage(error));
  }
}

/**
 * 查询某物品最后一次出现：图片地址 + 拍摄时间
 * @param {string} category - 物品类别
 * @param {{ cacheBust?: boolean }} options - cacheBust 为 true 时加时间戳避免使用缓存
 */
export async function getItemLastAppearance(
  category: string,
  options: SearchOptions = {}
): Promise<ItemLastAppearance> {
  if (USE_MOCK) {
    if (!MOCK_CATEGORIES.includes(category)) throw new Error("未找到该物品记录");
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540"><rect width="100%" height="100%" fill="#e2e8f0"/><rect x="280" y="110" width="360" height="300" fill="#14b8a6" fill-opacity=".18" stroke="#0f766e" stroke-width="8"/><text x="36" y="64" font-size="32" fill="#334155">${category} · mock</text></svg>`;
    const image = `data:image/svg+xml,${encodeURIComponent(svg)}`;
    return {
      category,
      image_path: image,
      processed_image_path: image,
      timestamp: new Date().toISOString(),
    };
  }
  const params = options.cacheBust ? { _t: Date.now() } : undefined;

  try {
    const { data } = await http.get<ItemLastAppearance>(`/api/items/${encodeURIComponent(category)}`, {
      params,
      headers: options.cacheBust ? { "Cache-Control": "no-cache" } : undefined,
    });
    return data;
  } catch (error: unknown) {
    throw new Error(getApiErrorMessage(error));
  }
}

/**
 * 根据后端返回的本地路径拼出前端可访问的图片 URL
 * 若 image_path 已是完整 URL 则直接返回
 */
export function getImageUrl(imagePath: string): string {
  if (!imagePath) return "";
  if (
    imagePath.startsWith("http://")
    || imagePath.startsWith("https://")
    || imagePath.startsWith("data:")
  ) {
    return imagePath;
  }
  const base = API_BASE.replace(/\/$/, "");
  const path = imagePath.startsWith("/") ? imagePath : `/${imagePath}`;
  return base + path;
}
