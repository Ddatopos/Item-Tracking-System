/**
 * 寻物接口：物品列表、某物品最后一次出现（图片地址 + 时间）
 * 后端约定：category / image_path / timestamp
 */

import { AxiosError } from "axios";
import http, { API_BASE } from "./http";

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
  try {
    const { data } = await http.get<string[]>("/api/items");
    return Array.isArray(data) ? data : [];
  } catch (error: unknown) {
    if (error instanceof Error) {
      throw new Error(error.message || "获取物品列表失败");
    }
    throw new Error("获取物品列表失败");
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
  const params = options.cacheBust ? { _t: Date.now() } : undefined;

  try {
    const { data } = await http.get<ItemLastAppearance>(`/api/items/${encodeURIComponent(category)}`, {
      params,
      headers: options.cacheBust ? { "Cache-Control": "no-cache" } : undefined,
    });
    return data;
  } catch (error: unknown) {
    const axiosError = error as AxiosError;
    if (axiosError.response?.status === 404) {
      throw new Error("未找到该物品记录");
    }
    if (error instanceof Error && error.message) {
      throw new Error(error.message);
    }
    throw new Error("查询失败");
  }
}

/**
 * 根据后端返回的本地路径拼出前端可访问的图片 URL
 * 若 image_path 已是完整 URL 则直接返回
 */
export function getImageUrl(imagePath: string): string {
  if (!imagePath) return "";
  if (imagePath.startsWith("http://") || imagePath.startsWith("https://")) {
    return imagePath;
  }
  const base = API_BASE.replace(/\/$/, "");
  const path = imagePath.startsWith("/") ? imagePath : `/${imagePath}`;
  return base + path;
}
