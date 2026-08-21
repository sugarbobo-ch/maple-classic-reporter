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
  it('renders update icon button and triggers onOpenUpdateDetails on click', () => {
    const openDetails = vi.fn();
    const { rerender } = render(
      <Header {...baseProps} updateStatus={status('available')} onOpenUpdateDetails={openDetails} />
    );

    const updateBtn = screen.getByRole('button', { name: /有可用更新/ });
    expect(updateBtn).toBeInTheDocument();
    fireEvent.click(updateBtn);
    expect(openDetails).toHaveBeenCalledTimes(1);

    rerender(
      <Header {...baseProps} updateStatus={status('downloading', 42)} onOpenUpdateDetails={openDetails} />
    );
    expect(screen.getByRole('button', { name: /正在更新/ })).toBeInTheDocument();

    rerender(
      <Header {...baseProps} updateStatus={status('ready')} onOpenUpdateDetails={openDetails} />
    );
    expect(screen.getByRole('button', { name: /已下載完成/ })).toBeInTheDocument();
  });
});
