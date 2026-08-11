export interface EvaluationResponse {
  report_id: number;
  dataset_name: string;
  dataset_split: 'train' | 'val' | 'test' | 'production_review';
  sample_count: number;
  accuracy: number | null;
  precision: number | null;
  recall: number | null;
  f1: number | null;
  auc: number | null;
  confusion_matrix: Record<string, unknown> | null;
  status: 'success' | 'failed';
  created_at: string;
}
