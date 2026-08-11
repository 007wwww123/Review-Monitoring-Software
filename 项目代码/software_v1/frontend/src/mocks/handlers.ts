import { http, HttpResponse } from 'msw';
import type {
  BatchDetectionRequest,
  DetectionSubmitResponse,
  DetectionRecordItem,
  DetectionRecordListResponse,
  DetectionResultResponse,
  Explanation,
  ReportSummaryResponse,
  ModelVersionResponse,
  EvaluationResponse,
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
    data_source: 'mock',
    is_mock: true,
    is_proxy_task: true,
    created_at: `2026-08-${String(day).padStart(2, '0')}T${String(9 + (index % 8)).padStart(2, '0')}:20:00+08:00`,
  };
});
const mockReports = new Map<number, ReportSummaryResponse>();
let reportSequence = 7001;
const initialMockModels: ModelVersionResponse[] = [
  {
    version: 'mock-v1.0.0', model_name: 'semantic-temporal-gated-fusion', tokenizer_name: 'albert/albert-base-v2',
    config: { max_length: 256, behavior_input_size: 10, behavior_hidden_size: 128, fusion_hidden_size: 256, minimum_history: 1, maximum_history: 30, semantic_labels: ['real', 'misleading', 'exaggerated', 'advertising'], behavior_labels: ['normal', 'review_manipulation', 'crowdturfing', 'bot_like', 'insufficient_evidence'] },
    metrics: null, checkpoint_sha256: 'mock-checkpoint-not-for-production', is_active: true, created_at: '2026-08-01T09:00:00+08:00',
  },
  {
    version: 'mock-v0.9.0', model_name: 'semantic-temporal-gated-fusion', tokenizer_name: 'albert/albert-base-v2',
    config: { max_length: 256, behavior_input_size: 10, behavior_hidden_size: 128, fusion_hidden_size: 256, minimum_history: 1, maximum_history: 30 },
    metrics: null, checkpoint_sha256: 'mock-archived-checkpoint', is_active: false, created_at: '2026-07-15T09:00:00+08:00',
  },
];
let mockModels: ModelVersionResponse[] = initialMockModels.map((item) => ({ ...item }));
let mockRole = 'admin';
const mockEvaluations: EvaluationResponse[] = [
  { report_id: 8101, dataset_name: 'mock-sealed-test', dataset_split: 'test', sample_count: 1200, accuracy: 0.884, precision: 0.872, recall: 0.861, f1: 0.866, auc: 0.921, confusion_matrix: { labels: ['real', 'fake'], matrix: [[548, 52], [87, 513]] }, status: 'success', created_at: '2026-07-28T15:30:00+08:00' },
  { report_id: 8100, dataset_name: 'mock-production-review', dataset_split: 'production_review', sample_count: 240, accuracy: null, precision: null, recall: null, f1: null, auc: null, confusion_matrix: null, status: 'failed', created_at: '2026-07-20T10:00:00+08:00' },
];

function explanationFor(item: DetectionRecordItem): Explanation | null {
  if (item.result_id === 3005) return null;
  const behaviorAvailable = item.behavior_type !== 'insufficient_evidence';
  return {
    schema_version: 'explanation.v1',
    final: { authenticity: item.authenticity, confidence: item.confidence, risk_source: item.risk_source, action: item.action },
    semantic: {
      scores: item.semantic_type === 'real'
        ? { real: 0.82, misleading: 0.08, exaggerated: 0.06, advertising: 0.04 }
        : { real: 0.09, misleading: 0.63, exaggerated: 0.17, advertising: 0.11 },
      selected_type: item.semantic_type,
    },
    behavior: {
      scores: behaviorAvailable
        ? { normal: 0.08, review_manipulation: 0.61, crowdturfing: 0.14, bot_like: 0.17, insufficient_evidence: 0 }
        : { normal: 0, review_manipulation: 0, crowdturfing: 0, bot_like: 0, insufficient_evidence: 1 },
      selected_type: item.behavior_type,
      available: behaviorAvailable,
      history_length: behaviorAvailable ? 12 : 0,
      is_proxy_task: true,
    },
    fusion: {
      semantic_weight: behaviorAvailable ? 0.58 : 1,
      behavior_weight: behaviorAvailable ? 0.42 : 0,
      weight_summary: behaviorAvailable ? '语义与行为证据共同参与融合' : '行为证据不足，当前由语义分支主导',
    },
    evidence: {
      semantic_evidence_state: 'available',
      behavior_evidence_state: behaviorAvailable ? 'available' : 'insufficient',
      calibration_state: 'uncalibrated',
    },
    disclaimers: [
      '门控权重仅为融合权重摘要，不构成因果归因。',
      '细分类分数是未校准的相对匹配度，不代表确定类别。',
      '行为二分类使用评论真假标签作为代理任务，并非独立人工标注真值。',
      '检测结果仅作为辅助审核建议，不替代人工事实认定。',
    ],
  };
}

