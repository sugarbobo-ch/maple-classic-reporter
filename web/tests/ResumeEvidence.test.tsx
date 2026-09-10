import { act, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ToastProvider } from '../src/components/ui';
import ReportFlowModal from '../src/components/ReportFlowModal';
import { useReportWorkflow } from '../src/hooks/useReportWorkflow';
import { TEST_CONFIG, installMockPyWebView } from './mockPyWebViewApi';
import type { HistoryRecord } from '../src/types';

const draft: HistoryRecord = {
  record_id: 'draft',
  suspect_id: '甲',
  submission_state: 'draft',
  media_path: 'C:/saved.mp4',
  media_type: 'video',
  media_available: true,
};

describe('resume evidence', () => {
  it('rechecks the local file before opening a stale history record', async () => {
    const api = installMockPyWebView({
      get_history: vi.fn().mockResolvedValue([{ ...draft, media_available: false }]),
    });
    const { result } = renderHook(
      () => useReportWorkflow({ config: TEST_CONFIG, onHistoryChange: vi.fn() }),
      { wrapper: ToastProvider }
    );
    await act(() => result.current.handleContinueDraft(draft, false));
    expect(api.get_history).toHaveBeenCalled();
    expect(result.current.modalOpen).toBe(false);
  });

  it('loads the saved local file rather than a stale OCR path', async () => {
    const api = installMockPyWebView();
    render(
      <ToastProvider>
        <ReportFlowModal
          stage="form"
          config={TEST_CONFIG}
          initialRecord={draft}
          ocrResults={{
            suspect_ids: [],
            map_name: '',
            media_path: 'C:/stale.mp4',
            media_type: 'video',
          }}
          onClose={vi.fn()}
          onSubmitReport={vi.fn()}
          onUpdateWhitelist={vi.fn()}
        />
      </ToastProvider>
    );
    await waitFor(() => expect(api.get_media_stream_url).toHaveBeenCalledWith('C:/saved.mp4'));
  });

  it('keeps saved video controls outside the disabled batch form and explains playback errors', async () => {
    installMockPyWebView({
      get_media_stream_url: vi.fn().mockResolvedValue('http://127.0.0.1:1234/media'),
    });
    const record: HistoryRecord = { ...draft, batch_id: 'batch', batch_phase: 'queued' };
    const { baseElement } = render(
      <ToastProvider>
        <ReportFlowModal
          stage="form"
          config={TEST_CONFIG}
          initialRecord={record}
          history={[record]}
          onClose={vi.fn()}
          onSubmitReport={vi.fn()}
          onUpdateWhitelist={vi.fn()}
        />
      </ToastProvider>
    );
    await waitFor(() => expect(baseElement.querySelector('video')).not.toBeNull());
    const video = baseElement.querySelector('video')!;
    expect(video).toHaveAttribute('src', 'http://127.0.0.1:1234/media');
    expect(video).toHaveAttribute('controls');
    expect(video.closest('fieldset[disabled]')).toBeNull();
    expect(screen.getByRole('button', { name: '區段剪輯' })).toBeDisabled();
    fireEvent.error(video);
    expect(screen.getByRole('alert')).toHaveTextContent('影片無法播放');
  });

  it('checks the local file before continuing a manual report', async () => {
    const manual = {
      ...draft,
      submission_state: 'awaiting_manual' as const,
      media_available: false,
    };
    const api = installMockPyWebView({ get_history: vi.fn().mockResolvedValue([manual]) });
    const { result } = renderHook(
      () => useReportWorkflow({ config: TEST_CONFIG, onHistoryChange: vi.fn() }),
      { wrapper: ToastProvider }
    );
    await act(async () => {
      await result.current.handleContinueManual(manual);
    });
    expect(api.get_history).toHaveBeenCalled();
    expect(result.current.modalOpen).toBe(false);
  });

  it('previews a saved video while the manual report assistant is open', async () => {
    const api = installMockPyWebView({
      get_media_stream_url: vi.fn().mockResolvedValue('http://127.0.0.1:1234/manual-media'),
    });
    const manual = {
      ...draft,
      submission_state: 'awaiting_manual' as const,
      media_available: true,
    };
    const { baseElement } = render(
      <ToastProvider>
        <ReportFlowModal
          stage="form"
          config={TEST_CONFIG}
          initialRecord={manual}
          manualReport={manual}
          onClose={vi.fn()}
          onSubmitReport={vi.fn()}
          onUpdateWhitelist={vi.fn()}
          onOpenReportPage={vi.fn()}
          onConfirmManual={vi.fn()}
        />
      </ToastProvider>
    );
    await waitFor(() => expect(api.get_media_stream_url).toHaveBeenCalledWith('C:/saved.mp4'));
    await waitFor(() => expect(baseElement.querySelector('video')).not.toBeNull());
    expect(baseElement.querySelector('video')).toHaveAttribute(
      'src',
      'http://127.0.0.1:1234/manual-media'
    );
  });

  it('retains failed batch identity and records for a retry', async () => {
    const failedRecord: HistoryRecord = {
      record_id: 'failed-batch-1',
      suspect_id: '甲',
      batch_id: 'failed-batch',
      batch_order: 0,
      batch_phase: 'draft',
      submission_state: 'draft',
      media_path: 'C:/saved.mp4',
      media_type: 'video',
    };
    const submitBatch = vi.fn().mockResolvedValue({
      status: 'error',
      message: '送出失敗',
      batch_id: 'failed-batch',
      records: [failedRecord],
    });
    installMockPyWebView({
      submit_report_batch: submitBatch,
      get_history: vi.fn().mockResolvedValue([]),
    });
    const { result } = renderHook(
      () => useReportWorkflow({ config: TEST_CONFIG, onHistoryChange: vi.fn() }),
      { wrapper: ToastProvider }
    );

    await act(async () => {
      await result.current.handleSubmitReport({
        suspect_id: '甲',
        suspects: [{ suspect_id: '甲', note_override: null }],
        file_path: 'C:/saved.mp4',
        map_name: '弓箭手村',
      });
    });

    expect(result.current.submissionStatus).toMatchObject({
      status: 'error',
      batch_id: 'failed-batch',
      records: [failedRecord],
    });
  });
});
