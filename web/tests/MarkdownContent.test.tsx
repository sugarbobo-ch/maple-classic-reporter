import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import MarkdownContent from '../src/components/ui/MarkdownContent';

describe('MarkdownContent', () => {
  it('renders GitHub-style Markdown and keeps external links controllable', () => {
    const onOpenLink = vi.fn();

    render(
      <MarkdownContent
        source={
          '# Release notes\n\n- **Safer updates**\n\n[Read the release](https://example.com/release)\n\n<script>alert(1)</script>'
        }
        onOpenLink={onOpenLink}
      />
    );

    expect(screen.getByRole('heading', { name: 'Release notes', level: 3 })).toBeInTheDocument();
    expect(screen.getByRole('list')).toBeInTheDocument();
    expect(screen.getByText('Safer updates')).toBeInTheDocument();

    const link = screen.getByRole('link', { name: 'Read the release' });
    expect(link).toHaveAttribute('target', '_blank');
    fireEvent.click(link);
    expect(onOpenLink).toHaveBeenCalledWith('https://example.com/release');
    expect(document.querySelector('script')).toBeNull();
  });

  it('shows a calm fallback when a release has no notes', () => {
    render(<MarkdownContent source="" />);

    expect(screen.getByText('此版本沒有提供更新說明。')).toBeInTheDocument();
  });
});
