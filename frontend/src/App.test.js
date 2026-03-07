/**
 * 寻物前端测试：验证能否正常显示后端返回的图片与时间
 * 运行: npm test -- --watchAll=false --testPathPattern=App.test
 * 浏览器验证: 使用 Mock 时无需后端，见 .env.development（REACT_APP_USE_MOCK=true），npm start 后选物品点查询即可看到 1920x1080 示例图与时间
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';

jest.mock('./api/itemApi', () => ({
  getItemCategories: jest.fn(() =>
    Promise.resolve(['手机', '钥匙', '遥控器'])
  ),
  getItemLastAppearance: jest.fn((category) =>
    Promise.resolve({
      category,
      image_path: 'https://example.com/test-1920x1080.jpg',
      timestamp: '2025-03-03 14:30:00',
    })
  ),
  getImageUrl: jest.fn((path) => path || ''),
}));

const itemApi = require('./api/itemApi');

describe('寻物前端：能否正常显示后端返回的图片与时间', () => {
  beforeEach(() => {
    itemApi.getItemCategories.mockResolvedValue(['手机', '钥匙', '遥控器']);
    itemApi.getItemLastAppearance.mockImplementation((category) =>
      Promise.resolve({
        category,
        image_path: 'https://example.com/test-1920x1080.jpg',
        timestamp: '2025-03-03 14:30:00',
      })
    );
    itemApi.getImageUrl.mockImplementation((path) => path || '');
  });

  it('初始加载会请求物品列表并显示在下拉框', async () => {
    render(<App />);
    expect(itemApi.getItemCategories).toHaveBeenCalled();
    await waitFor(() => {
      expect(screen.getByRole('option', { name: '手机' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: '钥匙' })).toBeInTheDocument();
    });
  });

  it('选择物品并点击查询后，显示后端返回的图片地址和时间', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole('combobox')).not.toBeDisabled();
    });

    const select = screen.getByRole('combobox', { name: /物品类别/i });
    await userEvent.selectOptions(select, '手机');

    const btn = screen.getByRole('button', { name: /查询最后出现位置/i });
    await userEvent.click(btn);

    await waitFor(() => {
      expect(itemApi.getItemLastAppearance).toHaveBeenCalledWith('手机');
    });

    await waitFor(() => {
      const img = screen.getByRole('img', { name: /手机 最后出现/i });
      expect(img).toBeInTheDocument();
      expect(img).toHaveAttribute(
        'src',
        'https://example.com/test-1920x1080.jpg'
      );
    });

    expect(screen.getByText('2025-03-03 14:30:00')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /手机 最后出现/i })).toBeInTheDocument();
    expect(itemApi.getImageUrl).toHaveBeenCalledWith(
      'https://example.com/test-1920x1080.jpg'
    );
  });

  it('结果区展示物品名称与最后出现时间两行信息', async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByRole('combobox')).not.toBeDisabled();
    });
    await userEvent.selectOptions(screen.getByRole('combobox'), '钥匙');
    await userEvent.click(screen.getByRole('button', { name: /查询最后出现位置/i }));

    await waitFor(() => {
      expect(screen.getByRole('img', { name: /钥匙 最后出现/i })).toBeInTheDocument();
      expect(screen.getByText('2025-03-03 14:30:00')).toBeInTheDocument();
    });
  });
});
