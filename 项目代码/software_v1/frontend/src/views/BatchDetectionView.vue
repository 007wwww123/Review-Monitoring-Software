<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue';
import { AlertCircle, ArrowRight, CheckCircle2, ChevronLeft, ChevronRight, Download, FileSpreadsheet, LoaderCircle, RotateCcw, Trash2, Upload } from 'lucide-vue-next';
import { ApiError, getDetectionTask, submitBatchDetection } from '../api/client';
import type { TaskStatus, TaskStatusResponse } from '../types';
import { batchRowToRequest, parseBatchFile, validateBatchRows, type BatchPreviewRow } from '../utils/batch-parser';
import AppCard from '../components/AppCard.vue';
import DonutChart from '../components/charts/DonutChart.vue';
import { formatDateTime, shortId } from '../labels';

const rows = ref<BatchPreviewRow[]>([]);
const fileName = ref('');
const fileErrors = ref<string[]>([]);
const requestError = ref('');
const task = ref<TaskStatusResponse | null>(null);
const submitting = ref(false);
const dragging = ref(false);
const currentPage = ref(1);
const pageSize = 20;
let pollingGeneration = 0;

const invalidCount = computed(() => rows.value.filter((row) => row.errors.length).length);
const totalPages = computed(() => Math.max(1, Math.ceil(rows.value.length / pageSize)));
const paginatedRows = computed(() => rows.value.slice((currentPage.value - 1) * pageSize, currentPage.value * pageSize));
const canSubmit = computed(() => rows.value.length > 0 && invalidCount.value === 0 && !fileErrors.value.length && !submitting.value);
const processedCount = computed(() => task.value ? task.value.completed_count + task.value.failed_count : 0);
const progress = computed(() => task.value?.total_count ? Math.min(100, Math.round(processedCount.value / task.value.total_count * 100)) : 0);
const templateHref = '/batch-review-template.csv';
const terminalStatuses: TaskStatus[] = ['succeeded', 'failed', 'cancelled'];
const statusLabels: Record<TaskStatus, string> = { pending: '等待处理', running: '处理中', succeeded: '已完成', failed: '失败', cancelled: '已取消' };
const statusTone: Record<TaskStatus, string> = { pending: 'neutral', running: 'primary', succeeded: 'ok', failed: 'fake', cancelled: 'neutral' };
const REQUIRED_COLUMNS = ['review_id', 'user_id', 'prod_id', 'rating', 'date', 'text'];
const steps = ['下载 CSV 模板并按字段填写', '导入 CSV / TSV 文件', '在预览表格中修正错误行', '提交批量检测任务', '到检测记录中查看结果'];
const progressParts = computed(() => task.value ? [
  { key: 'done', label: '成功', value: task.value.completed_count, tone: 'primary' as const },
  { key: 'failed', label: '失败', value: task.value.failed_count, tone: 'fake' as const },
  { key: 'rest', label: '剩余', value: Math.max(task.value.total_count - processedCount.value, 0), tone: 'neutral' as const },
] : []);

function resetTask() {
  pollingGeneration += 1;
  task.value = null;
  requestError.value = '';
  submitting.value = false;
}

function clearFile() {
  rows.value = [];
  fileName.value = '';
  fileErrors.value = [];
  currentPage.value = 1;
  resetTask();
}

async function loadFile(file?: File) {
  if (!file) return;
  resetTask();
  fileName.value = file.name;
  currentPage.value = 1;
  try {
    const parsed = parseBatchFile(await file.text());
    rows.value = parsed.rows;
    fileErrors.value = parsed.fileErrors;
  } catch {
    rows.value = [];
    fileErrors.value = ['文件读取失败，请确认文件未损坏。'];
  }
}

function onFileInput(event: Event) {
  const input = event.target as HTMLInputElement;
  void loadFile(input.files?.[0]);
  input.value = '';
}

function onDrop(event: DragEvent) {
  dragging.value = false;
  void loadFile(event.dataTransfer?.files[0]);
}

function revalidate() {
  rows.value = validateBatchRows(rows.value);
}

