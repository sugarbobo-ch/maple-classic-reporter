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
    expect(screen.getByText('OCR：Test Map')).toBeInTheDocument();
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
});
