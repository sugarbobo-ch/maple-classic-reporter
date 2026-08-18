import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import HistoryView from '../src/components/HistoryView';
import { ToastProvider } from '../src/components/ui';
import { TEST_HISTORY, installMockPyWebView } from './mockPyWebViewApi';
import { HistoryRecord } from '../src/types';

function renderHistory(
  onOpenUrl = vi.fn(),
  onClearHistory = vi.fn().mockResolvedValue(true),
  onCheckSanctions = vi.fn().mockResolvedValue(undefined),
  extraProps: Record<string, any> = {}
) {
  return render(
    <ToastProvider>
      <HistoryView
        history={TEST_HISTORY}
        onBack={vi.fn()}
        onClearHistory={onClearHistory}
        onOpenUrl={onOpenUrl}
        onCheckSanctions={onCheckSanctions}
        {...extraProps}
      />
    </ToastProvider>
  );
}

describe('HistoryView evidence links and sanction status', () => {
  it('opens and copies the real evidence URL from a history row', async () => {
    const onOpenUrl = vi.fn();
    const api = installMockPyWebView();
    renderHistory(onOpenUrl);

    const dataRow = screen.getAllByRole('row')[1];
    const actionButtons = within(dataRow).getAllByRole('button');
    expect(actionButtons).toHaveLength(2);

    fireEvent.click(actionButtons[0]);
    expect(onOpenUrl).toHaveBeenCalledWith(TEST_HISTORY[0].evidence_url);

    fireEvent.click(actionButtons[1]);
    await waitFor(() => {
      expect(api.set_clipboard_text).toHaveBeenCalledWith(TEST_HISTORY[0].evidence_url);
    });
  });

  it('clears persisted history only after confirmation', async () => {
    const onClearHistory = vi.fn().mockResolvedValue(true);
    installMockPyWebView();
    renderHistory(vi.fn(), onClearHistory);

    fireEvent.click(screen.getByTestId('clear-history'));
    expect(screen.getByText('清空歷史紀錄')).toBeInTheDocument();
    expect(screen.getByTestId('confirm-clear-history-button')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('confirm-clear-history-button'));
    await waitFor(() => expect(onClearHistory).toHaveBeenCalledTimes(1));
  });

  it('triggers sanction check when check button is clicked', async () => {
    const onCheckSanctions = vi.fn().mockResolvedValue(undefined);
    renderHistory(vi.fn(), vi.fn(), onCheckSanctions);

    const checkBtn = screen.getByTestId('check-sanction-status');
    expect(checkBtn).toHaveTextContent('檢查制裁狀態');
    fireEvent.click(checkBtn);
    expect(onCheckSanctions).toHaveBeenCalledTimes(1);
  });

  it('displays checking state, progress message, and last sync timestamp', () => {
    renderHistory(vi.fn(), vi.fn(), vi.fn(), {
      isCheckingSanctions: true,
      sanctionSyncStatus: {
        running: true,
        phase: 'fetching',
        current: 2,
        total: 5,
        message: '正在檢查第 2/5 篇公告',
      },
      lastCompleteSyncAt: '2026-08-17T14:30:00+08:00',
    });

    const checkBtn = screen.getByTestId('check-sanction-status');
    expect(checkBtn).toBeDisabled();
    expect(checkBtn).toHaveTextContent('檢查中…');
    expect(screen.getByText('正在檢查第 2/5 篇公告')).toBeInTheDocument();
    expect(screen.getByText('上次完整檢查：2026-08-17 14:30')).toBeInTheDocument();
  });

  it('renders banned status badge with tooltip and announcement link button', () => {
    const bannedHistory: HistoryRecord[] = [
      {
        record_id: 'rec-1',
        time: '2026-08-17 10:00:00',
        suspect_id: 'HackerPlayer',
        server: '雪吉拉',
        map: '勇士之村',
        status: '成功',
        ban_status: 'banned',
        ban_date: '2026-08-17',
        ban_result: '永久鎖定',
        ban_announcement_url: 'https://maplestoryclassic.beanfun.com/Bulletin/Detail/12345',
        evidence_url: 'https://drive.google.com/file/d/test/view',
      },
      {
        record_id: 'rec-2',
        time: '2026-08-17 11:00:00',
        suspect_id: 'CleanPlayer',
        server: '雪吉拉',
        map: '魔法森林',
        status: '成功',
        ban_status: 'unbanned',
      },
    ];

    const onOpenUrl = vi.fn();
    render(
      <ToastProvider>
        <HistoryView
          history={bannedHistory}
          onBack={vi.fn()}
          onOpenUrl={onOpenUrl}
          lastCompleteSyncAt={null}
        />
      </ToastProvider>
    );

    expect(screen.getByText('已制裁')).toBeInTheDocument();
    expect(screen.getByText('未被制裁')).toBeInTheDocument();
    expect(screen.getByText('上次完整檢查：尚未完成檢查')).toBeInTheDocument();

    const openAnnouncementBtn = screen.getByLabelText('開啟官方制裁公告');
    fireEvent.click(openAnnouncementBtn);
    expect(onOpenUrl).toHaveBeenCalledWith('https://maplestoryclassic.beanfun.com/Bulletin/Detail/12345');
  });

  it('toggles compact mode on and off', () => {
    renderHistory();

    const toggleBtn = screen.getByTestId('toggle-compact-mode');
    expect(toggleBtn).toHaveTextContent('標準排列');
    expect(screen.getByRole('table')).not.toHaveClass('compact');

    fireEvent.click(toggleBtn);
    expect(toggleBtn).toHaveTextContent('緊密排列');
    expect(screen.getByRole('table')).toHaveClass('compact');

    fireEvent.click(toggleBtn);
    expect(toggleBtn).toHaveTextContent('標準排列');
    expect(screen.getByRole('table')).not.toHaveClass('compact');
  });

  it('paginates records and handles page navigation', () => {
    const manyRecords: HistoryRecord[] = Array.from({ length: 25 }, (_, i) => ({
      record_id: `rec-${i + 1}`,
      time: `2026-08-17 12:${i < 10 ? '0' + i : i}:00`,
      suspect_id: `suspect-${i + 1}`,
      server: 'Gamania',
      map_name: `Map ${i + 1}`,
      upload_status: 'success',
      evidence_url: `https://drive.google.com/file/d/test-${i + 1}/view`,
    }));

    render(
      <ToastProvider>
        <HistoryView history={manyRecords} onBack={vi.fn()} onOpenUrl={vi.fn()} />
      </ToastProvider>
    );

    // Default pageSize is 15 -> page 1 shows 15 rows
    expect(screen.getByTestId('pagination-info')).toHaveTextContent('顯示第 1 ~ 15 筆，共 25 筆紀錄');
    expect(screen.getByText('suspect-1')).toBeInTheDocument();
    expect(screen.getByText('suspect-15')).toBeInTheDocument();
    expect(screen.queryByText('suspect-16')).not.toBeInTheDocument();

    // Click next page
    const nextBtn = screen.getByRole('button', { name: '下一頁' });
    fireEvent.click(nextBtn);

    expect(screen.getByTestId('pagination-info')).toHaveTextContent('顯示第 16 ~ 25 筆，共 25 筆紀錄');
    expect(screen.queryByText('suspect-1')).not.toBeInTheDocument();
    expect(screen.getByText('suspect-16')).toBeInTheDocument();
    expect(screen.getByText('suspect-25')).toBeInTheDocument();
  });
});
