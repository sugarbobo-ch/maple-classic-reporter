import { describe, expect, it, vi } from 'vitest';
import { createHistoryBridge, createReporterBridge } from '../src/bridge/reporterBridge';
import { createMockPyWebViewApi } from './mockPyWebViewApi';

describe('ReporterBridge history seam', () => {
  it('maps the typed history interface to the desktop transport', async () => {
    const transport = {
      get_history: vi.fn().mockResolvedValue([{ record_id: 'history-1' }]),
      clear_history: vi.fn().mockResolvedValue(true),
      cleanup_history_evidence: vi.fn().mockResolvedValue({
        success: true,
        cleaned_record_ids: ['history-1'],
      }),
      delete_history_entries: vi.fn().mockResolvedValue({
        success: true,
        deleted_record_ids: ['history-1'],
      }),
    };
    const bridge = createHistoryBridge(transport);

    await expect(bridge.load()).resolves.toEqual([{ record_id: 'history-1' }]);
    await expect(bridge.cleanupEvidence(['history-1'], ['local'])).resolves.toMatchObject({
      success: true,
    });
    await expect(bridge.deleteEntries(['history-1'], [])).resolves.toMatchObject({
      success: true,
    });

    expect(transport.get_history).toHaveBeenCalledOnce();
    expect(transport.cleanup_history_evidence).toHaveBeenCalledWith(['history-1'], ['local']);
    expect(transport.delete_history_entries).toHaveBeenCalledWith(['history-1'], []);
  });

  it('exposes grouped capture and window interfaces through the full adapter', async () => {
    const transport = createMockPyWebViewApi();
    const bridge = createReporterBridge(transport);

    await bridge.capture.replayStatus();
    await bridge.window.toggleMaximized();

    expect(transport.get_replay_status).toHaveBeenCalledOnce();
    expect(transport.toggle_window_maximized).toHaveBeenCalledOnce();
  });
});
