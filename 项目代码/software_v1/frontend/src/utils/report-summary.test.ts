import { describe, expect, it } from 'vitest';
import { reportSummaryRows } from './report-summary';

describe('reportSummaryRows', () => {
  it('translates counts and distributions and hides audit flags', () => {
    const rows = reportSummaryRows({
      total_count: 31,
      authenticity_distribution: { real: 15, fake: 16 },
      risk_level_distribution: { low: 15, medium: 16 },
      behavior_evidence_distribution: { insufficient: 19, available: 12 },
      data_source: 'real_model',
      is_mock: false,
      is_proxy_task: true,
    });
    expect(rows.map((row) => [row.label, row.value])).toEqual([
      ['任务总数', '31'],
      ['真实性分布', '真实 15 · 疑似虚假 16'],
      ['风险等级分布', '低风险 15 · 中风险 16'],
      ['行为证据分布', '证据不足 19 · 可用 12'],
    ]);
  });

  it('keeps unknown fields visible as-is', () => {
    expect(reportSummaryRows({ new_metric: 3 })).toEqual([{ key: 'new_metric', label: 'new_metric', value: '3' }]);
  });
});