export const handlers = [
  http.get('/api/v1/health', () => HttpResponse.json({ status: 'ok' })),
  http.get('/api/v1/models', () => {
    mockModels = initialMockModels.map((item) => ({ ...item }));
    return HttpResponse.json(mockModels);
  }),
  http.post('/api/v1/models/:version/activate', ({ params }) => {
    const version = String(params.version);
    const target = mockModels.find((item) => item.version === version);
    if (!target) return HttpResponse.json({ detail: 'model not found' }, { status: 404 });
    mockModels = mockModels.map((item) => ({ ...item, is_active: item.version === version }));
    return HttpResponse.json(mockModels.find((item) => item.version === version));
  }),
  http.post('/api/v1/auth/login', async ({ request }) => {
    const payload = await request.json() as { username: string; password: string };
    if (!payload.username || payload.password !== 'demo') return HttpResponse.json({ detail: '用户名或密码错误' }, { status: 401 });
    mockRole = payload.username === 'admin' ? 'admin' : 'reviewer';
    return HttpResponse.json({ user_id: 1, username: payload.username, role: mockRole, access_token: 'mock-access-token', token_type: 'bearer', expires_at: new Date(Date.now() + 1800000).toISOString() });
  }),
  http.get('/api/v1/auth/me', () => HttpResponse.json({ user_id: 1, username: mockRole === 'admin' ? 'admin' : 'reviewer', display_name: mockRole === 'admin' ? '系统管理员' : '审核用户', role: mockRole, status: 'active', last_login_at: new Date().toISOString() })),
  http.put('/api/v1/auth/password', async ({ request }) => {
    const body = await request.json() as { current_password: string; new_password: string };
    if (body.current_password !== 'demo') return HttpResponse.json({ detail: 'current password is incorrect' }, { status: 400 });
    return new HttpResponse(null, { status: 204 });
  }),
  http.post('/api/v1/auth/logout', () => new HttpResponse(null, { status: 204 })),
  http.post('/api/v1/users', async ({ request }) => {
    if (mockRole !== 'admin') return HttpResponse.json({ detail: 'administrator permission required' }, { status: 403 });
    const body = await request.json() as { username: string; display_name?: string; role: string };
    if (body.username === 'existing') return HttpResponse.json({ detail: 'username already exists' }, { status: 409 });
    return HttpResponse.json({ user_id: 20, username: body.username, display_name: body.display_name ?? null, role: body.role, status: 'active', created_at: new Date().toISOString() }, { status: 201 });
  }),
  http.get('/api/v1/evaluations', () => HttpResponse.json(mockEvaluations)),
  http.get('/api/v1/evaluations/:reportId', ({ params }) => {
    const item = mockEvaluations.find((report) => report.report_id === Number(params.reportId));
    return item ? HttpResponse.json(item) : HttpResponse.json({ detail: 'evaluation not found' }, { status: 404 });
  }),
  http.get('/api/v1/results/:resultId', ({ params }) => {
    const resultId = Number(params.resultId);
    const item = mockRecords.find((record) => record.result_id === resultId);
    if (!item) return HttpResponse.json({ detail: 'result not found' }, { status: 404 });
    const response: DetectionResultResponse = { ...item, review_id: item.review_id ?? null, explanation: explanationFor(item) };
    return HttpResponse.json(response);
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
  http.post('/api/v1/reports', async ({ request }) => {
    const payload = await request.json() as { task_id: string };
    const records = mockRecords.filter((item) => item.task_id === payload.task_id);
    if (!records.length) return HttpResponse.json({ detail: 'task not found' }, { status: 404 });
    const report: ReportSummaryResponse = {
      report_id: reportSequence++,
      task_id: payload.task_id,
      status: 'succeeded',
      summary: { total_count: records.length, success_count: records.length, failed_count: 0 },
      created_at: new Date().toISOString(),
    };
    mockReports.set(report.report_id, report);
    return HttpResponse.json(report);
  }),
  http.get('/api/v1/reports/:reportId/download', ({ params, request }) => {
    const report = mockReports.get(Number(params.reportId));
    if (!report) return HttpResponse.json({ detail: 'report not found' }, { status: 404 });
    const format = new URL(request.url).searchParams.get('format') ?? 'json';
    if (format === 'csv') {
      const rows = Object.entries(report.summary).map(([key, value]) => `${key},${value}`).join('\n');
      return new HttpResponse(`metric,value\n${rows}\n`, { headers: { 'Content-Type': 'text/csv', 'Content-Disposition': `attachment; filename=report-${report.report_id}.csv` } });
    }
    return HttpResponse.json(report.summary, { headers: { 'Content-Disposition': `attachment; filename=report-${report.report_id}.json` } });
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
