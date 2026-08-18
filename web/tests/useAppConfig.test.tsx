import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import useAppConfig from '../src/hooks/useAppConfig';
import { TEST_CONFIG, installMockPyWebView } from './mockPyWebViewApi';

describe('useAppConfig persistence boundary', () => {
  it('reloads backend values when saving a switch fails', async () => {
    const backendConfig = { ...TEST_CONFIG, ocr_autofill_map: true };
    const saveConfigKey = vi.fn().mockResolvedValue(false);
    installMockPyWebView(
      {
        get_initial_data: vi.fn().mockResolvedValue({ config: backendConfig }),
        save_config_key: saveConfigKey,
      },
      { config: backendConfig }
    );

    const { result } = renderHook(() => useAppConfig());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.updateConfig('ocr_autofill_map', false);
    });

    expect(saveConfigKey).toHaveBeenCalledWith('ocr_autofill_map', false);
    expect(result.current.config.ocr_autofill_map).toBe(true);
    expect(result.current.saveError).toBeTruthy();
  });
});
