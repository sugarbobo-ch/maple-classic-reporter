import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import App from '../src/App';
import { dispatchPyWebViewEvent } from '../src/hooks/usePyWebViewEvents';
import { ToastProvider } from '../src/components/ui';
import { TEST_CONFIG, installMockPyWebView } from './mockPyWebViewApi';

describe('App submission workflow', () => {
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
