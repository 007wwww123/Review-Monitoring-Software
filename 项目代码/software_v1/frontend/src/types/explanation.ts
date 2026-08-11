import type { Action, Authenticity, BehaviorType, RiskSource, SemanticType } from './enums';

export interface Explanation {
  schema_version: 'explanation.v1';
  final: { authenticity: Authenticity; confidence: number; risk_source: RiskSource; action: Action };
  semantic: { scores: Record<'real' | 'misleading' | 'exaggerated' | 'advertising', number>; selected_type: SemanticType };
  behavior: { scores: Record<'normal' | 'review_manipulation' | 'crowdturfing' | 'bot_like' | 'insufficient_evidence', number>; selected_type: BehaviorType; available: boolean; history_length: number; is_proxy_task: boolean };
  fusion: { semantic_weight: number; behavior_weight: number; weight_summary: string };
  evidence: { semantic_evidence_state: string; behavior_evidence_state: string; calibration_state: string };
  disclaimers: [string, string, string, string];
}
