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
});
