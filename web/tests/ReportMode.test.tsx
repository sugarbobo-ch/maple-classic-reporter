import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import ReportFlowModal from '../src/components/ReportFlowModal';
import { ToastProvider } from '../src/components/ui';
import { TEST_CONFIG, installMockPyWebView } from './mockPyWebViewApi';

describe('Report submission mode', () => {
  it('respects a saved manual choice, reveals automatic settings, and scrolls them into view', async () => {
    installMockPyWebView();
    const onPersistSubmissionMode = vi.fn();
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    const scrollIntoView = vi.fn();
    HTMLElement.prototype.scrollIntoView = scrollIntoView;
    render(
      <ToastProvider>
        <ReportFlowModal
          stage="form"
          config={{ ...TEST_CONFIG, report_submission_mode: 'manual' }}
          ocrResults={{ suspect_ids: ['Player'], map_name: '墮落城市', media_path: 'C:\\evidence.mp4', media_type: 'video' }}
          onClose={vi.fn()}
          onSubmitReport={vi.fn()}
          onUpdateWhitelist={vi.fn()}
          onPersistSubmissionMode={onPersistSubmissionMode}
        />
      </ToastProvider>
    );

    const selectorElement = screen.getByTestId('report-mode-selector');
    const modeSelector = within(selectorElement);
    expect(selectorElement).toHaveClass('step-block');
    expect(modeSelector.getByText('6')).toHaveClass('step-number');
    expect(modeSelector.getByText('檢舉方式', { exact: true })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /手動檢舉/ })).toHaveAttribute('aria-checked', 'true');
    expect(screen.queryByRole('switch')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('radio', { name: /自動檢舉/ }));
    expect(onPersistSubmissionMode).toHaveBeenCalledWith('automatic');
    expect(screen.getByRole('switch')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: '自動檢舉設定' })).toBeInTheDocument();
    expect(screen.getByTestId('report-background-setting')).toContainElement(screen.getByRole('switch'));
    await waitFor(() => expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'end' }));

    HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
  });
});
