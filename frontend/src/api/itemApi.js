/**
 * 寻物接口：物品列表、某物品最后一次出现（图片地址 + 时间）
 * 后端约定：category / image_path / timestamp
 */

const API_BASE = process.env.REACT_APP_API_URL || '';
const USE_MOCK = process.env.REACT_APP_USE_MOCK === 'true';

/** Mock 数据：开发时无后端可用来验证前端展示（REACT_APP_USE_MOCK=true） */
const MOCK_CATEGORIES = ['手机', '钥匙', '遥控器', '钱包'];
// 按物品类别返回不同图片（picsum 用不同 id 得到不同图），便于验证“切换类别会换图”
const MOCK_IMAGE_BY_CATEGORY = {
  手机: 'https://picsum.photos/id/10/1920/1080',
  钥匙: 'https://picsum.photos/id/20/1920/1080',
  遥控器: 'https://picsum.photos/id/30/1920/1080',
  钱包: 'https://picsum.photos/id/40/1920/1080',
};
const MOCK_IMAGE_DEFAULT = 'https://picsum.photos/1920/1080';

function mockGetItemCategories() {
  return Promise.resolve([...MOCK_CATEGORIES]);
}

function mockGetItemLastAppearance(category) {
  const image_path = MOCK_IMAGE_BY_CATEGORY[category] || MOCK_IMAGE_DEFAULT;
  return Promise.resolve({
    category,
    image_path,
    timestamp: '2025-03-03 14:30:00',
  });
}

/**
 * 获取所有物品类别列表（用于下拉选项）
 * @returns {Promise<string[]>}
 */
export async function getItemCategories() {
  if (USE_MOCK) return mockGetItemCategories();
  const res = await fetch(`${API_BASE}/api/items`);
  if (!res.ok) throw new Error('获取物品列表失败');
  return res.json();
}

/**
 * 查询某物品最后一次出现：图片地址 + 拍摄时间
 * @param {string} category - 物品类别
 * @returns {Promise<{ category: string, image_path: string, timestamp: string }>}
 */
export async function getItemLastAppearance(category) {
  if (USE_MOCK) return mockGetItemLastAppearance(category);
  const encoded = encodeURIComponent(category);
  const res = await fetch(`${API_BASE}/api/items/${encoded}`);
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
