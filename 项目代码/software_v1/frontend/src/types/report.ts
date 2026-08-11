export interface ReportRequest { task_id: string }
export interface ReportSummaryResponse { report_id: number; task_id: string; status: string; summary: Record<string, number | string>; created_at: string }
