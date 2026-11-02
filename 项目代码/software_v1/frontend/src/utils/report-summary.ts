// 把任务报告摘要转成中文展示行；审计标记只保留在下载文件里，页面不显示
import { authenticityLabels, evidenceStateLabels } from '../labels';

export type ReportSummary = Record<string, unknown>;

const FIELD_LABELS: Record<string, string> = {
  total_count: '任务总数',
  success_count: '成功条数',
  failed_count: '失败条数',
  authenticity_distribution: '真实性分布',
  risk_level_distribution: '风险等级分布',
  behavior_evidence_distribution: '行为证据分布',
  model_version: '模型版本',
};
const HIDDEN_FIELDS = new Set(['data_source', 'is_mock', 'is_proxy_task']);
const VALUE_LABELS: Record<string, string> = {
  ...authenticityLabels,
  ...evidenceStateLabels,
  low: '低风险', medium: '中风险', high: '高风险',
};

function formatValue(value: unknown): string {
  if (value && typeof value === 'object') {
    const parts = Object.entries(value as Record<string, unknown>).map(([key, count]) => `${VALUE_LABELS[key] ?? key} ${count}`);
    return parts.length ? parts.join(' · ') : '无';
  }
  return String(value);
}

export function reportSummaryRows(summary: ReportSummary): { key: string; label: string; value: string }[] {
  return Object.entries(summary)
    .filter(([key]) => !HIDDEN_FIELDS.has(key))
    .map(([key, value]) => ({ key, label: FIELD_LABELS[key] ?? key, value: formatValue(value) }));
}
