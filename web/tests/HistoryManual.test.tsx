import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import HistoryView from '../src/components/HistoryView';
import { ToastProvider } from '../src/components/ui';

describe('HistoryView manual reports', () => {
  it('keeps pending manual reports out of sanction checks and lets users continue them', () => {
    const onContinueManual = vi.fn();
    render(
      <ToastProvider>
        <HistoryView
          history={[{
            record_id: 'manual-1',
            time: '2026-08-24 12:00:00',
            suspect_id: 'ManualPlayer',
            submission_state: 'awaiting_manual',
            evidence_url: 'https://example.com/evidence',
          }]}
          onBack={vi.fn()}
          onOpenUrl={vi.fn()}
          onCheckSanctions={vi.fn()}
          onContinueManual={onContinueManual}
        />
      </ToastProvider>
    );

    expect(screen.getByText('待手動檢舉')).toBeInTheDocument();
    expect(screen.getByTestId('check-sanction-status')).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '繼續手動檢舉' }));
    expect(onContinueManual).toHaveBeenCalledWith(expect.objectContaining({ record_id: 'manual-1' }));
  });
});
