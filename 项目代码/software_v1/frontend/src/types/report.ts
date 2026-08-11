export interface ReportSummaryResponse { report_id: string; task_id: string; status: string; summary: Record<string, number | string>; created_at: string }
