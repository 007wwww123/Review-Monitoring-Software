import type {
  BatchDetectionRequest,
  DetectionSubmitResponse,
  DetectionRecordListResponse,
  DetectionRecordQuery,
  DetectionResultResponse,
  ReportSummaryResponse,
  SingleDetectionRequest,
  SingleDetectionResponse,
  TaskStatusResponse,
} from '../types';
import type { LoginRequest, LoginResponse } from '../types/auth';
import { clearSession, getToken, saveSession } from '../auth';

const apiBase = import.meta.env.VITE_API_BASE_URL ?? '';

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function parseError(response: Response): Promise<string> {
  try {
    const body = await response.json() as { detail?: string | Array<{ msg?: string }> };
    if (typeof body.detail === 'string') return body.detail;
    if (Array.isArray(body.detail)) return body.detail.map((item) => item.msg ?? '参数错误').join('；');
  } catch {
    // Fall through to the HTTP status when the response is not JSON.
  }
  return `请求失败（${response.status}）`;
}

/* Authenticated request wrapper is shared by all API calls. */
export async function submitSingleDetection(payload: SingleDetectionRequest): Promise<SingleDetectionResponse> {
  return requestJson('/api/v1/detections/single', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
/*
  let response: Response;
  try {
    response = await fetch(`${apiBase}/api/v1/detections/single`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new ApiError('无法连接检测服务，请检查服务是否已启动。', 0);
  }
  if (!response.ok) throw new ApiError(await parseError(response), response.status);
  return response.json() as Promise<SingleDetectionResponse>;*/
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    const headers = new Headers(init?.headers);
    if (!headers.has('Content-Type') && init?.body) headers.set('Content-Type', 'application/json');
    const token = getToken();
    if (token) headers.set('Authorization', `Bearer ${token}`);
    response = await fetch(`${apiBase}${url}`, { ...init, headers });
  } catch {
    throw new ApiError('无法连接检测服务，请检查服务是否已启动。', 0);
  }
  if (response.status === 401) { clearSession(); window.dispatchEvent(new Event('auth:expired')); }
  if (!response.ok) throw new ApiError(await parseError(response), response.status);
  return response.json() as Promise<T>;
}

async function requestBlob(url: string): Promise<Blob> {
  let response: Response;
  try {
    const headers = new Headers();
    const token = getToken();
    if (token) headers.set('Authorization', `Bearer ${token}`);
    response = await fetch(`${apiBase}${url}`, { headers });
  } catch {
    throw new ApiError('无法连接检测服务，请检查服务是否已启动。', 0);
  }
  if (response.status === 401) { clearSession(); window.dispatchEvent(new Event('auth:expired')); }
  if (!response.ok) throw new ApiError(await parseError(response), response.status);
  return response.blob();
}

export async function login(payload: LoginRequest): Promise<LoginResponse> {
  const session = await requestJson<LoginResponse>('/api/v1/auth/login', { method: 'POST', body: JSON.stringify(payload) });
  saveSession(session); return session;
}

export function submitBatchDetection(payload: BatchDetectionRequest): Promise<DetectionSubmitResponse> {
  return requestJson('/api/v1/detections/batch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export function getDetectionTask(taskId: string): Promise<TaskStatusResponse> {
  return requestJson(`/api/v1/detections/${encodeURIComponent(taskId)}`);
}

export function getDetectionRecords(query: DetectionRecordQuery): Promise<DetectionRecordListResponse> {
  const params = new URLSearchParams({ page: String(query.page), page_size: String(query.page_size) });
  if (query.keyword) params.set('keyword', query.keyword);
  if (query.authenticity) params.set('authenticity', query.authenticity);
  if (query.action) params.set('action', query.action);
  if (query.date_from) params.set('date_from', query.date_from);
  if (query.date_to) params.set('date_to', query.date_to);
  return requestJson(`/api/v1/results?${params.toString()}`);
}

export function getDetectionResult(resultId: number): Promise<DetectionResultResponse> {
  return requestJson(`/api/v1/results/${resultId}`);
}

export function createTaskReport(taskId: string): Promise<ReportSummaryResponse> {
  return requestJson('/api/v1/reports', { method: 'POST', body: JSON.stringify({ task_id: taskId }) });
}

export function downloadTaskReport(reportId: number, format: 'json' | 'csv'): Promise<Blob> {
  return requestBlob(`/api/v1/reports/${reportId}/download?format=${format}`);
}
