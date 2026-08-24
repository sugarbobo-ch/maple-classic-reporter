import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import App from '../src/App';
import { ToastProvider } from '../src/components/ui';
import { TEST_CONFIG, createMockPyWebViewApi, installMockPyWebView } from './mockPyWebViewApi';

function renderApp() {
  return render(<ToastProvider><App /></ToastProvider>);
}

describe('App onboarding boundary', () => {
  it('does not flash onboarding while the PyWebView bridge is still loading saved config', async () => {
    vi.useFakeTimers();
    const api = createMockPyWebViewApi();

    try {
      renderApp();

      expect(screen.getByRole('status')).toHaveTextContent('正在準備應用程式');
      await act(async () => {
        vi.advanceTimersByTime(250);
      });

      expect(
        screen.queryByRole('heading', { name: '新楓之谷：經典版《自動外掛檢舉工具》' })
      ).not.toBeInTheDocument();
      expect(screen.getByRole('status')).toHaveTextContent('正在準備應用程式');

      installMockPyWebView(api);
      await act(async () => {
        window.dispatchEvent(new Event('pywebviewready'));
        await Promise.resolve();
        await Promise.resolve();
      });

      expect(screen.getByRole('button', { name: /^設定$/ })).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it('keeps only the native window controls in the onboarding top-right corner', async () => {
    const api = createMockPyWebViewApi({
      get_initial_data: vi.fn().mockResolvedValue({
        config: { ...TEST_CONFIG, onboarding_completed: false },
        windows: [],
        audio_devices: [],
        history: [],
        gdrive_authenticated: false,
      }),
    });
    installMockPyWebView(api);
    renderApp();

    expect(await screen.findByRole('heading', { name: '新楓之谷：經典版《自動外掛檢舉工具》' })).toBeInTheDocument();
    const windowControls = screen.getByRole('group', { name: '視窗控制' });
    const controlBar = windowControls.parentElement as HTMLElement;
    expect(within(windowControls).getByRole('button', { name: '最小化' })).toBeInTheDocument();
    expect(within(windowControls).getByRole('button', { name: '最大化' })).toBeInTheDocument();
    expect(within(windowControls).getByRole('button', { name: '關閉' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '歷史紀錄' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '設定' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /切換為.+模式/ })).not.toBeInTheDocument();

    fireEvent.click(within(windowControls).getByRole('button', { name: '最小化' }));
    fireEvent.click(within(windowControls).getByRole('button', { name: '最大化' }));
    fireEvent.click(within(windowControls).getByRole('button', { name: '關閉' }));

    await waitFor(() => {
      expect(api.minimize_window).toHaveBeenCalledTimes(1);
      expect(api.toggle_window_maximized).toHaveBeenCalledTimes(1);
      expect(api.close_window).toHaveBeenCalledTimes(1);
    });

    fireEvent.mouseDown(controlBar, { button: 0 });
    fireEvent.doubleClick(controlBar, { button: 0 });
    await waitFor(() => {
      expect(api.drag_window).toHaveBeenCalledWith('proportional');
      expect(api.toggle_window_maximized).toHaveBeenCalledTimes(2);
    });
  });

  it('shows onboarding only after config loads and saves safe defaults when skipped', async () => {
    const api = createMockPyWebViewApi({
      get_initial_data: vi.fn().mockResolvedValue({
        config: { ...TEST_CONFIG, onboarding_completed: false },
        windows: [],
        audio_devices: [],
        history: [],
        gdrive_authenticated: false,
      }),
    });
    installMockPyWebView(api);
    renderApp();

    expect(await screen.findByRole('heading', { name: '新楓之谷：經典版《自動外掛檢舉工具》' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '使用預設設定' }));

    await waitFor(() =>
      expect(api.save_config_all).toHaveBeenCalledWith(
        expect.objectContaining({ onboarding_completed: true, report_submission_mode: 'automatic' })
      )
    );
    expect(await screen.findByRole('button', { name: /^設定$/ })).toBeInTheDocument();
  });

  it('reopens the tutorial from settings without clearing saved preferences', async () => {
    installMockPyWebView();
    renderApp();

    fireEvent.click(await screen.findByRole('button', { name: /^設定$/ }));
    fireEvent.click(await screen.findByRole('tab', { name: '關於與更新' }));
    fireEvent.click(screen.getByRole('button', { name: '重新開啟設定教學' }));

    expect(await screen.findByRole('heading', { name: '新楓之谷：經典版《自動外掛檢舉工具》' })).toBeInTheDocument();
  });
});
