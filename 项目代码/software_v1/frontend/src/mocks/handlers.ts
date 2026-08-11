import { http, HttpResponse } from 'msw';
import type {
  BatchDetectionRequest,
  DetectionSubmitResponse,
  DetectionRecordItem,
  DetectionRecordListResponse,
  SingleDetectionRequest,
  SingleDetectionResponse,
  TaskStatusResponse,
} from '../types';

let resultSequence = 1001;
type MockTask = { polls: number; total: number; outcome: 'success' | 'partial' | 'failed'; createdAt: string };
const batchTasks = new Map<string, MockTask>();
const authenticityCycle = ['real', 'fake', 'real', 'fake'] as const;
const semanticCycle = ['real', 'misleading', 'advertising', 'exaggerated'] as const;
const behaviorCycle = ['insufficient_evidence', 'review_manipulation', 'normal', 'bot_like'] as const;
const actionCycle = ['keep', 'review', 'keep', 'block'] as const;
const riskCycle = ['real', 'language_fake', 'real', 'language_behavior_composite'] as const;
const recordTexts = ['包装完好，商品与描述一致', '宣传内容与实际体验存在差异', '活动期间重复出现相似推荐语', '短时间内集中发布极端评分'];
const mockRecords: DetectionRecordItem[] = Array.from({ length: 26 }, (_, index) => {
  const group = index % 4;
  const day = 11 - Math.floor(index / 4);
  return {
    result_id: 3001 + index,
    task_id: `00000000-0000-4000-8000-${String(index + 1).padStart(12, '0')}`,
    review_id: `REV-202608-${String(index + 1).padStart(3, '0')}`,
    user_key: `U-${String(7421 + index * 37).padStart(6, '0')}`,
    product_id: `PROD-${String((index % 8) + 1).padStart(3, '0')}`,
    text_excerpt: recordTexts[group],
    authenticity: authenticityCycle[group],
    confidence: Number((0.73 + (index % 7) * 0.03).toFixed(2)),
    semantic_type: semanticCycle[group],
    behavior_type: behaviorCycle[group],
    risk_source: riskCycle[group],
    action: actionCycle[group],
    model_version: 'mock-v1.0.0',
    created_at: `2026-08-${String(day).padStart(2, '0')}T${String(9 + (index % 8)).padStart(2, '0')}:20:00+08:00`,
  };
});

export const handlers = [
  http.post('/api/v1/auth/login', async ({ request }) => {
    const payload = await request.json() as { username: string; password: string };
    if (!payload.username || payload.password !== 'demo') return HttpResponse.json({ detail: '用户名或密码错误' }, { status: 401 });
    return HttpResponse.json({ user_id: 1, username: payload.username, role: 'reviewer', access_token: 'mock-access-token', token_type: 'bearer', expires_at: new Date(Date.now() + 1800000).toISOString() });
  }),
  http.get('/api/v1/results', ({ request }) => {
    const url = new URL(request.url);
    const page = Math.max(1, Number(url.searchParams.get('page') ?? 1));
    const pageSize = Math.min(100, Math.max(1, Number(url.searchParams.get('page_size') ?? 10)));
    const keyword = (url.searchParams.get('keyword') ?? '').trim().toLowerCase();
    const authenticity = url.searchParams.get('authenticity');
    const action = url.searchParams.get('action');
    const dateFrom = url.searchParams.get('date_from');
    const dateTo = url.searchParams.get('date_to');
    const filtered = mockRecords.filter((item) => {
      const searchable = `${item.review_id ?? ''} ${item.user_key} ${item.product_id} ${item.text_excerpt}`.toLowerCase();
      const day = item.created_at.slice(0, 10);
      return (!keyword || searchable.includes(keyword))
        && (!authenticity || item.authenticity === authenticity)
        && (!action || item.action === action)
        && (!dateFrom || day >= dateFrom)
        && (!dateTo || day <= dateTo);
    });
    const start = (page - 1) * pageSize;
    const response: DetectionRecordListResponse = {
      items: filtered.slice(start, start + pageSize),
      total: filtered.length,
      page,
      page_size: pageSize,
    };
    return HttpResponse.json(response);
  }),
  http.post('/api/v1/detections/batch', async ({ request }) => {
    const payload = await request.json() as BatchDetectionRequest;
    if (payload.items.some((item) => item.text.toLowerCase().includes('[503]'))) {
      return HttpResponse.json({ detail: '批量模型服务暂不可用（模拟）' }, { status: 503 });
    }
    const taskId = crypto.randomUUID();
    const createdAt = new Date().toISOString();
    const outcome = payload.items.some((item) => item.text.toLowerCase().includes('[failed]'))
      ? 'failed'
      : payload.items.some((item) => item.text.toLowerCase().includes('[partial]')) ? 'partial' : 'success';
    batchTasks.set(taskId, { polls: 0, total: payload.items.length, outcome, createdAt });
    const response: DetectionSubmitResponse = { task_id: taskId, status: 'pending', created_at: createdAt };
    return HttpResponse.json(response, { status: 202 });
  }),
  http.get('/api/v1/detections/:taskId', ({ params }) => {
    const taskId = String(params.taskId);
    const task = batchTasks.get(taskId);
    if (!task) return HttpResponse.json({ detail: 'task not found' }, { status: 404 });
    task.polls += 1;
    const running = task.polls < 2;
    const failed = running ? 0 : task.outcome === 'failed' ? task.total : task.outcome === 'partial' ? 1 : 0;
    const completed = running ? Math.max(0, Math.floor(task.total / 2)) : task.total - failed;
    const response: TaskStatusResponse = {
      task_id: taskId,
      status: running ? 'running' : task.outcome === 'failed' ? 'failed' : 'succeeded',
      total_count: task.total,
      completed_count: completed,
      failed_count: failed,
      ...(failed ? { error_summary: task.outcome === 'partial' ? 'item 1: 模拟单条处理失败' : '所有条目处理失败（模拟）' } : {}),
      created_at: task.createdAt,
      started_at: task.createdAt,
      ...(running ? {} : { finished_at: new Date().toISOString() }),
    };
    return HttpResponse.json(response);
  }),
  http.post('/api/v1/detections/single', async ({ request }) => {
    const payload = await request.json() as SingleDetectionRequest;
    if (payload.text.toLowerCase().includes('[503]')) {
      return HttpResponse.json({ detail: '模型服务暂不可用（模拟）' }, { status: 503 });
    }
    if (payload.text.toLowerCase().includes('[422]')) {
      return HttpResponse.json({ detail: [{ msg: '评论文本触发模拟校验错误' }] }, { status: 422 });
    }
    const hasHistory = Boolean(payload.behavior_history?.length);
    const response: SingleDetectionResponse = {
      task: {
        task_id: crypto.randomUUID(),
        status: 'succeeded',
        created_at: new Date().toISOString(),
      },
      result: {
        result_id: resultSequence++,
        review_id: payload.review_id,
        authenticity: hasHistory ? 'fake' : 'real',
        confidence: hasHistory ? 0.86 : 0.91,
        semantic_type: hasHistory ? 'misleading' : 'real',
        behavior_type: hasHistory ? 'review_manipulation' : 'insufficient_evidence',
        risk_source: hasHistory ? 'language_behavior_composite' : 'real',
        action: hasHistory ? 'review' : 'keep',
        model_version: 'mock-v1.0.0',
      },
    };
    return HttpResponse.json(response, { status: 202 });
  }),
];
