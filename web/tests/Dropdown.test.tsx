import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import Dropdown from '../src/components/ui/Dropdown';

describe('Dropdown layout', () => {
  it('keeps long option labels inside the trigger and viewport width', () => {
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
    expect(menu).not.toHaveClass('compact');
    expect(menu).toHaveStyle({
      minWidth: '0',
      width: '320px',
      maxWidth: 'calc(100vw - 20px)',
    });
    expect(screen.getByRole('option', { name: longLabel })).toHaveAttribute('title', longLabel);

    vi.restoreAllMocks();
  });

  it('uses compact selected-option spacing only for narrow menus', () => {
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
      width: 80,
      height: 36,
      top: 20,
      right: 100,
      bottom: 56,
      left: 20,
      x: 20,
      y: 20,
      toJSON: () => ({}),
    });

    render(
      <Dropdown
        value={20}
        options={[
          { value: 15, label: '15 FPS' },
          { value: 20, label: '20 FPS' },
        ]}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: '20 FPS' }));

    expect(screen.getByRole('listbox')).toHaveClass('compact');
  });

  it('keeps numeric page-size labels readable just above the baseline width', () => {
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
      width: 120,
      height: 36,
      top: 20,
      right: 140,
      bottom: 56,
      left: 20,
      x: 20,
      y: 20,
      toJSON: () => ({}),
    });

    render(
      <Dropdown
        value={100}
        options={[
          { value: 30, label: '30 筆 / 頁' },
          { value: 50, label: '50 筆 / 頁' },
          { value: 100, label: '100 筆 / 頁' },
        ]}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: '100 筆 / 頁' }));

    expect(screen.getByRole('listbox')).toHaveClass('compact');
    expect(screen.getByRole('option', { name: '100 筆 / 頁' })).toBeInTheDocument();

    vi.restoreAllMocks();
  });
});
