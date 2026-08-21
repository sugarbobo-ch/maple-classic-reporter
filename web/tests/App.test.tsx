import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import App from '../src/App';
import { dispatchPyWebViewEvent } from '../src/hooks/usePyWebViewEvents';
import { ToastProvider } from '../src/components/ui';
import { TEST_CONFIG, installMockPyWebView } from './mockPyWebViewApi';

describe('App submission workflow', () => {
  it('replaces a stale suspect candidate when a new replay is recognized', async () => {
    const api = installMockPyWebView();

    render(
      <ToastProvider>
        <App />
      </ToastProvider>
    );

    await waitFor(() => expect(api.get_initial_data).toHaveBeenCalled());

    dispatchPyWebViewEvent({
      type: 'OCR_RESULT',
      data: {
        status: 'success',
        suspect_ids: ['old-suspect'],
        map_name: 'Test Map',
        map_name_source: 'ocr',
        media_path: 'C:\\test\\old-replay.mp4',
        media_type: 'video',
      },
    });

    const suspectInput = await screen.findByTestId('report-suspect-id');
    expect(suspectInput).toHaveValue('old-suspect');
    fireEvent.click(screen.getByRole('button', { name: '取消' }));
    await waitFor(() => expect(screen.queryByTestId('report-suspect-id')).not.toBeInTheDocument());

    dispatchPyWebViewEvent({
      type: 'REPLAY_SAVED',
      data: { file_path: 'C:\\test\\new-replay.mp4' },
    });
    await screen.findByText('已儲存循環錄影，正在解析關鍵影格...');

    dispatchPyWebViewEvent({
      type: 'OCR_RESULT',
      data: {
        status: 'success',
        suspect_ids: ['new-suspect'],
        map_name: 'Test Map',
        map_name_source: 'ocr',
        media_path: 'C:\\test\\new-replay.mp4',
        media_type: 'video',
      },
    });

    expect(await screen.findByTestId('report-suspect-id')).toHaveValue('new-suspect');
  });

  it('cancels pending recognition and ignores late OCR events', async () => {
    const cancelOcr = vi.fn().mockResolvedValue(true);
    const api = installMockPyWebView({ cancel_ocr: cancelOcr });

    render(
      <ToastProvider>
        <App />
      </ToastProvider>
    );

    await waitFor(() => expect(api.get_initial_data).toHaveBeenCalled());

    dispatchPyWebViewEvent({
      type: 'REPLAY_SAVED',
      data: { file_path: 'C:\\test\\replay.mp4' },
    });
    await screen.findByText('已儲存循環錄影，正在解析關鍵影格...');

    fireEvent.click(screen.getByRole('button', { name: '取消' }));
    await waitFor(() => expect(cancelOcr).toHaveBeenCalledTimes(1));

    dispatchPyWebViewEvent({
      type: 'OCR_RESULT',
      data: {
        status: 'success',
        suspect_ids: ['late-suspect'],
        map_name: 'Test Map',
        media_path: 'C:\\test\\replay.mp4',
        media_type: 'video',
      },
    });

    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.queryByTestId('report-suspect-id')).not.toBeInTheDocument();
    expect(screen.queryByText('檢舉證據回報表單')).not.toBeInTheDocument();

    dispatchPyWebViewEvent({
      type: 'REPLAY_STATE_CHANGED',
      data: { state: 'ready', duration: 30, total: 30 },
    });
    fireEvent.click(await screen.findByRole('button', { name: '儲存影片片段' }));
    await waitFor(() => expect(api.save_replay).toHaveBeenCalledTimes(1));
  });

  it('persists the background submission mode changed in the report form', async () => {
    const saveConfigKey = vi.fn().mockResolvedValue(true);
    const api = installMockPyWebView({ save_config_key: saveConfigKey });

    render(
      <ToastProvider>
        <App />
      </ToastProvider>
    );

    await waitFor(() => expect(api.get_initial_data).toHaveBeenCalled());

    dispatchPyWebViewEvent({
      type: 'OCR_RESULT',
      data: {
        status: 'success',
        suspect_ids: ['suspect-42'],
        map_name: 'Test Map',
        media_path: 'C:\\test\\replay.mp4',
        media_type: 'video',
      },
    });

    const submissionModeSwitch = await screen.findByRole('switch');
    expect(submissionModeSwitch).toHaveAttribute('aria-checked', 'true');
    fireEvent.click(submissionModeSwitch);

    await waitFor(() => {
      expect(saveConfigKey).toHaveBeenCalledWith('form_submit_headless', false);
    });
    expect(submissionModeSwitch).toHaveAttribute('aria-checked', 'false');

    fireEvent.click(screen.getByRole('button', { name: '取消' }));
    await waitFor(() => expect(screen.queryByRole('switch')).not.toBeInTheDocument());
    dispatchPyWebViewEvent({
      type: 'OCR_RESULT',
      data: {
        status: 'success',
        suspect_ids: ['next-suspect'],
        map_name: 'Test Map',
        media_path: 'C:\\test\\next-replay.mp4',
        media_type: 'video',
      },
    });
    expect(await screen.findByRole('switch')).toHaveAttribute('aria-checked', 'false');
  });

  it('recognizes a paused evidence video frame through the bridge', async () => {
    const recognizeVideoFrame = vi.fn().mockResolvedValue({
      status: 'success',
      suspect_ids: ['frame-player'],
      map_name: 'Test Map',
      map_name_source: 'ocr',
      ocr_map_name: 'Test Map',
      media_path: 'C:\\test\\evidence.mp4',
      media_type: 'video',
    });
    const api = installMockPyWebView({
      recognize_video_frame: recognizeVideoFrame,
      get_media_stream_url: vi.fn().mockResolvedValue('http://127.0.0.1:1234/evidence'),
    });

    render(
      <ToastProvider>
        <App />
      </ToastProvider>
    );

    await waitFor(() => expect(api.get_initial_data).toHaveBeenCalled());
    dispatchPyWebViewEvent({
      type: 'OCR_RESULT',
      data: {
        status: 'success',
        suspect_ids: [],
        map_name: 'Test Map',
        media_path: 'C:\\test\\evidence.mp4',
        media_type: 'video',
      },
    });

    const recognizeButton = await screen.findByTestId('recognize-current-frame-button');
    fireEvent.click(recognizeButton);

    await waitFor(() => {
      expect(recognizeVideoFrame).toHaveBeenCalledWith('C:\\test\\evidence.mp4', 0);
    });
    expect(await screen.findByText('frame-player')).toBeInTheDocument();
  });

  it('keeps the form open and exposes the failure when submission fails', async () => {
    const submitReport = vi.fn().mockResolvedValue({
      status: 'error',
      message: 'submission-failed-in-test',
    });
    const api = installMockPyWebView(
      { submit_report: submitReport },
      {
        config: TEST_CONFIG,
        history: [],
        windows: [],
        audio_devices: [],
        gdrive_authenticated: true,
      }
    );

    render(
      <ToastProvider>
        <App />
      </ToastProvider>
    );

    await waitFor(() => expect(api.get_initial_data).toHaveBeenCalled());

    dispatchPyWebViewEvent({
      type: 'OCR_RESULT',
      data: {
        status: 'success',
        suspect_ids: ['suspect-42'],
        map_name: 'Test Map',
        ocr_map_name: 'Test Map',
        map_name_source: 'ocr',
        media_path: 'C:\\test\\original.mp4',
        media_type: 'video',
      },
    });

    const suspectInput = await screen.findByTestId('report-suspect-id');
    expect(screen.getByTestId('report-map-name')).toHaveValue('Test Map');
    expect(screen.getByText('辨識結果：Test Map')).toBeInTheDocument();
    fireEvent.change(suspectInput, { target: { value: 'suspect-42' } });
    fireEvent.click(screen.getByTestId('report-submit'));

    await waitFor(() => {
      expect(submitReport).toHaveBeenCalledWith(
        expect.objectContaining({
          suspect_id: 'suspect-42',
          file_path: 'C:\\test\\original.mp4',
          upload_destination: 'gdrive',
        })
      );
    });

    expect(await screen.findByRole('alert')).toHaveTextContent('submission-failed-in-test');
    expect(screen.getByTestId('report-submit')).toBeInTheDocument();
  });

  it('gives visible feedback when a manual update check finds no newer release', async () => {
    const checkForUpdates = vi.fn().mockResolvedValue(true);
    const api = installMockPyWebView(
      { check_for_updates: checkForUpdates },
      {
        config: TEST_CONFIG,
        history: [],
        windows: [],
        audio_devices: [],
        gdrive_authenticated: true,
      }
    );

    render(
      <ToastProvider>
        <App />
      </ToastProvider>
    );

    await waitFor(() => expect(api.get_initial_data).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('button', { name: '設定' }));
    fireEvent.click(await screen.findByRole('tab', { name: '關於與更新' }));
    fireEvent.click(screen.getByRole('button', { name: '檢查更新' }));
    expect(checkForUpdates).toHaveBeenCalledWith(true);

    dispatchPyWebViewEvent({
      type: 'UPDATE_STATUS',
      data: {
        state: 'up_to_date',
        current_version: '2.0.0-pre',
        target_version: null,
        downloaded_bytes: 0,
        total_bytes: 0,
        progress_percent: 0,
        required_bytes: 0,
        available_bytes: 0,
      },
    });

    expect(await screen.findByText('目前已是最新版', { selector: '.ui-toast-title-text' })).toBeInTheDocument();
  });
});