function removeRow(rowNumber: number) {
  rows.value = validateBatchRows(rows.value.filter((row) => row.rowNumber !== rowNumber));
  currentPage.value = Math.min(currentPage.value, totalPages.value);
  resetTask();
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function pollTask(taskId: string, generation: number) {
  const interval = import.meta.env.MODE === 'test' ? 5 : 1000;
  for (let attempt = 0; attempt < 60; attempt += 1) {
    if (generation !== pollingGeneration) return;
    const status = await getDetectionTask(taskId);
    if (generation !== pollingGeneration) return;
    task.value = status;
    if (terminalStatuses.includes(status.status)) return;
    await delay(interval);
  }
  throw new ApiError('任务状态查询超时，请稍后到检测记录中查看。', 408);
}

async function submit() {
  revalidate();
  if (!canSubmit.value) return;
  resetTask();
  submitting.value = true;
  const generation = pollingGeneration;
  try {
    const response = await submitBatchDetection({ items: rows.value.map(batchRowToRequest) });
    task.value = {
      task_id: response.task_id,
      status: response.status,
      total_count: rows.value.length,
      completed_count: response.status === 'succeeded' ? rows.value.length : 0,
      failed_count: 0,
      created_at: response.created_at,
    };
    await pollTask(response.task_id, generation);
  } catch (error) {
    requestError.value = error instanceof ApiError ? error.message : '批量任务提交失败，请稍后重试。';
  } finally {
    if (generation === pollingGeneration) submitting.value = false;
  }
}

onBeforeUnmount(() => { pollingGeneration += 1; });
</script>

<template>
  <section class="page batch-page">
    <nav class="crumb" aria-label="面包屑">检测工作台 / <b>批量检测任务</b></nav>
    <header class="page-title">
      <h1>批量检测任务</h1>
      <span class="page-id">导入评论文件，校验数据后提交统一检测任务</span>
      <div class="page-actions">
        <a class="btn" :href="templateHref" download="batch-review-template.csv"><Download :size="15" />下载 CSV 模板</a>
      </div>
    </header>

    <div class="batch-layout">
      <AppCard title="评论数据" subtitle="CSV 或 TSV 文件，单次最多 1000 条">
        <template v-if="rows.length || fileErrors.length" #extra>
          <button type="button" class="btn small" @click="clearFile"><RotateCcw :size="14" />清空</button>
        </template>

        <label
          v-if="!rows.length" class="upload-zone" :class="{ dragging }"
          @dragenter.prevent="dragging = true" @dragover.prevent @dragleave.prevent="dragging = false" @drop.prevent="onDrop"
        >
          <input data-testid="file-input" type="file" accept=".csv,.tsv,text/csv,text/tab-separated-values" @change="onFileInput" />
          <span class="upload-icon"><Upload :size="24" /></span>
          <strong>选择 CSV / TSV 文件</strong>
          <small>或将文件拖放到此处</small>
          <span class="columns">需要的字段：<code v-for="column in REQUIRED_COLUMNS" :key="column">{{ column }}</code></span>
        </label>

        <div v-if="fileErrors.length" class="alert-bar file-alert" role="alert">
          <AlertCircle :size="16" />
          <div><strong>文件无法导入</strong><span v-for="error in fileErrors" :key="error">{{ error }}</span></div>
        </div>

        <template v-if="rows.length">
          <div class="file-summary">
            <span class="file-icon"><FileSpreadsheet :size="19" /></span>
            <div>
              <strong>{{ fileName }}</strong>
              <small class="num">{{ rows.length }} 条评论 · <span :class="invalidCount ? 'bad' : 'good'">{{ invalidCount ? `${invalidCount} 条待修正` : '校验通过' }}</span></small>
            </div>
            <label class="btn small replace-file"><input type="file" accept=".csv,.tsv,text/csv,text/tab-separated-values" @change="onFileInput" />重新选择</label>
          </div>

          <div v-if="invalidCount" class="alert-bar" role="alert"><AlertCircle :size="16" />存在 {{ invalidCount }} 条错误数据，修正后才能提交。</div>

          <div class="table-wrap">
            <table class="ui-table preview-table">
              <thead><tr><th>行</th><th>评论 ID</th><th>用户 ID *</th><th>商品 ID *</th><th>评分 *</th><th>评论时间 *</th><th>评论文本 *</th><th><span class="sr-only">操作</span></th></tr></thead>
              <tbody>
                <template v-for="row in paginatedRows" :key="row.rowNumber">
                  <tr :class="{ invalid: row.errors.length }">
                    <td class="row-number num">{{ row.rowNumber }}</td>
                    <td><input v-model="row.review_id" class="cell-input" maxlength="101" aria-label="评论 ID" @input="revalidate" /></td>
                    <td><input v-model="row.user_id" class="cell-input" maxlength="129" aria-label="用户 ID" @input="revalidate" /></td>
                    <td><input v-model="row.prod_id" class="cell-input" maxlength="129" aria-label="商品 ID" @input="revalidate" /></td>
                    <td><input v-model="row.rating" class="cell-input rating" type="number" min="1" max="5" step="0.5" aria-label="评分" @input="revalidate" /></td>
                    <td><input v-model="row.date" class="cell-input date" aria-label="评论时间" @input="revalidate" /></td>
                    <td><input v-model="row.text" class="cell-input text" maxlength="10001" aria-label="评论文本" @input="revalidate" /></td>
                    <td><button type="button" class="btn icon small" :aria-label="`删除第 ${row.rowNumber} 行`" title="删除该行" @click="removeRow(row.rowNumber)"><Trash2 :size="15" /></button></td>
                  </tr>
                  <tr v-if="row.errors.length" class="error-row"><td colspan="8"><AlertCircle :size="13" />第 {{ row.rowNumber }} 行：{{ row.errors.join('；') }}</td></tr>
                </template>
              </tbody>
            </table>
          </div>

          <div class="table-foot">
            <span class="num">显示 {{ (currentPage - 1) * pageSize + 1 }}–{{ Math.min(currentPage * pageSize, rows.length) }}，共 {{ rows.length }} 条</span>
            <div class="pager">
              <button type="button" class="btn icon small" aria-label="上一页" :disabled="currentPage === 1" @click="currentPage--"><ChevronLeft :size="16" /></button>
              <span class="num">{{ currentPage }} / {{ totalPages }}</span>
              <button type="button" class="btn icon small" aria-label="下一页" :disabled="currentPage === totalPages" @click="currentPage++"><ChevronRight :size="16" /></button>
            </div>
          </div>

          <div class="submit-bar">
            <p>批量导入不含行为历史，结果中可能出现“行为证据不足”。</p>
            <button data-testid="batch-submit" type="button" class="btn primary" :disabled="!canSubmit" @click="submit">
              <LoaderCircle v-if="submitting" class="spin-icon" :size="16" /><Upload v-else :size="16" />{{ submitting ? '任务处理中…' : `提交 ${rows.length} 条评论` }}
            </button>
          </div>
        </template>
      </AppCard>

      <AppCard title="任务状态" :subtitle="task ? '批量处理进度' : '提交后在此显示进度'" class="task-card" aria-live="polite">
        <template v-if="task" #extra><span class="tag" :class="statusTone[task.status]">{{ statusLabels[task.status] }}</span></template>

        <ol v-if="!task" class="steps">
          <li v-for="(step, index) in steps" :key="step"><b>{{ index + 1 }}</b>{{ step }}</li>
        </ol>

        <template v-else>
          <DonutChart :parts="progressParts" :center="`${progress}%`" caption="处理进度" />
          <p class="progress-count num">{{ processedCount }} / {{ task.total_count }}</p>
          <dl class="task-stats">
            <div><dt>评论总数</dt><dd class="num">{{ task.total_count }}</dd></div>
            <div><dt>处理成功</dt><dd class="num good">{{ task.completed_count }}</dd></div>
            <div><dt>处理失败</dt><dd class="num" :class="{ bad: task.failed_count }">{{ task.failed_count }}</dd></div>
          </dl>
          <dl class="task-meta">
            <dt>任务编号</dt><dd class="num" :title="task.task_id">{{ shortId(task.task_id, 6) }}</dd>
            <dt>创建时间</dt><dd class="num">{{ formatDateTime(task.created_at) }}</dd>
          </dl>
          <div v-if="task.status === 'succeeded' && !task.failed_count" class="alert-bar ok"><CheckCircle2 :size="16" />全部评论处理完成。</div>
          <div v-if="task.error_summary" class="alert-bar"><AlertCircle :size="16" />{{ task.error_summary }}</div>
          <RouterLink v-if="task.status === 'succeeded'" to="/results" class="btn primary to-records">查看检测记录<ArrowRight :size="15" /></RouterLink>
        </template>
        <div v-if="requestError" class="alert-bar request-error" role="alert"><AlertCircle :size="16" />{{ requestError }}</div>
      </AppCard>
    </div>
  </section>
</template>

<style scoped>
.batch-layout { display: grid; grid-template-columns: minmax(0, 1fr) 340px; align-items: start; gap: 16px; }
.upload-zone { position: relative; display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 44px 20px; border: 1.5px dashed var(--color-line-strong); border-radius: 12px; background: var(--color-surface-muted); cursor: pointer; text-align: center; transition: border-color .15s, background .15s; }
.upload-zone:hover, .upload-zone.dragging { border-color: var(--color-primary); background: var(--color-primary-soft); }
.upload-zone input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
.upload-icon { display: grid; width: 52px; height: 52px; place-items: center; margin-bottom: 6px; border-radius: 14px; background: var(--color-brand-deep); color: var(--color-accent); }
.upload-zone strong { font-size: 15px; }
.upload-zone small { color: var(--color-text-muted); font-size: 13px; }
.columns { display: flex; flex-wrap: wrap; justify-content: center; align-items: center; gap: 6px; margin-top: 10px; color: var(--color-text-muted); font-size: 12px; }
.columns code { padding: 1px 7px; border-radius: 5px; background: var(--color-surface); box-shadow: 0 0 0 1px var(--color-line); color: var(--color-text-secondary); font-size: 12px; }
.file-alert { align-items: flex-start; margin-top: 12px; }
.file-alert div { display: flex; flex-direction: column; gap: 2px; }
.file-summary { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; padding: 12px 14px; border: 1px solid var(--color-line); border-radius: 10px; }
.file-summary > div { flex: 1; }
.file-summary strong { display: block; font-size: 14px; }
.file-summary small { color: var(--color-text-muted); font-size: 12px; }
.file-icon { display: grid; width: 38px; height: 38px; place-items: center; border-radius: 10px; background: var(--color-behavior-soft); color: var(--color-behavior); }
.good { color: color-mix(in srgb, var(--color-primary) 80%, #000); font-weight: 600; }
.bad { color: var(--color-fake); font-weight: 600; }
.replace-file { position: relative; overflow: hidden; }
.replace-file input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
.table-wrap { overflow-x: auto; border: 1px solid var(--color-line); border-radius: 10px; }
.preview-table { min-width: 1040px; }
.preview-table td { padding: 6px 8px; }
.preview-table th { padding: 9px 8px; background: var(--color-surface-muted); }
.row-number { width: 42px; color: var(--color-text-muted); text-align: center; }
.cell-input { width: 100%; padding: 6px 8px; border: 1px solid transparent; border-radius: 7px; outline: 0; background: transparent; color: var(--color-text); font: inherit; font-size: 13px; }
.cell-input:hover { border-color: var(--color-line); }
.cell-input:focus { border-color: var(--color-primary); background: var(--color-surface); box-shadow: 0 0 0 3px var(--color-primary-soft); }
.cell-input { min-width: 104px; }
.cell-input.rating { width: 64px; min-width: 64px; }
.cell-input.date { min-width: 200px; }
.cell-input.text { min-width: 260px; }
tr.invalid td { background: var(--color-fake-soft); }
.error-row td { padding: 4px 12px 8px; background: var(--color-fake-soft); color: var(--color-fake); font-size: 12px; }
.error-row svg { margin-right: 4px; vertical-align: -2px; }
.table-foot { display: flex; align-items: center; justify-content: space-between; margin-top: 10px; color: var(--color-text-muted); font-size: 13px; }
.pager { display: flex; align-items: center; gap: 10px; }
.submit-bar { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--color-line); }
.submit-bar p { margin: 0; color: var(--color-text-muted); font-size: 12px; }
.spin-icon { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.task-card { position: sticky; top: 22px; }
.steps { position: relative; display: flex; flex-direction: column; gap: 10px; margin: 0; padding: 0; list-style: none; }
.steps::before { position: absolute; top: 14px; bottom: 14px; left: 13px; width: 2px; background: var(--color-line); content: ""; }
.steps li { position: relative; display: flex; align-items: center; gap: 12px; padding: 8px 0; font-size: 13px; }
.steps b { z-index: 1; display: grid; flex: none; width: 28px; height: 28px; place-items: center; border: 2px solid var(--color-surface); border-radius: 50%; background: var(--color-primary-soft); color: var(--color-primary); font-size: 12px; }
.steps li:nth-child(2) b { background: var(--color-primary); color: var(--color-on-primary); }
.steps li:nth-child(4) b { background: var(--color-behavior); color: #fff; }
.steps li:last-child b { background: var(--color-accent); color: var(--color-on-accent); }
.progress-count { margin: -4px 0 12px; color: var(--color-text-muted); font-size: 13px; text-align: center; }
.task-stats { display: grid; grid-template-columns: repeat(3, 1fr); margin: 0 0 12px; overflow: hidden; border: 1px solid var(--color-line); border-radius: 10px; }
.task-stats div { padding: 9px 12px; text-align: center; }
.task-stats div + div { border-left: 1px solid var(--color-line); }
.task-stats dt { color: var(--color-text-muted); font-size: 12px; }
.task-stats dd { margin: 0; font-size: 18px; font-weight: 700; }
.task-meta { display: grid; grid-template-columns: 70px 1fr; row-gap: 8px; margin: 0 0 12px; font-size: 13px; }
.task-meta dt { color: var(--color-text-muted); }
.task-meta dd { margin: 0; }
.to-records { width: 100%; }
.request-error { margin: 12px 0 0; }

@media (max-width: 1120px) {
  .batch-layout { grid-template-columns: 1fr; }
  .task-card { position: static; }
}
</style>
