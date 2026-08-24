import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import ReportTab from '../src/components/settings/ReportTab';
import { TEST_CONFIG } from './mockPyWebViewApi';

describe('ReportTab defaults', () => {
  it('places automatic reporting first and keeps the settings copy concise', () => {
    render(<ReportTab config={{ ...TEST_CONFIG, report_submission_mode: undefined }} onUpdateConfig={vi.fn()} />);

    expect(screen.getByText('選擇預設的檢舉方式。送出前仍可更改。')).toBeInTheDocument();
    const choices = screen.getAllByRole('radio');
    expect(choices[0]).toHaveAccessibleName(/自動檢舉/);
    expect(choices[0]).toHaveAttribute('aria-checked', 'true');
    expect(choices.every((choice) => choice.querySelectorAll('svg').length === 1)).toBe(true);
    expect(screen.getByRole('radiogroup')).toHaveClass('settings-choice-list-2');
    expect(screen.getByRole('switch').closest('.report-settings-background-setting')).not.toBeNull();
  });
});
