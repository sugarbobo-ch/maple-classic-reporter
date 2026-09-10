import { useState } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import SuspectTags from '../src/components/report-flow/SuspectTags';

function Harness() {
  const [names, setNames] = useState<string[]>([]);
  const [input, setInput] = useState('');
  return (
    <SuspectTags names={names} input={input} onNamesChange={setNames} onInputChange={setInput} />
  );
}

describe('suspect name tags', () => {
  it('splits mixed pasted separators, removes duplicates, and supports removal and clear', () => {
    render(<Harness />);
    const input = screen.getByRole('textbox', { name: '疑似角色 ID' });
    fireEvent.paste(input, { clipboardData: { getData: () => '甲 乙　丙,丁，戊\n己\r\n甲,, ' } });
    expect(screen.getByRole('status')).toHaveTextContent('已加入 6 人');
    fireEvent.click(screen.getByRole('button', { name: '刪除 丙' }));
    expect(screen.getByRole('status')).toHaveTextContent('已加入 5 人');
    fireEvent.change(input, { target: { value: '未完成' } });
    fireEvent.click(screen.getByRole('button', { name: '全部刪除' }));
    expect(input).toHaveValue('');
    expect(screen.getByRole('status')).toHaveTextContent('已加入 0 人');
  });

  it.each([' ', '　', ',', '，', 'Enter'])(
    'commits a name with %s without submitting a form',
    (key) => {
      render(<Harness />);
      const input = screen.getByRole('textbox', { name: '疑似角色 ID' });
      fireEvent.change(input, { target: { value: '名字' } });
      fireEvent.keyDown(input, { key });
      expect(screen.getByRole('button', { name: '刪除 名字' })).toBeInTheDocument();
      expect(input).toHaveValue('');
    }
  );

  it('does not tokenize while the IME is composing', () => {
    render(<Harness />);
    const input = screen.getByRole('textbox', { name: '疑似角色 ID' });
    fireEvent.compositionStart(input);
    fireEvent.change(input, { target: { value: '中文 名字' } });
    fireEvent.keyDown(input, { key: 'Enter', isComposing: true });
    expect(screen.getByRole('status')).toHaveTextContent('已加入 0 人');
    fireEvent.change(input, { target: { value: '中文名字' } });
    fireEvent.compositionEnd(input, { data: '中文名字' });
    expect(screen.getByRole('status')).toHaveTextContent('已加入 0 人');
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(screen.getByRole('button', { name: '刪除 中文名字' })).toBeInTheDocument();
  });

  it('commits the current name when the input loses focus', () => {
    render(<Harness />);
    const input = screen.getByRole('textbox', { name: '疑似角色 ID' });

    fireEvent.change(input, { target: { value: '失焦玩家' } });
    fireEvent.blur(input);

    expect(screen.getByRole('button', { name: '刪除 失焦玩家' })).toBeInTheDocument();
    expect(input).toHaveValue('');
  });
});
