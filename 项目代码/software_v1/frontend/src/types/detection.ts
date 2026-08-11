import type { Action, Authenticity, BehaviorType, RiskSource, SemanticType, TaskStatus } from './enums';
import type { Explanation } from './explanation';

export interface BehaviorHistoryItem { review_id?: string; date: string; features: [number, number, number, number, number, number, number, number, number, number] }
export interface SingleDetectionRequest { review_id?: string; user_id: string; prod_id: string; rating: number; date: string; text: string; behavior_history?: BehaviorHistoryItem[] }
export interface BatchDetectionRequest { items: SingleDetectionRequest[] }
export interface DetectionSubmitResponse { task_id: string; status: TaskStatus; created_at: string }
export interface DetectionResultResponse { result_id: string; review_id?: string; authenticity: Authenticity; confidence: number; semantic_type: SemanticType; behavior_type: BehaviorType; risk_source: RiskSource; action: Action; model_version: string; explanation: Explanation; created_at: string }
