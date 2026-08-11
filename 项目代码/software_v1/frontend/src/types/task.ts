import type { TaskStatus } from './enums';
export interface TaskStatusResponse { task_id: string; status: TaskStatus; total_count: number; completed_count: number; failed_count: number; error_summary?: string; created_at: string; started_at?: string; finished_at?: string }
