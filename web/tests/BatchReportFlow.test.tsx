import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import ReportFlowModal from '../src/components/ReportFlowModal';
import { ToastProvider } from '../src/components/ui';
import { TEST_CONFIG } from './mockPyWebViewApi';
import type { HistoryRecord } from '../src/types';

const evidence = {
  suspect_ids: ['甲', '乙'],
  map_name: '弓箭手村',
  media_path: 'C:/test.mp4',
  media_type: 'video' as const,
};

describe('batch report form', () => {
  it('preserves the batch payload when saving from recognition progress', async () => {
    const saveDraft = vi.fn().mockResolvedValue(undefined);
    const records: HistoryRecord[] = [
      {
        record_id: 'batch-1',
        suspect_id: '甲',
        batch_id: 'batch',
        batch_order: 0,
        batch_note: '共用說明',
        submission_state: 'draft',
        batch_phase: 'draft',
        media_path: 'C:/test.mp4',
        media_type: 'video',
        media_available: true,
      },
      {
        record_id: 'batch-2',
        suspect_id: '乙',
        batch_id: 'batch',
        batch_order: 1,
        batch_note: '共用說明',
        note_override: '乙的說明',
        submission_state: 'draft',
        batch_phase: 'draft',
        media_path: 'C:/test.mp4',
        media_type: 'video',
        media_available: true,
      },
    ];
    render(
      <ToastProvider>
        <ReportFlowModal
          stage="progress"
          config={TEST_CONFIG}
          history={records}
          initialRecord={records[0]}
          ocrResults={{ ...evidence, media_path: 'C:/test.mp4' }}
          onClose={vi.fn()}
          onUpdateWhitelist={vi.fn()}
          onSubmitReport={vi.fn()}
          onSaveDraft={saveDraft}
        />
      </ToastProvider>
    );
    fireEvent.click(screen.getByTestId('save-draft-progress'));
    await waitFor(() => expect(saveDraft).toHaveBeenCalledTimes(1));
    expect(saveDraft).toHaveBeenCalledWith(
      expect.objectContaining({
        batch_id: 'batch',
        suspect_id: '甲',
        map_name: '弓箭手村',
        note: '共用說明',
        suspects: [
          { suspect_id: '甲', note_override: null },
          { suspect_id: '乙', note_override: '乙的說明' },
        ],
      })
    );
  });

  it('commits the final unseparated name and keeps per-person notes separate', async () => {
    const submit = vi.fn();
    render(
      <ToastProvider>
        <ReportFlowModal
          stage="form"
          config={TEST_CONFIG}
          ocrResults={evidence}
          onClose={vi.fn()}
          onUpdateWhitelist={vi.fn()}
          onSubmitReport={submit}
        />
      </ToastProvider>
    );
    fireEvent.click(screen.getByRole('button', { name: '乙' }));
    fireEvent.click(screen.getByRole('button', { name: /編輯 乙 的個別說明/ }));
    fireEvent.change(screen.getByLabelText('乙 的檢舉說明'), {
      target: { value: '乙在第十秒出現' },
    });
    expect(
      screen.getByRole('button', { name: /編輯 乙 的個別說明，已自訂說明/ })
    ).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('補充說明'), { target: { value: '新的共用說明' } });
    expect(screen.getByLabelText('乙 的檢舉說明')).toHaveValue('乙在第十秒出現');
    fireEvent.click(screen.getByRole('button', { name: /編輯 甲 的個別說明/ }));
    expect(screen.queryByLabelText('乙 的檢舉說明')).not.toBeInTheDocument();
    expect(screen.getByLabelText('甲 的檢舉說明')).toHaveValue('新的共用說明');
    fireEvent.click(screen.getByRole('button', { name: /編輯 乙 的個別說明/ }));
    expect(screen.getByLabelText('乙 的檢舉說明')).toHaveValue('乙在第十秒出現');
    fireEvent.change(screen.getByRole('textbox', { name: '疑似角色 ID' }), {
      target: { value: '丙' },
    });
    fireEvent.click(screen.getByTestId('report-submit'));
    await waitFor(() =>
      expect(submit).toHaveBeenCalledWith(
        expect.objectContaining({
          note: '新的共用說明',
          suspects: [
            { suspect_id: '甲', note_override: null },
            { suspect_id: '乙', note_override: '乙在第十秒出現' },
            { suspect_id: '丙', note_override: null },
          ],
        })
      )
    );
  });

  it('restores all batch draft names and notes in order', () => {
    const records: HistoryRecord[] = ['甲', '乙'].map((suspect_id, index) => ({
      record_id: String(index),
      suspect_id,
      batch_id: 'batch',
      batch_order: index,
      batch_note: '共用',
      note_override: index ? '個別' : null,
      batch_phase: 'draft',
      submission_state: 'draft',
      media_path: 'C:/test.mp4',
    }));
    render(
      <ToastProvider>
        <ReportFlowModal
          stage="form"
          config={TEST_CONFIG}
          ocrResults={evidence}
          history={records.slice().reverse()}
          initialRecord={records[1]}
          onClose={vi.fn()}
          onUpdateWhitelist={vi.fn()}
          onSubmitReport={vi.fn()}
        />
      </ToastProvider>
    );
    expect(screen.getByRole('button', { name: '刪除 甲' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '刪除 乙' })).toBeInTheDocument();
    expect(screen.getByLabelText('補充說明')).toHaveValue('共用');
    fireEvent.click(screen.getByRole('button', { name: /編輯 乙 的個別說明/ }));
    expect(screen.getByLabelText('乙 的檢舉說明')).toHaveValue('個別');
    fireEvent.click(screen.getByRole('button', { name: '恢復共用' }));
    expect(screen.getByLabelText('乙 的檢舉說明')).toHaveValue('共用');
  });

  it('never repopulates a cleared list on OCR reruns', () => {
    const props = {
      stage: 'form' as const,
      config: TEST_CONFIG,
      onClose: vi.fn(),
      onUpdateWhitelist: vi.fn(),
      onSubmitReport: vi.fn(),
    };
    const { rerender } = render(
      <ToastProvider>
        <ReportFlowModal {...props} ocrResults={evidence} />
      </ToastProvider>
    );
    fireEvent.click(screen.getByRole('button', { name: '全部刪除' }));
    rerender(
      <ToastProvider>
        <ReportFlowModal {...props} ocrResults={{ ...evidence, suspect_ids: ['丙'] }} />
      </ToastProvider>
    );
    expect(screen.queryByRole('button', { name: '刪除 丙' })).not.toBeInTheDocument();
    expect(screen.getByTestId('report-submit')).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '丙' }));
    expect(screen.getByRole('button', { name: '刪除 丙' })).toBeInTheDocument();
  });

  it('uses the manual report batch when submission status has been cleared', () => {
    const records: HistoryRecord[] = ['甲', '乙'].map((suspect_id, batch_order) => ({
      record_id: `manual-${batch_order}`,
      suspect_id,
      batch_id: 'manual-batch',
      batch_order,
      batch_phase: 'manual',
      submission_state: 'awaiting_manual',
      server: 'Gamania',
      map_name: '弓箭手村',
      note: '共用說明',
      evidence_url: 'https://example.com/evidence',
      media_path: 'C:/test.mp4',
      media_type: 'video',
      media_available: true,
    }));

    render(
      <ToastProvider>
        <ReportFlowModal
          stage="form"
          config={TEST_CONFIG}
          history={records}
          initialRecord={null}
          manualReport={records[0]}
          onClose={vi.fn()}
          onUpdateWhitelist={vi.fn()}
          onSubmitReport={vi.fn()}
          onOpenReportPage={vi.fn()}
          onConfirmManual={vi.fn()}
        />
      </ToastProvider>
    );

    expect(document.querySelector('.report-mode-description')).toHaveTextContent(
      '本批已完成 0 / 2 人；目前處理 甲'
    );
  });

  it('reuses a batch id carried by a failed submission status', async () => {
    const submit = vi.fn();
    const records: HistoryRecord[] = [
      {
        record_id: 'failed-batch-1',
        suspect_id: '甲',
        batch_id: 'failed-batch',
        batch_order: 0,
        batch_phase: 'draft',
        submission_state: 'draft',
        media_path: 'C:/test.mp4',
        media_type: 'video',
      },
    ];

    render(
      <ToastProvider>
        <ReportFlowModal
          stage="form"
          config={TEST_CONFIG}
          history={[]}
          initialRecord={null}
          submissionStatus={{
            step: 'failed',
            status: 'error',
            message: '送出失敗',
            batch_id: 'failed-batch',
            records,
          }}
          ocrResults={evidence}
          onClose={vi.fn()}
          onUpdateWhitelist={vi.fn()}
          onSubmitReport={submit}
        />
      </ToastProvider>
    );

    fireEvent.click(screen.getByTestId('report-submit'));
    await waitFor(() =>
      expect(submit).toHaveBeenCalledWith(expect.objectContaining({ batch_id: 'failed-batch' }))
    );
  });
});
