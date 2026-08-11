<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue';
import {
  AlertCircle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Download,
  FileSpreadsheet,
  LoaderCircle,
  RotateCcw,
  Trash2,
  Upload,
} from 'lucide-vue-next';
import { ApiError, getDetectionTask, submitBatchDetection } from '../api/client';
import type { TaskStatus, TaskStatusResponse } from '../types';
import { batchRowToRequest, parseBatchFile, validateBatchRows, type BatchPreviewRow } from '../utils/batch-parser';

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
  <section class="page-content">
    <div class="page-heading">
      <div>
        <span class="eyebrow">内容审核 / 批量检测</span>
        <h1>批量检测任务</h1>
        <p>导入评论文件，校验数据后提交统一检测任务。</p>
      </div>
      <a class="icon-text-button template-link" :href="templateHref" download="batch-review-template.csv"><Download :size="16" />下载 CSV 模板</a>
    </div>

    <div class="batch-layout">
      <section class="batch-panel">
        <div class="section-heading">
          <div><h2>评论数据</h2><p>CSV 或 TSV，最多 1000 条</p></div>
          <button v-if="rows.length || fileErrors.length" type="button" class="icon-text-button secondary" @click="clearFile"><RotateCcw :size="16" />清空</button>
        </div>

        <label
          v-if="!rows.length"
          class="upload-zone"
          :class="{ dragging }"
          @dragenter.prevent="dragging = true"
          @dragover.prevent
          @dragleave.prevent="dragging = false"
          @drop.prevent="onDrop"
        >
          <input data-testid="file-input" type="file" accept=".csv,.tsv,text/csv,text/tab-separated-values" @change="onFileInput" />
          <span class="upload-icon"><Upload :size="24" /></span>
          <strong>选择 CSV / TSV 文件</strong>
          <small>或将文件拖放到此处</small>
          <em>字段：review_id、user_id、prod_id、rating、date、text</em>
        </label>

        <div v-if="fileErrors.length" class="alert error file-alert" role="alert">
          <AlertCircle :size="18" />
          <div><strong>文件无法导入</strong><span v-for="error in fileErrors" :key="error">{{ error }}</span></div>
        </div>

        <template v-if="rows.length">
          <div class="file-summary">
            <span class="file-type-icon"><FileSpreadsheet :size="19" /></span>
            <div><strong>{{ fileName }}</strong><small>{{ rows.length }} 条评论 · {{ invalidCount ? `${invalidCount} 条待修正` : '校验通过' }}</small></div>
            <label class="icon-text-button secondary replace-file"><input type="file" accept=".csv,.tsv,text/csv,text/tab-separated-values" @change="onFileInput" />重新选择</label>
          </div>

          <div v-if="invalidCount" class="alert error" role="alert"><AlertCircle :size="18" /><span>存在 {{ invalidCount }} 条错误数据，修正后才能提交。</span></div>

          <div class="batch-table-wrap">
            <table class="batch-table">
              <thead><tr><th>行</th><th>评论 ID</th><th>用户 ID *</th><th>商品 ID *</th><th>评分 *</th><th>评论时间 *</th><th>评论文本 *</th><th><span class="sr-only">操作</span></th></tr></thead>
              <tbody>
                <template v-for="row in paginatedRows" :key="row.rowNumber">
                  <tr :class="{ 'invalid-row': row.errors.length }">
                    <td class="row-number">{{ row.rowNumber }}</td>
                    <td><input v-model="row.review_id" maxlength="101" aria-label="评论 ID" @input="revalidate" /></td>
                    <td><input v-model="row.user_id" maxlength="129" aria-label="用户 ID" @input="revalidate" /></td>
                    <td><input v-model="row.prod_id" maxlength="129" aria-label="商品 ID" @input="revalidate" /></td>
                    <td><input v-model="row.rating" class="rating-cell" type="number" min="1" max="5" step="0.5" aria-label="评分" @input="revalidate" /></td>
                    <td><input v-model="row.date" class="date-cell" aria-label="评论时间" @input="revalidate" /></td>
                    <td><input v-model="row.text" class="text-cell" maxlength="10001" aria-label="评论文本" @input="revalidate" /></td>
                    <td><button type="button" class="icon-button danger-button" :aria-label="`删除第 ${row.rowNumber} 行`" title="删除该行" @click="removeRow(row.rowNumber)"><Trash2 :size="16" /></button></td>
                  </tr>
                  <tr v-if="row.errors.length" class="table-error-row"><td colspan="8"><AlertCircle :size="14" />第 {{ row.rowNumber }} 行：{{ row.errors.join('；') }}</td></tr>
                </template>
              </tbody>
            </table>
          </div>

          <div class="table-footer">
            <span>显示 {{ (currentPage - 1) * pageSize + 1 }}–{{ Math.min(currentPage * pageSize, rows.length) }}，共 {{ rows.length }} 条</span>
            <div class="pagination">
              <button type="button" class="icon-button" aria-label="上一页" :disabled="currentPage === 1" @click="currentPage--"><ChevronLeft :size="17" /></button>
              <span>{{ currentPage }} / {{ totalPages }}</span>
              <button type="button" class="icon-button" aria-label="下一页" :disabled="currentPage === totalPages" @click="currentPage++"><ChevronRight :size="17" /></button>
            </div>
          </div>

          <div class="batch-actions">
            <p>行为历史统一为空，任务结果可能出现“行为证据不足”。</p>
            <button data-testid="batch-submit" type="button" class="primary-button" :disabled="!canSubmit" @click="submit">
              <LoaderCircle v-if="submitting" class="spin-icon" :size="18" /><Upload v-else :size="18" />{{ submitting ? '任务处理中…' : `提交 ${rows.length} 条评论` }}
            </button>
          </div>
        </template>
      </section>

      <aside class="task-panel" aria-live="polite">
        <div class="section-heading"><div><h2>任务状态</h2><p>批量处理进度摘要</p></div><span v-if="task" class="status-pill" :class="task.status">{{ statusLabels[task.status] }}</span></div>
        <div v-if="!task" class="result-empty batch-empty"><div class="result-empty-icon"><FileSpreadsheet :size="25" /></div><strong>暂无任务</strong><p>导入并提交有效文件后，可在此查看处理进度。</p></div>
        <template v-else>
          <div class="task-progress-head"><strong>{{ progress }}%</strong><span>{{ processedCount }} / {{ task.total_count }}</span></div>
          <div class="task-progress"><span :style="{ width: `${progress}%` }"></span></div>
          <dl class="task-stats">
            <div><dt>评论总数</dt><dd>{{ task.total_count }}</dd></div>
            <div><dt>处理成功</dt><dd class="success-text">{{ task.completed_count }}</dd></div>
            <div><dt>处理失败</dt><dd :class="{ 'danger-text': task.failed_count }">{{ task.failed_count }}</dd></div>
          </dl>
          <dl class="result-list task-meta">
            <div><dt>任务编号</dt><dd class="mono task-id">{{ task.task_id }}</dd></div>
            <div><dt>创建时间</dt><dd>{{ new Date(task.created_at).toLocaleString('zh-CN') }}</dd></div>
          </dl>
          <div v-if="task.status === 'succeeded' && !task.failed_count" class="task-message success"><CheckCircle2 :size="18" /><span>全部评论处理完成。</span></div>
          <div v-if="task.error_summary" class="task-message error"><AlertCircle :size="18" /><span>{{ task.error_summary }}</span></div>
        </template>
        <div v-if="requestError" class="alert error task-request-error" role="alert"><AlertCircle :size="18" /><span>{{ requestError }}</span></div>
      </aside>
    </div>
  </section>
</template>
