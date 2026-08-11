import type { Action, Authenticity, BehaviorType, RiskSource, SemanticType } from './enums';

export interface DetectionRecordItem {
  result_id: number;
  task_id: string;
  review_id?: string;
  user_key: string;
  product_id: string;
  text_excerpt: string;
  authenticity: Authenticity;
  confidence: number;
  semantic_type: SemanticType;
  behavior_type: BehaviorType;
  risk_source: RiskSource;
  action: Action;
  model_version: string;
  created_at: string;
}

export interface DetectionRecordQuery {
  page: number;
  page_size: number;
  keyword?: string;
  authenticity?: Authenticity;
  action?: Action;
  date_from?: string;
  date_to?: string;
}

export interface DetectionRecordListResponse {
  items: DetectionRecordItem[];
  total: number;
  page: number;
  page_size: number;
}
