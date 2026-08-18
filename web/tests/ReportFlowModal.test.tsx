import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import ReportFlowModal from '../src/components/ReportFlowModal';
import { ToastProvider } from '../src/components/ui';
import { TEST_CONFIG, installMockPyWebView } from './mockPyWebViewApi';

describe('ReportFlowModal evidence selection', () => {
  it('submits the edited media path instead of the original recording', async () => {
    const trimVideoSegment = vi.fn().mockResolvedValue({
      success: true,
      new_path: 'C:\\test\\edited.mp4',
      duration: 3,
      stream_url: 'http://127.0.0.1:1234/edited',
      original_backup_path: 'C:\\test\\original.backup.mp4',
    });
    const onSubmitReport = vi.fn().mockResolvedValue(undefined);
    const api = installMockPyWebView({
      get_media_stream_url: vi.fn().mockResolvedValue('http://127.0.0.1:1234/original'),
      trim_video_segment: trimVideoSegment,
    });

    render(
      <ToastProvider>
        <ReportFlowModal
          stage="form"
          config={TEST_CONFIG}
          ocrResults={{
            status: 'success',
            suspect_ids: [],
            map_name: 'Test Map',
            media_path: 'C:\\test\\original.mp4',
            media_type: 'video',
          }}
          onClose={vi.fn()}
          onSubmitReport={onSubmitReport}
          onUpdateWhitelist={vi.fn()}
        />
      </ToastProvider>
    );

    await waitFor(() => expect(document.querySelector('video')).toBeTruthy());
    fireEvent.click(screen.getByTestId('video-trim-toggle'));

    const video = document.querySelector('video');
    expect(video).toBeTruthy();
    if (!video) return;

    Object.defineProperty(video, 'duration', { configurable: true, value: 10 });
    fireEvent.loadedMetadata(video);

    Object.defineProperty(video, 'currentTime', { configurable: true, writable: true, value: 2 });
    fireEvent.timeUpdate(video);
    fireEvent.click(screen.getByRole('button', { name: '設定影片剪輯起點' }));

    Object.defineProperty(video, 'currentTime', { configurable: true, writable: true, value: 5 });
    fireEvent.timeUpdate(video);
    fireEvent.click(screen.getByRole('button', { name: '設定影片剪輯終點' }));
    fireEvent.click(screen.getByRole('button', { name: '套用影片剪輯' }));

    await waitFor(() => {
      expect(trimVideoSegment).toHaveBeenCalledWith(
        'C:\\test\\original.mp4',
        2,
        5,
        undefined
      );
    });

    fireEvent.change(screen.getByTestId('report-suspect-id'), {
      target: { value: 'suspect-42' },
    });
    fireEvent.click(screen.getByTestId('report-submit'));

    await waitFor(() => {
      expect(onSubmitReport).toHaveBeenCalledWith(
        expect.objectContaining({
          suspect_id: 'suspect-42',
          map_name: 'Test Map',
          media_path: 'C:\\test\\edited.mp4',
          file_path: 'C:\\test\\edited.mp4',
        })
      );
    });
    expect(api.trim_video_segment).toHaveBeenCalledTimes(1);
  });

  it('triggers onSkipOcr when clicking skip OCR button in progress stage', async () => {
    const onSkipOcr = vi.fn();
    render(
      <ToastProvider>
        <ReportFlowModal
          stage="progress"
          progressPercent={50}
          config={TEST_CONFIG}
          onClose={vi.fn()}
          onSkipOcr={onSkipOcr}
          onSubmitReport={vi.fn()}
          onUpdateWhitelist={vi.fn()}
        />
      </ToastProvider>
    );

    const skipBtn = screen.getByTestId('skip-ocr-button');
    expect(skipBtn).toBeInTheDocument();
    fireEvent.click(skipBtn);
    expect(onSkipOcr).toHaveBeenCalledTimes(1);
  });

  it('puts the OCR map before maps from history and removes note templates', () => {
    render(
      <ToastProvider>
        <ReportFlowModal
          stage="form"
          config={TEST_CONFIG}
          ocrResults={{
            status: 'success',
            suspect_ids: [],
            map_name: 'OCR 地圖',
            ocr_map_name: 'OCR 地圖',
            map_name_source: 'ocr',
            media_path: '',
            media_type: 'image',
          }}
          history={[{ map_name: '歷史地圖 A' }, { map: '歷史地圖 B' }]}
          onClose={vi.fn()}
          onSubmitReport={vi.fn()}
          onUpdateWhitelist={vi.fn()}
        />
      </ToastProvider>
    );

    const suggestions = screen.getByTestId('map-suggestion-group');
    expect(suggestions.firstElementChild).toHaveAttribute('data-testid', 'ocr-map-suggestion');
    expect(screen.getByTestId('history-map-suggestion-0')).toHaveTextContent('歷史地圖 A');
    expect(screen.getByTestId('history-map-suggestion-1')).toHaveTextContent('歷史地圖 B');
    expect(screen.queryByText('常用範本：')).not.toBeInTheDocument();
  });

  it('does not label the default map as OCR when map OCR is disabled', () => {
    render(
      <ToastProvider>
        <ReportFlowModal
          stage="form"
          config={{ ...TEST_CONFIG, default_map: '維多利亞港', ocr_autofill_map: false }}
          ocrResults={{
            status: 'success',
            suspect_ids: [],
            map_name: '維多利亞港',
            map_name_source: 'default',
            media_path: '',
            media_type: 'image',
          }}
          history={[{ map_name: '歷史地圖' }]}
          onClose={vi.fn()}
          onSubmitReport={vi.fn()}
          onUpdateWhitelist={vi.fn()}
        />
      </ToastProvider>
    );

    expect(screen.getByTestId('report-map-name')).toHaveValue('維多利亞港');
    expect(screen.queryByTestId('ocr-map-suggestion')).not.toBeInTheDocument();
    expect(screen.getByTestId('ocr-map-disabled-hint')).toHaveTextContent(
      '尚未啟用地圖 OCR'
    );
    expect(screen.getByTestId('history-map-suggestion-0')).toHaveTextContent('歷史地圖');
  });

  it('orders history maps with the latest first and deduplicates against OCR map', () => {
    render(
      <ToastProvider>
        <ReportFlowModal
          stage="form"
          config={TEST_CONFIG}
          ocrResults={{
            status: 'success',
            suspect_ids: [],
            map_name: '幽靈船',
            ocr_map_name: '幽靈船',
            map_name_source: 'ocr',
            media_path: '',
            media_type: 'image',
          }}
          history={[
            { map_name: '散步路 II', timestamp: '2026-08-01 10:00:00' },
            { map_name: '幽靈船', timestamp: '2026-08-15 12:00:00' },
            { map_name: '地鐵一號線', timestamp: '2026-08-17 18:00:00' },
          ]}
          onClose={vi.fn()}
          onSubmitReport={vi.fn()}
          onUpdateWhitelist={vi.fn()}
        />
      </ToastProvider>
    );

    const ocrChip = screen.getByTestId('ocr-map-suggestion');
    expect(ocrChip).toHaveTextContent('OCR：幽靈船');
    expect(ocrChip).toHaveClass('active');

    // History options should be sorted newest first (地鐵一號線 from 08-17, then 散步路 II from 08-01), with 幽靈船 excluded since it's already the OCR chip
    const hist0 = screen.getByTestId('history-map-suggestion-0');
    expect(hist0).toHaveTextContent('地鐵一號線');
    const hist1 = screen.getByTestId('history-map-suggestion-1');
    expect(hist1).toHaveTextContent('散步路 II');
    expect(screen.queryByTestId('history-map-suggestion-2')).not.toBeInTheDocument();

    // Clicking a history chip should select it
    fireEvent.click(hist0);
    expect(screen.getByTestId('report-map-name')).toHaveValue('地鐵一號線');
    expect(hist0).toHaveClass('active');
    expect(ocrChip).not.toHaveClass('active');
  });

  it('limits history map suggestions to the 5 most recent maps', () => {
    render(
      <ToastProvider>
        <ReportFlowModal
          stage="form"
          config={TEST_CONFIG}
          ocrResults={{
            status: 'success',
            suspect_ids: [],
            map_name: '',
            ocr_map_name: '',
            media_path: '',
            media_type: 'image',
          }}
          history={[
            { map_name: '地圖 7', timestamp: '2026-08-01 10:00:00' },
            { map_name: '地圖 6', timestamp: '2026-08-02 10:00:00' },
            { map_name: '地圖 5', timestamp: '2026-08-03 10:00:00' },
            { map_name: '地圖 4', timestamp: '2026-08-04 10:00:00' },
            { map_name: '地圖 3', timestamp: '2026-08-05 10:00:00' },
            { map_name: '地圖 2', timestamp: '2026-08-06 10:00:00' },
            { map_name: '地圖 1', timestamp: '2026-08-07 10:00:00' },
          ]}
          onClose={vi.fn()}
          onSubmitReport={vi.fn()}
          onUpdateWhitelist={vi.fn()}
        />
      </ToastProvider>
    );

    // Should list latest 5 maps (地圖 1 through 地圖 5)
    expect(screen.getByTestId('history-map-suggestion-0')).toHaveTextContent('地圖 1');
    expect(screen.getByTestId('history-map-suggestion-1')).toHaveTextContent('地圖 2');
    expect(screen.getByTestId('history-map-suggestion-2')).toHaveTextContent('地圖 3');
    expect(screen.getByTestId('history-map-suggestion-3')).toHaveTextContent('地圖 4');
    expect(screen.getByTestId('history-map-suggestion-4')).toHaveTextContent('地圖 5');
    expect(screen.queryByTestId('history-map-suggestion-5')).not.toBeInTheDocument();
  });

  it('auto-fills the top non-whitelisted suspect candidate into the input', () => {
    render(
      <ToastProvider>
        <ReportFlowModal
          stage="form"
          config={{
            ...TEST_CONFIG,
            ocr_autofill_id: true,
            whitelist: ['whitelisted_player'],
          }}
          ocrResults={{
            status: 'success',
            suspect_ids: ['whitelisted_player', 'target_suspect', 'another_player'],
            map_name: '',
            ocr_map_name: '',
            media_path: '',
            media_type: 'video',
          }}
          onClose={vi.fn()}
          onSubmitReport={vi.fn()}
          onUpdateWhitelist={vi.fn()}
        />
      </ToastProvider>
    );

    const suspectInput = screen.getByTestId('report-suspect-id');
    expect(suspectInput).toHaveValue('target_suspect');

    // Clicking another candidate should update the input
    fireEvent.click(screen.getByText('another_player'));
    expect(suspectInput).toHaveValue('another_player');
  });
});

