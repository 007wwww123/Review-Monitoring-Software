export interface ModelVersionResponse {
  version: string;
  model_name: string;
  tokenizer_name: string;
  config: Record<string, unknown>;
  metrics: Record<string, number | string> | null;
  checkpoint_sha256: string;
  is_active: boolean;
  created_at: string;
}
