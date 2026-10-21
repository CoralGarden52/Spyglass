import { fireEvent, render, screen, within } from '@testing-library/react';
import { vi } from 'vitest';
import type { components } from '../../types/api.generated';
import { SourceCards } from './SourceCards';

const sources: components['schemas']['SearchSourceView'][] = [
  {
    evidence_id: 'controlled-valid',
    validity_status: 'valid',
    result: {
      title: 'Controlled public documentation',
      url: 'https://docs.example.org/page',
      snippet: 'Short UI summary for the user.',
      summary: 'Model-only long evidence context.',
      content: '',
      rerank_score: 2.4,
      authority: 4,
      date: '2026-10-20T09:00:00Z',
      site_name: 'Controlled documentation',
      site_icon: 'https://docs.example.org/favicon.ico',
      source_confidence: 0.86,
      confidence_policy: 'controlled',
      high_quality: true,
      high_authority: true,
    },
  },
  {
    evidence_id: 'controlled-rejected',
    validity_status: 'rejected',
    result: {
      title: 'Controlled excluded candidate',
      url: 'https://community.example.org/review',
      snippet: 'Unrelated candidate summary.',
      summary: '',
      content: '',
      rerank_score: 0.4,
      authority: -1,
      date: null,
      site_name: null,
      site_icon: null,
      source_confidence: null,
      confidence_policy: 'controlled',
      high_quality: false,
      high_authority: false,
    },
  },
];

test('cards show native metadata, safe links and evidence action without substituting long summary', () => {
  const open = vi.fn();
  const { container } = render(<SourceCards sources={sources} onEvidence={open} />);
  const card = screen
    .getByRole('link', { name: 'Controlled public documentation' })
    .closest('article')!;
  expect(within(card).getByText('Short UI summary for the user.')).toBeInTheDocument();
  expect(within(card).getByText('2026-10-20 · UTC')).toBeInTheDocument();
  expect(screen.queryByText('Model-only long evidence context.')).not.toBeInTheDocument();
  expect(within(card).getByRole('link')).toHaveAttribute('href', sources[0].result.url);
  expect(within(card).getByRole('link')).toHaveAttribute('rel', 'noopener noreferrer');
  fireEvent.click(within(card).getByRole('button', { name: /查看证据/ }));
  expect(open).toHaveBeenCalledWith('controlled-valid');
  expect(screen.getByText('发布时间未知')).toBeInTheDocument();
  fireEvent.error(container.querySelector('img')!);
  expect(container.querySelectorAll('img')).toHaveLength(0);
  expect(screen.getAllByLabelText('默认站点图标')).toHaveLength(2);
});

test('status and keyword filters work together and can reset an empty result', () => {
  const { container } = render(<SourceCards sources={sources} onEvidence={vi.fn()} />);
  expect(container.querySelectorAll('.source-card')).toHaveLength(2);
  fireEvent.click(screen.getByRole('button', { name: /已排除/ }));
  expect(container.querySelectorAll('.source-card')).toHaveLength(1);
  expect(screen.getByRole('link')).toHaveAttribute('href', sources[1].result.url);
  fireEvent.change(screen.getByRole('textbox', { name: '搜索来源' }), {
    target: { value: 'docs.example.org' },
  });
  expect(screen.getByText('没有匹配的来源')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: '重置筛选' }));
  expect(container.querySelectorAll('.source-card')).toHaveLength(2);
  fireEvent.change(screen.getByRole('textbox', { name: '搜索来源' }), {
    target: { value: 'DOCUMENTATION' },
  });
  expect(container.querySelectorAll('.source-card')).toHaveLength(1);
});
