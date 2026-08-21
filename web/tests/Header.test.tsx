import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import Header from '../src/components/Header';
import { UpdateStatus } from '../src/types';

const baseProps = {
  currentView: 'home' as const,
  setCurrentView: vi.fn(),
  onUpdateTheme: vi.fn(),
};

function status(state: UpdateStatus['state'], progress = 0): UpdateStatus {
  return {
    state,
    current_version: '1.0.0',
    target_version: '1.1.0',
    downloaded_bytes: progress,
    total_bytes: 100,
    progress_percent: progress,
    required_bytes: 100,
    available_bytes: 1000,
  };
}

describe('Header update control', () => {
  it('switches from available update to circular progress and restart action', () => {
    const openDetails = vi.fn();
    const restart = vi.fn();
    const { rerender } = render(
      <Header {...baseProps} updateStatus={status('available')} onOpenUpdateDetails={openDetails} />
    );

    fireEvent.click(screen.getByRole('button', { name: /有可用更新/ }));
    expect(openDetails).toHaveBeenCalledTimes(1);

    rerender(
      <Header {...baseProps} updateStatus={status('downloading', 42)} onOpenUpdateDetails={openDetails} />
    );
    expect(screen.getByRole('progressbar', { name: /正在更新/ })).toHaveAttribute('aria-valuenow', '42');
    expect(screen.getByText('42%')).toBeInTheDocument();

    rerender(
      <Header {...baseProps} updateStatus={status('ready')} onRestartAndApplyUpdate={restart} />
    );
    fireEvent.click(screen.getByRole('button', { name: /重啟應用/ }));
    expect(restart).toHaveBeenCalledTimes(1);
  });

  it('shows a queued restart label while the app is busy', () => {
    render(
      <Header {...baseProps} updateBusy updateStatus={status('ready')} onRestartAndApplyUpdate={vi.fn()} />
    );
    expect(screen.getByRole('button', { name: /目前工作完成後重啟更新/ })).toBeDisabled();
  });
});
