import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import HistoryView, { HistoryViewProps } from '../src/components/HistoryView';
import { ToastProvider } from '../src/components/ui';
import { TEST_HISTORY, installMockPyWebView } from './mockPyWebViewApi';
import { HistoryRecord } from '../src/types';

function renderHistory(
  onOpenUrl = vi.fn(),
  onClearHistory = vi.fn().mockResolvedValue(true),
  onCheckSanctions = vi.fn().mockResolvedValue(undefined),
  extraProps: Partial<HistoryViewProps> = {}
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
  it('offers continue reporting only for available drafts', () => {
    const onContinueDraft = vi.fn();
    const draft: HistoryRecord = {
      record_id: 'draft-1',
      time: '2026-08-23 12:00:00',
      submission_state: 'draft',
      media_path: 'C:\\test\\evidence.mp4',
      media_type: 'video',
      media_available: true,
    };
    renderHistory(vi.fn(), vi.fn(), vi.fn(), {
      history: [draft],
      onContinueDraft,
    });

    expect(screen.getByText('尚未送出')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('continue-draft-draft-1'));
    expect(screen.getByText('要直接使用已儲存的資料，還是先重新辨識這份證據？')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('continue-draft-with-saved-data'));
    expect(onContinueDraft).toHaveBeenCalledWith(draft, false);
  });

  it('offers recognition using the current ID and map settings', () => {
    const onContinueDraft = vi.fn();
    const draft: HistoryRecord = {
      record_id: 'draft-recognize',
      submission_state: 'draft',
      media_path: 'C:\\test\\evidence.mp4',
      media_available: true,
    };
    renderHistory(vi.fn(), vi.fn(), vi.fn(), {
      history: [draft],
      onContinueDraft,
      ocrAutofillId: true,
      ocrAutofillMap: false,
    });

    fireEvent.click(screen.getByTestId('continue-draft-draft-recognize'));
    expect(screen.getByText('依目前設定，將重新辨識：角色 ID。')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('continue-draft-with-recognition'));
    expect(onContinueDraft).toHaveBeenCalledWith(draft, true);
  });

  it('disables recognition when both OCR auto-fill settings are off', () => {
    const draft: HistoryRecord = {
      record_id: 'draft-no-ocr',
      submission_state: 'draft',
      media_path: 'C:\\test\\evidence.mp4',
      media_available: true,
    };
    renderHistory(vi.fn(), vi.fn(), vi.fn(), {
      history: [draft],
      onContinueDraft: vi.fn(),
      ocrAutofillId: false,
      ocrAutofillMap: false,
    });

    fireEvent.click(screen.getByTestId('continue-draft-draft-no-ocr'));
    expect(screen.getByTestId('continue-draft-with-recognition')).toBeDisabled();
    expect(screen.getByText(/目前已關閉角色 ID 與地圖辨識/)).toBeInTheDocument();
  });

  it('disables continue reporting when draft evidence is missing', () => {
    const draft: HistoryRecord = {
      record_id: 'draft-missing',
      submission_state: 'draft',
      media_path: 'C:\\missing.mp4',
      media_available: false,
    };
    renderHistory(vi.fn(), vi.fn(), vi.fn(), {
      history: [draft],
      onContinueDraft: vi.fn(),
    });

    expect(screen.getByText('檔案遺失')).toBeInTheDocument();
    expect(screen.getByTestId('continue-draft-draft-missing')).toBeDisabled();
  });

  it('opens and copies the real evidence URL from a history row', async () => {
    const onOpenUrl = vi.fn();
    const api = installMockPyWebView();
    renderHistory(onOpenUrl);

    const dataRow = screen.getAllByRole('row')[1];
    const actionButtons = dataRow.querySelectorAll('.history-actions button');
    expect(actionButtons).toHaveLength(2);
    expect(actionButtons[0]).toHaveClass('ui-btn-ghost', 'ui-btn-icon');
    expect(actionButtons[1]).toHaveClass('ui-btn-ghost', 'ui-btn-icon');

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

    fireEvent.click(screen.getByTestId('history-more-actions'));
    fireEvent.click(screen.getByRole('menuitem', { name: '清空歷史紀錄' }));
    const dialog = screen.getByRole('dialog', { name: '清空歷史紀錄' });
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: '清空歷史紀錄' })).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('confirm-clear-history-button'));
    await waitFor(() => expect(onClearHistory).toHaveBeenCalledTimes(1));
  });

  it('offers manual evidence cleanup for a submitted Google Drive record', async () => {
    const record: HistoryRecord = {
      record_id: 'submitted-drive-1',
      submission_state: 'submitted',
      evidence_url: 'https://drive.google.com/file/d/file-123/view',
      evidence_provider: 'gdrive',
      remote_evidence_id: 'file-123',
      remote_evidence_state: 'available',
      media_cleanup_eligible: true,
      media_path: 'C:\\recordings\\maple_evidence_1.mp4',
      suspect_id: 'PlayerOne',
    };
    const cleanup = vi.fn().mockResolvedValue({ success: true, cleaned_record_ids: [record.record_id] });
    renderHistory(vi.fn(), vi.fn(), vi.fn(), {
      history: [record],
      onCleanupEvidence: cleanup,
    });

    fireEvent.click(screen.getByRole('button', { name: /更多操作/ }));
    fireEvent.click(screen.getByRole('menuitem', { name: '清理證據' }));
    expect(screen.getByRole('dialog', { name: '清理證據' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('checkbox', { name: '將 Google Drive 檔案移至垃圾桶' }));
    fireEvent.click(screen.getByRole('button', { name: '清理所選證據' }));

    await waitFor(() => expect(cleanup).toHaveBeenCalledWith(['submitted-drive-1'], ['google_drive']));
  });

  it('lets users delete the record when Drive cleanup fails', async () => {
    const record: HistoryRecord = {
      record_id: 'submitted-drive-failure',
      submission_state: 'submitted',
      evidence_url: 'https://drive.google.com/file/d/file-456/view',
      evidence_provider: 'gdrive',
      remote_evidence_id: 'file-456',
      remote_evidence_state: 'available',
      suspect_id: 'PlayerTwo',
    };
    const deleteEntries = vi
      .fn()
      .mockResolvedValueOnce({
        success: false,
        failed_record_ids: [record.record_id],
        failed: [{ record_id: record.record_id, message: 'Google Drive 權限不足' }],
      })
      .mockResolvedValueOnce({ success: true, deleted_record_ids: [record.record_id] });
    renderHistory(vi.fn(), vi.fn(), vi.fn(), {
      history: [record],
      onDeleteHistoryEntries: deleteEntries,
    });

    fireEvent.click(screen.getByRole('button', { name: /更多操作/ }));
    fireEvent.click(screen.getByRole('menuitem', { name: '刪除紀錄' }));
    fireEvent.click(screen.getByRole('checkbox', { name: '將 Google Drive 檔案移至垃圾桶' }));
    fireEvent.click(screen.getByRole('button', { name: '刪除紀錄' }));

    await waitFor(() => expect(screen.getByRole('button', { name: '只刪除紀錄' })).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: '只刪除紀錄' }));
    await waitFor(() => expect(deleteEntries).toHaveBeenNthCalledWith(2, [record.record_id], []));
  });

  it('triggers sanction check when check button is clicked', async () => {
    const onCheckSanctions = vi.fn().mockResolvedValue(undefined);
    renderHistory(vi.fn(), vi.fn(), onCheckSanctions);

    const checkBtn = screen.getByTestId('check-sanction-status');
    expect(checkBtn).toHaveTextContent('檢查官方處分狀態');
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

    expect(screen.getByText('已封鎖')).toBeInTheDocument();
    expect(screen.getByText('未封鎖')).toBeInTheDocument();
    expect(screen.getByText('上次完整檢查：尚未完成檢查')).toBeInTheDocument();

    const openAnnouncementBtn = screen.getByLabelText('開啟官方處分公告');
    fireEvent.click(openAnnouncementBtn);
    expect(onOpenUrl).toHaveBeenCalledWith(
      'https://maplestoryclassic.beanfun.com/Bulletin/Detail/12345'
    );
  });

  it('toggles compact mode on and off', () => {
    renderHistory();

    expect(screen.getByRole('table')).not.toHaveClass('compact');

    fireEvent.click(screen.getByTestId('history-more-actions'));
    const toggleBtn = screen.getByRole('menuitem', { name: '切換為緊湊排列' });
    fireEvent.click(toggleBtn);
    expect(screen.getByRole('table')).toHaveClass('compact');

    fireEvent.click(screen.getByTestId('history-more-actions'));
    fireEvent.click(screen.getByRole('menuitem', { name: '切換為標準排列' }));
    expect(screen.getByRole('table')).not.toHaveClass('compact');
  });

  it('does not show an empty pending tab when every record is submitted', () => {
    renderHistory();

    expect(screen.queryByRole('button', { name: /待處理/ })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /全部/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /已完成/ })).toBeInTheDocument();
  });

  it('keeps completed-row actions centered without a placeholder dash', () => {
    renderHistory();

    const operationCell = screen.getAllByRole('row')[1].querySelector('.history-operation-cell');
    expect(operationCell).not.toBeNull();
    expect(operationCell?.querySelector('.history-row-actions')).toBeInTheDocument();
    expect(operationCell?.textContent).not.toContain('-');
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
    expect(screen.getByTestId('pagination-info')).toHaveTextContent(
      '顯示第 1 ~ 15 筆，共 25 筆紀錄'
    );
    expect(screen.getByText('suspect-1')).toBeInTheDocument();
    expect(screen.getByText('suspect-15')).toBeInTheDocument();
    expect(screen.queryByText('suspect-16')).not.toBeInTheDocument();

    // Click next page
    const nextBtn = screen.getByRole('button', { name: '下一頁' });
    fireEvent.click(nextBtn);

    expect(screen.getByTestId('pagination-info')).toHaveTextContent(
      '顯示第 16 ~ 25 筆，共 25 筆紀錄'
    );
    expect(screen.queryByText('suspect-1')).not.toBeInTheDocument();
    expect(screen.getByText('suspect-16')).toBeInTheDocument();
    expect(screen.getByText('suspect-25')).toBeInTheDocument();
  });
});
