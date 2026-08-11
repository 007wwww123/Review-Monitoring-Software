export type Authenticity = 'real' | 'fake';
export type SemanticType = 'real' | 'misleading' | 'exaggerated' | 'advertising' | 'none' | 'uncertain';
export type BehaviorType = 'normal' | 'review_manipulation' | 'crowdturfing' | 'bot_like' | 'insufficient_evidence';
export type RiskSource = 'real' | 'language_fake' | 'behavior_fake' | 'language_behavior_composite' | 'uncertain';
export type Action = 'keep' | 'review' | 'block';
export type TaskStatus = 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled';
