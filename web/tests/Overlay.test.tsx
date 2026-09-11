import { act, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import Overlay from '../src/components/ui/Overlay';

describe('Overlay focus management', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('keeps focus in the text field when the close callback changes', async () => {
    vi.spyOn(HTMLElement.prototype, 'getClientRects').mockReturnValue({ length: 1 } as DOMRectList);

    const firstOnClose = vi.fn();
    const { rerender } = render(
      <Overlay isOpen onClose={firstOnClose}>
        <button type="button">Close</button>
        <input aria-label="Report note" />
      </Overlay>
    );

    const closeButton = screen.getByRole('button', { name: 'Close' });
    const input = screen.getByRole('textbox', { name: 'Report note' });
    await waitFor(() => expect(closeButton).toHaveFocus());

    input.focus();
    expect(input).toHaveFocus();

    rerender(
      <Overlay isOpen onClose={vi.fn()}>
        <button type="button">Close</button>
        <input aria-label="Report note" />
      </Overlay>
    );

    await act(async () => {
      await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
    });

    expect(input).toHaveFocus();
  });
});
