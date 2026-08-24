import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import QuickLinksTab from '../src/components/settings/QuickLinksTab';
import type { QuickLinkItem } from '../src/types';

const link: QuickLinkItem = {
  id: 'official-main',
  title: '新楓之谷官網',
  url: 'https://example.com',
  icon: 'Globe',
};

describe('QuickLinksTab destructive action', () => {
  it('requires confirmation before deleting a quick link', () => {
    const onDeleteQuickLink = vi.fn();

    render(
      <QuickLinksTab
        quickLinks={[link]}
        draggedIndex={null}
        dragOverIndex={null}
        onOpenAddModal={vi.fn()}
        onOpenEditModal={vi.fn()}
        onDeleteQuickLink={onDeleteQuickLink}
        onMoveQuickLink={vi.fn()}
        onDragStart={vi.fn()}
        onDragOver={vi.fn()}
        onDrop={vi.fn()}
        onDragEnd={vi.fn()}
      />
    );

    const deleteButton = screen.getByRole('button', { name: '刪除' });
    expect(deleteButton).toHaveClass('ui-btn-ghost');
    fireEvent.click(deleteButton);

    expect(screen.getByRole('dialog', { name: '刪除快捷連結？' })).toBeInTheDocument();
    expect(onDeleteQuickLink).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: '刪除快捷連結' }));
    expect(onDeleteQuickLink).toHaveBeenCalledWith('official-main');
  });
});
