import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import Dropdown from '../src/components/ui/Dropdown';

describe('Dropdown layout', () => {
  it('lets option content size the menu while keeping the trigger width as a floor', () => {
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
      width: 320,
      height: 36,
      top: 20,
      right: 340,
      bottom: 56,
      left: 20,
      x: 20,
      y: 20,
      toJSON: () => ({}),
    });

    const longLabel = '0007 - (C108) [MIGNON WORKS] 非常長的視窗名稱';
    render(
      <Dropdown
        value="maple"
        options={[
          { value: 'maple', label: '新楓之谷：經典版' },
          { value: 'long', label: longLabel },
        ]}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: '新楓之谷：經典版' }));

    const menu = screen.getByRole('listbox');
    expect(menu).toHaveStyle({
      minWidth: '320px',
      width: 'max-content',
      maxWidth: 'calc(100vw - 20px)',
    });
    expect(screen.getByRole('option', { name: longLabel })).toHaveAttribute('title', longLabel);

    vi.restoreAllMocks();
  });
});
