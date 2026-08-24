import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import SettingsView from '../src/components/SettingsView';
import type { SettingsViewProps } from '../src/components/SettingsView';
import { ToastProvider } from '../src/components/ui';
import { TEST_CONFIG } from './mockPyWebViewApi';

function renderSettings(
  initialTab: string,
  gdriveAuthenticated: boolean,
  onUpdateConfig = vi.fn(),
  overrides: Partial<SettingsViewProps> = {}
) {
  return render(
    <ToastProvider>
      <SettingsView
        config={TEST_CONFIG}
        initialTab={initialTab}
        gdriveAuthenticated={gdriveAuthenticated}
        onUpdateConfig={onUpdateConfig}
        onBack={vi.fn()}
        onOpenDriveFolder={vi.fn()}
        onAuthenticateDrive={vi.fn()}
        windows={[]}
        audioDevices={[]}
        {...overrides}
      />
    </ToastProvider>
  );
}

describe('SettingsView backend state', () => {
  it('supports roving keyboard navigation across setting tabs', async () => {
    renderSettings('general', false);
    const user = userEvent.setup();
    const generalTab = screen.getByRole('tab', { name: '一般與表單預設' });

    generalTab.focus();
    await user.keyboard('{ArrowRight}');

    const ocrTab = screen.getByRole('tab', { name: '文字辨識（OCR）設定' });
    await waitFor(() => expect(ocrTab).toHaveFocus());
    expect(ocrTab).toHaveAttribute('aria-selected', 'true');
    expect(generalTab).toHaveAttribute('tabindex', '-1');
  });

  it('shows the actual unauthorised Drive state instead of a fixed success badge', () => {
    const { rerender } = renderSettings('upload', false);
    const status = screen.getByTestId('gdrive-auth-status');

    expect(status).toHaveClass('ui-badge-warning');
    expect(status).not.toHaveClass('ui-badge-success');

    rerender(
      <ToastProvider>
        <SettingsView
          config={TEST_CONFIG}
          initialTab="upload"
          gdriveAuthenticated={true}
          onUpdateConfig={vi.fn()}
          onBack={vi.fn()}
          onOpenDriveFolder={vi.fn()}
          onAuthenticateDrive={vi.fn()}
        />
      </ToastProvider>
    );

    expect(screen.getByTestId('gdrive-auth-status')).toHaveClass('ui-badge-success');
  });

  it('persists each OCR switch independently', () => {
    const onUpdateConfig = vi.fn();
    renderSettings('ocr', false, onUpdateConfig);

    const switches = screen.getAllByRole('switch');
    expect(switches).toHaveLength(2);

    fireEvent.click(switches[0]);
    fireEvent.click(switches[1]);

    expect(onUpdateConfig).toHaveBeenNthCalledWith(1, 'ocr_autofill_id', false);
    expect(onUpdateConfig).toHaveBeenNthCalledWith(2, 'ocr_autofill_map', false);
  });

  it('confirms Google logout before disconnecting the account', async () => {
    const onDisconnectDrive = vi.fn().mockResolvedValue({
      success: true,
      message: 'Google 帳號已登出。',
      is_authenticated: false,
      remote_revoked: true,
      requires_manual_revoke: false,
    });
    renderSettings('upload', true, vi.fn(), { onDisconnectDrive });
    const user = userEvent.setup();

    await user.click(screen.getByRole('button', { name: '登出' }));
    expect(screen.getByRole('dialog', { name: '登出 Google 帳號？' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '登出 Google 帳號' }));

    await waitFor(() => expect(onDisconnectDrive).toHaveBeenCalledTimes(1));
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: '登出 Google 帳號？' })).not.toBeInTheDocument()
    );
  });

  it('offers manual Google permission cleanup when remote revocation fails', async () => {
    const onDisconnectDrive = vi.fn().mockResolvedValue({
      success: true,
      message: '這台電腦已登出，但無法連線撤銷 Google 授權。',
      is_authenticated: false,
      remote_revoked: false,
      requires_manual_revoke: true,
    });
    renderSettings('upload', true, vi.fn(), { onDisconnectDrive });
    const user = userEvent.setup();

    await user.click(screen.getByRole('button', { name: '登出' }));
    await user.click(screen.getByRole('button', { name: '登出 Google 帳號' }));

    expect((await screen.findAllByText('這台電腦已登出')).length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: '前往 Google 帳號權限' })).toBeEnabled();
  });

  it('requires explicit acknowledgement before deleting all local data', async () => {
    const onResetAllUserData = vi.fn().mockResolvedValue({
      success: true,
      accepted: true,
      message: '程式即將關閉並刪除所有本機資料。',
    });
    renderSettings('about', false, vi.fn(), { onResetAllUserData });
    const user = userEvent.setup();

    await user.click(screen.getByRole('button', { name: '刪除所有本機資料' }));
    const dialog = screen.getByRole('dialog', { name: '刪除所有本機資料？' });
    const resetButtons = screen.getAllByRole('button', { name: '刪除所有本機資料' });
    const confirmButton = resetButtons[resetButtons.length - 1];
    expect(confirmButton).toBeDisabled();

    await user.click(
      screen.getByRole('checkbox', { name: '我了解錄影、截圖與歷史紀錄將永久刪除' })
    );
    expect(confirmButton).toBeEnabled();
    await user.click(confirmButton);

    expect(dialog).toBeInTheDocument();
    await waitFor(() => expect(onResetAllUserData).toHaveBeenCalledTimes(1));
  });

  it('creates a quick link with the same HTTPS normalization as the legacy controller', async () => {
    const onUpdateConfig = vi.fn();
    renderSettings('quicklinks', false, onUpdateConfig);
    const user = userEvent.setup();

    await user.click(screen.getByRole('button', { name: '新增連結' }));
    await user.type(screen.getByPlaceholderText('例如：巴哈姆特討論區'), 'Custom');
    await user.type(screen.getByPlaceholderText('https://...'), 'example.com/custom');
    await user.click(screen.getByRole('button', { name: '儲存' }));

    expect(onUpdateConfig).toHaveBeenCalledWith(
      'quick_links',
      expect.arrayContaining([
        expect.objectContaining({
          title: 'Custom',
          url: 'https://example.com/custom',
          icon: 'Globe',
          isDefault: false,
        }),
      ])
    );
  });

  it('rejects an unsafe quick-link URL before persisting it', async () => {
    const onUpdateConfig = vi.fn();
    renderSettings('quicklinks', false, onUpdateConfig);
    const user = userEvent.setup();

    await user.click(screen.getByRole('button', { name: '新增連結' }));
    await user.type(screen.getByPlaceholderText('例如：巴哈姆特討論區'), 'Unsafe');
    await user.type(screen.getByPlaceholderText('https://...'), 'javascript:alert(1)');
    await user.click(screen.getByRole('button', { name: '儲存' }));

    expect(onUpdateConfig).not.toHaveBeenCalledWith(
      'quick_links',
      expect.arrayContaining([expect.objectContaining({ title: 'Unsafe' })])
    );
    expect(
      screen.getByText('請輸入安全的 HTTPS 網址（不可含帳號、密碼、片段或非 443 埠）。')
    ).toBeInTheDocument();
  });
});
