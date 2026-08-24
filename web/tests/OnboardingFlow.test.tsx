import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import OnboardingFlow from '../src/components/OnboardingFlow';
import { TEST_CONFIG, TEST_WINDOWS, installMockPyWebView } from './mockPyWebViewApi';

function renderOnboarding(overrides = {}) {
  const props = {
    config: { ...TEST_CONFIG, onboarding_completed: false, report_submission_mode: 'automatic' as const },
    windows: TEST_WINDOWS,
    gdriveAuthenticated: false,
    onUpdateConfig: vi.fn(),
    onUpdateConfigBatch: vi.fn(),
    onAuthenticateDrive: vi.fn(),
    onFinish: vi.fn(),
    onSkip: vi.fn(),
    ...overrides,
  };
  render(<OnboardingFlow {...props} />);
  return props;
}

describe('OnboardingFlow', () => {
  it('introduces the real workflow and lets experienced users keep safe defaults', () => {
    const props = renderOnboarding();

    expect(screen.getByRole('heading', { name: '新楓之谷：經典版《自動外掛檢舉工具》' })).toBeInTheDocument();
    expect(screen.getByRole('heading').querySelectorAll('.onboarding-title-line')).toHaveLength(2);
    expect(screen.getByText('協助你錄影蒐證、辨識角色資訊、上傳證據，並選擇手動或自動完成官方檢舉。')).toBeInTheDocument();
    expect(screen.getByText('蒐證')).toBeInTheDocument();
    expect(screen.getByText('不讀取、不修改任何遊戲記憶體。')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '開始設定' })).toHaveClass('ui-btn-lg');
    expect(screen.getByRole('button', { name: '使用預設設定' })).toHaveClass('ui-btn', 'ui-btn-ghost', 'ui-btn-lg');
    fireEvent.click(screen.getByRole('button', { name: '使用預設設定' }));
    expect(props.onSkip).toHaveBeenCalledTimes(1);
  });

  it('uses descriptive radio cards and offers a no-upload trial mode', () => {
    const props = renderOnboarding();
    fireEvent.click(screen.getByRole('button', { name: '開始設定' }));
    expect(screen.getByRole('radiogroup')).toHaveClass('onboarding-radio-list-3');
    expect(screen.getAllByRole('radio').every((radio) => radio.classList.contains('onboarding-radio-card'))).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: '下一步' }));
    fireEvent.click(screen.getByRole('button', { name: '下一步' }));

    expect(screen.getByRole('radio', { name: /Google Drive/ })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /Discord Webhook/ })).toBeInTheDocument();
    expect(screen.getAllByRole('radio').every((radio) => radio.querySelectorAll('svg').length === 1)).toBe(true);
    fireEvent.click(screen.getByRole('radio', { name: /只在本機試用/ }));
    expect(props.onUpdateConfig).toHaveBeenCalledWith('upload_destination', 'none');
  });

  it('scrolls every step inside the content region and places automatic reporting first', () => {
    renderOnboarding();
    fireEvent.click(screen.getByRole('button', { name: '開始設定' }));
    const scrollRegion = document.querySelector<HTMLElement>('.onboarding-scroll-region');
    expect(scrollRegion).not.toBeNull();
    if (scrollRegion) scrollRegion.scrollTop = 120;

    fireEvent.click(screen.getByRole('button', { name: '下一步' }));
    expect(scrollRegion?.scrollTop).toBe(0);
    fireEvent.click(screen.getByRole('button', { name: '下一步' }));
    fireEvent.click(screen.getByRole('button', { name: '下一步' }));

    expect(screen.getByRole('heading', { name: '檢舉方式' })).toBeInTheDocument();
    const reportChoices = screen.getAllByRole('radio');
    expect(reportChoices[0]).toHaveAccessibleName(/自動檢舉/);
    expect(reportChoices[0]).toHaveAttribute('aria-checked', 'true');
  });

  it('finishes with a clear next action and a separate settings summary', () => {
    renderOnboarding();
    fireEvent.click(screen.getByRole('button', { name: '開始設定' }));
    for (let index = 0; index < 4; index += 1) {
      fireEvent.click(screen.getByRole('button', { name: '下一步' }));
    }

    expect(screen.getByRole('heading', { name: '設定完成' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '設定摘要' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '開始使用' })).toBeInTheDocument();
  });

  it('explains how to create a Discord webhook before asking for the URL', () => {
    renderOnboarding({
      config: { ...TEST_CONFIG, onboarding_completed: false, upload_destination: 'discord' as const },
    });
    fireEvent.click(screen.getByRole('button', { name: '開始設定' }));
    fireEvent.click(screen.getByRole('button', { name: '下一步' }));
    fireEvent.click(screen.getByRole('button', { name: '下一步' }));

    expect(screen.getByText(/編輯頻道.*整合.*Webhook/)).toBeInTheDocument();
    expect(screen.getByLabelText('Discord Webhook 網址')).toBeInTheDocument();
  });

  it('uses progressive disclosure for recording settings and persists recognition choices', () => {
    const props = renderOnboarding();
    fireEvent.click(screen.getByRole('button', { name: '開始設定' }));
    expect(screen.getByRole('heading', { name: '錄影' })).toBeInTheDocument();
    expect(screen.queryByText('錄影秒數')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /進階設定/ }));
    expect(screen.getByText('錄影秒數')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '下一步' }));

    expect(screen.getByRole('heading', { name: '辨識' })).toBeInTheDocument();
    expect(screen.getByText('辨識會分析截圖和影片中的畫面，找出角色 ID 與地圖文字。不會讀取或修改遊戲程序或記憶體。')).toBeInTheDocument();
    const switches = screen.getAllByRole('switch');
    fireEvent.click(switches[0]);
    expect(props.onUpdateConfig).toHaveBeenCalledWith('ocr_autofill_id', false);
  });

  it('tests a Discord trial webhook and keeps the result visible', async () => {
    const api = installMockPyWebView({
      test_discord_webhook: vi.fn().mockResolvedValue({ success: true, message: '連線成功' }),
    });
    const config = {
      ...TEST_CONFIG,
      onboarding_completed: false,
      upload_destination: 'discord' as const,
      discord_webhook_url: 'https://discord.com/api/webhooks/1/token',
    };
    renderOnboarding({ config });
    fireEvent.click(screen.getByRole('button', { name: '開始設定' }));
    fireEvent.click(screen.getByRole('button', { name: '下一步' }));
    fireEvent.click(screen.getByRole('button', { name: '下一步' }));

    fireEvent.click(screen.getByRole('button', { name: '測試連線' }));

    await waitFor(() => expect(api.test_discord_webhook).toHaveBeenCalled());
    expect(await screen.findByText('連線成功')).toBeInTheDocument();
  });
});
