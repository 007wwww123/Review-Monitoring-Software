// 检测结果相关的标签文案与格式化，各页面统一从这里取。
import type { Action, Authenticity, BehaviorType, RiskSource, SemanticType } from './types';

export const authenticityLabels: Record<Authenticity, string> = { real: '真实', fake: '疑似虚假' };
export const semanticLabels: Record<SemanticType, string> = {
  real: '真实语义', misleading: '误导性', exaggerated: '夸张性', advertising: '广告性', none: '无', uncertain: '不确定',
};
export const behaviorLabels: Record<BehaviorType, string> = {
  normal: '行为正常', review_manipulation: '评论操纵', crowdturfing: '群体操纵', bot_like: '机器行为', insufficient_evidence: '行为证据不足',
};
export const riskLabels: Record<RiskSource, string> = {
  real: '未发现风险', language_fake: '语义风险', behavior_fake: '行为风险', language_behavior_composite: '语义与行为复合风险', uncertain: '风险不确定',
};
export const actionLabels: Record<Action, string> = { keep: '保留', review: '人工复核', block: '拦截' };
// 处置建议对应的标签色：保留绿、复核橙、拦截红
export const actionTone = { keep: 'ok', review: 'warn', block: 'fake' } as const;
export const evidenceStateLabels: Record<string, string> = {
  available: '可用', insufficient: '证据不足', uncalibrated: '未校准', calibrated: '已校准',
};

// 模型输出的固定标签顺序，与后端契约一致，不能调整
export const SEMANTIC_ORDER = ['real', 'misleading', 'exaggerated', 'advertising'] as const;
export const BEHAVIOR_ORDER = ['normal', 'review_manipulation', 'crowdturfing', 'bot_like', 'insufficient_evidence'] as const;

export function percent(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

// 列表和单条接口只给真实性与置信度，换算成虚假概率
export function fakeProbabilityOf(item: { authenticity: Authenticity; confidence: number }): number {
  return item.authenticity === 'fake' ? item.confidence : 1 - item.confidence;
}

// 后端时间是不带时区的 UTC（utcnow），按 UTC 解析
export function parseServerTime(value: string): Date {
  return new Date(/[zZ]|[+-]\d{2}:?\d{2}$/.test(value) ? value : `${value}Z`);
}

// 按本地时间显示：2026-11-02 20:58:49
export function formatDateTime(value: string): string {
  const date = parseServerTime(value);
  if (Number.isNaN(date.getTime())) return value;
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

// 长哈希、任务号只显示首尾，完整值放在 title 里
export function shortId(value: string, keep = 8): string {
  return value.length > keep * 2 + 1 ? `${value.slice(0, keep)}…${value.slice(-keep)}` : value;
}
