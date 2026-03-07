/**
 * 寻物接口：物品列表、某物品最后一次出现（图片地址 + 时间）
 * 后端约定：category / image_path / timestamp
 */

const API_BASE = process.env.REACT_APP_API_URL || '';

/**
 * 获取所有物品类别列表（用于下拉选项）
 * @returns {Promise<string[]>}
 */
export async function getItemCategories() {
  const res = await fetch(`${API_BASE}/api/items`);
  if (!res.ok) throw new Error('获取物品列表失败');
  return res.json();
}

/**
 * 查询某物品最后一次出现：图片地址 + 拍摄时间
 * @param {string} category - 物品类别
 * @param {{ cacheBust?: boolean }} options - cacheBust 为 true 时加时间戳避免使用缓存
 * @returns {Promise<{ category: string, image_path: string, timestamp: string }>}
 */
export async function getItemLastAppearance(category, options = {}) {
  const encoded = encodeURIComponent(category);
  const url = options.cacheBust
    ? `${API_BASE}/api/items/${encoded}?_t=${Date.now()}`
    : `${API_BASE}/api/items/${encoded}`;
  const res = await fetch(url, options.cacheBust ? { cache: 'no-store' } : undefined);
  if (!res.ok) {
    if (res.status === 404) throw new Error('未找到该物品记录');
    throw new Error('查询失败');
  }
  return res.json();
}

/**
 * 根据后端返回的本地路径拼出前端可访问的图片 URL
 * 若 image_path 已是完整 URL 则直接返回
 */
export function getImageUrl(imagePath) {
  if (!imagePath) return '';
  if (imagePath.startsWith('http://') || imagePath.startsWith('https://')) {
    return imagePath;
  }
  const base = API_BASE.replace(/\/$/, '');
  const path = imagePath.startsWith('/') ? imagePath : `/${imagePath}`;
  return base + path;
}
