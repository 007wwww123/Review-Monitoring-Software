import Papa from 'papaparse';
import type { SingleDetectionRequest } from '../types';

export const BATCH_HEADERS = ['review_id', 'user_id', 'prod_id', 'rating', 'date', 'text'] as const;

export interface BatchPreviewRow {
  rowNumber: number;
  review_id: string;
  user_id: string;
  prod_id: string;
  rating: number | string;
  date: string;
  text: string;
  errors: string[];
}

export interface BatchParseResult {
  rows: BatchPreviewRow[];
  fileErrors: string[];
}

export function validateBatchRows(rows: BatchPreviewRow[]): BatchPreviewRow[] {
  const reviewIds = new Map<string, number>();
  rows.forEach((row) => {
    const id = row.review_id.trim();
    if (id) reviewIds.set(id, (reviewIds.get(id) ?? 0) + 1);
  });
  return rows.map((row) => {
    const errors: string[] = [];
    const rating = Number(row.rating);
    if (row.review_id.trim().length > 100) errors.push('评论 ID 最多 100 个字符');
    if (row.review_id.trim() && (reviewIds.get(row.review_id.trim()) ?? 0) > 1) errors.push('评论 ID 在文件内重复');
    if (!row.user_id.trim()) errors.push('用户 ID 不能为空');
    else if (row.user_id.trim().length > 128) errors.push('用户 ID 最多 128 个字符');
    if (!row.prod_id.trim()) errors.push('商品 ID 不能为空');
    else if (row.prod_id.trim().length > 128) errors.push('商品 ID 最多 128 个字符');
    if (!Number.isFinite(rating) || rating < 1 || rating > 5) errors.push('评分范围为 1 到 5');
    if (!row.date.trim() || Number.isNaN(Date.parse(row.date))) errors.push('日期格式无效');
    if (!row.text.trim()) errors.push('评论文本不能为空');
    else if (row.text.trim().length > 10000) errors.push('评论文本最多 10000 个字符');
    return { ...row, errors };
  });
}

export function parseBatchFile(content: string): BatchParseResult {
  const parsed = Papa.parse<Record<string, string>>(content, {
    header: true,
    skipEmptyLines: 'greedy',
    transformHeader: (header) => header.trim().replace(/^\uFEFF/, ''),
  });
  const fields = parsed.meta.fields ?? [];
  const missing = BATCH_HEADERS.filter((header) => !fields.includes(header));
  const fileErrors = parsed.errors.map((error) => `第 ${error.row !== undefined ? error.row + 2 : '?'} 行：${error.message}`);
  if (missing.length) fileErrors.unshift(`缺少表头：${missing.join('、')}`);
  if (parsed.data.length > 1000) fileErrors.unshift('单次最多导入 1000 条评论');
  if (!parsed.data.length) fileErrors.unshift('文件中没有可用数据');
  if (missing.length || parsed.data.length > 1000) return { rows: [], fileErrors };
  const rows = parsed.data.map((source, index): BatchPreviewRow => ({
    rowNumber: index + 2,
    review_id: source.review_id?.trim() ?? '',
    user_id: source.user_id?.trim() ?? '',
    prod_id: source.prod_id?.trim() ?? '',
    rating: source.rating?.trim() ?? '',
    date: source.date?.trim() ?? '',
    text: source.text?.trim() ?? '',
    errors: [],
  }));
  return { rows: validateBatchRows(rows), fileErrors };
}

export function batchRowToRequest(row: BatchPreviewRow): SingleDetectionRequest {
  return {
    ...(row.review_id.trim() ? { review_id: row.review_id.trim() } : {}),
    user_id: row.user_id.trim(),
    prod_id: row.prod_id.trim(),
    rating: Number(row.rating),
    date: new Date(row.date).toISOString(),
    text: row.text.trim(),
    behavior_history: [],
  };
}
