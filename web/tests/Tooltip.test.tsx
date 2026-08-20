import { act, fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import Tooltip from '../src/components/ui/Tooltip';

describe('Tooltip', () => {
  it('can suppress a tooltip for programmatic focus while retaining hover help', () => {
    vi.useFakeTimers();
    render(
      <Tooltip content="關閉" delay={0} showOnFocus={false}>
        <button type="button">關閉視窗</button>
      </Tooltip>
    );

    const button = screen.getByRole('button', { name: '關閉視窗' });
    fireEvent.focus(button);
    act(() => vi.runAllTimers());
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();

    fireEvent.mouseEnter(button);
    act(() => vi.runAllTimers());
    expect(screen.getByRole('tooltip')).toHaveTextContent('關閉');

    vi.useRealTimers();
  });
});
