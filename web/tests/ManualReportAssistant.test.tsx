import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import ManualReportAssistant from '../src/components/report-flow/ManualReportAssistant';
import { ToastProvider } from '../src/components/ui';
import { installMockPyWebView } from './mockPyWebViewApi';

describe('ManualReportAssistant', () => {
  it('shows official fields in order and confirms only after an explicit check', () => {
    installMockPyWebView();
    const onOpenReportPage = vi.fn();
    const onConfirm = vi.fn();
    render(
      <ToastProvider>
        <ManualReportAssistant
          record={{
            record_id: 'manual-1',
            submission_state: 'awaiting_manual',
            suspect_id: 'ManualPlayer',
            server: '雪吉拉',
            map_name: '墮落城市',
            note: '疑似自動打怪',
            evidence_url: 'https://example.com/evidence',
          }}
          onOpenReportPage={onOpenReportPage}
          onConfirm={onConfirm}
          onLater={vi.fn()}
        />
      </ToastProvider>
    );

    const labels = screen.getAllByText(/^(角色 ID|伺服器|地圖名稱|違規說明|檢舉證據網址)$/);
    expect(labels.map((node) => node.textContent)).toEqual([
      '角色 ID',
      '伺服器',
      '地圖名稱',
      '違規說明',
      '檢舉證據網址',
    ]);

    fireEvent.click(screen.getByRole('button', { name: '開啟外掛檢舉頁面' }));
    expect(onOpenReportPage).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('button', { name: '我已完成檢舉' }));
    expect(onConfirm).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '確認已成功送出' }));
    expect(onConfirm).toHaveBeenCalledWith('manual-1');
  });
});
