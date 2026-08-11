import { describe, expect, it } from 'vitest';
import { batchRowToRequest, parseBatchFile } from './batch-parser';

const header = 'review_id,user_id,prod_id,rating,date,text';

describe('batch parser', () => {
  it('parses quoted CSV content and Chinese text', () => {
    const result = parseBatchFile(`${header}\nREV-1,USER-1,PROD-1,5,2026-08-11T10:00:00+08:00,"包装完好, 配送及时"`);
    expect(result.fileErrors).toEqual([]);
    expect(result.rows).toHaveLength(1);
    expect(result.rows[0].text).toBe('包装完好, 配送及时');
    expect(result.rows[0].errors).toEqual([]);
  });

  it('automatically parses TSV files', () => {
    const result = parseBatchFile('review_id\tuser_id\tprod_id\trating\tdate\ttext\nR-1\tU-1\tP-1\t4\t2026-08-11T10:00:00Z\t内容正常');
    expect(result.rows[0].user_id).toBe('U-1');
    expect(result.rows[0].errors).toEqual([]);
  });

  it('reports missing headers', () => {
    const result = parseBatchFile('user_id,prod_id,rating,date,text\nU-1,P-1,5,2026-08-11T10:00:00Z,评论');
    expect(result.rows).toEqual([]);
    expect(result.fileErrors[0]).toContain('review_id');
  });

  it('reports invalid dates and duplicate review ids', () => {
    const result = parseBatchFile(`${header}\nR-1,U-1,P-1,5,bad,评论一\nR-1,U-2,P-2,4,2026-08-11T10:00:00Z,评论二`);
    expect(result.rows[0].errors).toContain('日期格式无效');
    expect(result.rows[0].errors).toContain('评论 ID 在文件内重复');
    expect(result.rows[1].errors).toContain('评论 ID 在文件内重复');
  });

  it('rejects files over one thousand rows', () => {
    const lines = Array.from({ length: 1001 }, (_, index) => `R-${index},U-${index},P-${index},5,2026-08-11T10:00:00Z,评论`).join('\n');
    const result = parseBatchFile(`${header}\n${lines}`);
    expect(result.rows).toEqual([]);
    expect(result.fileErrors).toContain('单次最多导入 1000 条评论');
  });

  it('normalizes a valid row to the API contract with empty history', () => {
    const row = parseBatchFile(`${header}\n,U-1,P-1,4.5,2026-08-11T10:00:00+08:00,评论`).rows[0];
    const request = batchRowToRequest(row);
    expect(request.review_id).toBeUndefined();
    expect(request.rating).toBe(4.5);
    expect(request.behavior_history).toEqual([]);
    expect(request.date).toBe('2026-08-11T02:00:00.000Z');
  });
});
