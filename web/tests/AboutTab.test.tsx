import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import AboutTab from '../src/components/settings/AboutTab';
import { TEST_CONFIG } from './mockPyWebViewApi';

describe('AboutTab update notes', () => {
  it('keeps Markdown notes collapsed until the user opens them', () => {
    const onOpenExternalUrl = vi.fn();
    render(
      <AboutTab
        config={TEST_CONFIG}
        onUpdateConfig={vi.fn()}
        onOpenGitHub={vi.fn()}
        onOpenExternalUrl={onOpenExternalUrl}
        onOpenLogFile={vi.fn()}
        onOpenLogFolder={vi.fn()}
        updateStatus={{
          state: 'available',
          current_version: '2.0.0',
          target_version: '2.0.1',
          downloaded_bytes: 0,
          total_bytes: 12 * 1024 * 1024,
          progress_percent: 0,
          package_kind: 'delta',
          release_notes: '## Highlights\n\n- Faster checks',
          release_url: 'https://github.com/example/release',
          required_bytes: 40 * 1024 * 1024,
          available_bytes: 100 * 1024 * 1024,
        }}
      />
    );

    const summary = screen.getByText('更新內容');
    const details = summary.closest('details');
    expect(details).not.toHaveAttribute('open');
    expect(screen.getByText('套件：差分包')).toBeInTheDocument();
    expect(screen.getByText(/需要 40 MB/)).toBeInTheDocument();

    fireEvent.click(summary);
    expect(details).toHaveAttribute('open');
    expect(screen.getByRole('heading', { name: 'Highlights', level: 3 })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('link', { name: '在 GitHub 查看完整 Release' }));
    expect(onOpenExternalUrl).toHaveBeenCalledWith('https://github.com/example/release');
  });

  it('disables check for updates button while downloading', () => {
    const onCheckForUpdates = vi.fn();
    render(
      <AboutTab
        config={TEST_CONFIG}
        onUpdateConfig={vi.fn()}
        onOpenGitHub={vi.fn()}
        onOpenExternalUrl={vi.fn()}
        onOpenLogFile={vi.fn()}
        onOpenLogFolder={vi.fn()}
        onCheckForUpdates={onCheckForUpdates}
        updateStatus={{
          state: 'downloading',
          current_version: '2.0.0',
          target_version: '2.1.1',
          downloaded_bytes: 5 * 1024 * 1024,
          total_bytes: 10 * 1024 * 1024,
          progress_percent: 50,
          package_kind: 'delta',
          release_notes: '',
          release_url: '',
          required_bytes: 0,
          available_bytes: 0,
        }}
      />
    );

    const checkButton = screen.getByRole('button', { name: '檢查更新' });
    expect(checkButton).toBeDisabled();
  });
});
