<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { AlertCircle, ArrowRight, ChevronLeft, ChevronRight, FileClock, RefreshCw, Search } from 'lucide-vue-next';
import { ApiError, getDetectionRecords } from '../api/client';
import type { Action, Authenticity, DetectionRecordItem } from '../types';
import AppCard from '../components/AppCard.vue';
import { actionLabels, authenticityLabels, behaviorLabels, formatDateTime, percent, semanticLabels, shortId } from '../labels';

const filters = reactive({ keyword: '', authenticity: '' as Authenticity | '', action: '' as Action | '', date_from: '', date_to: '' });
const records = ref<DetectionRecordItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = 10;
const loading = ref(false);
const errorMessage = ref('');

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)));
const rangeStart = computed(() => total.value ? (page.value - 1) * pageSize + 1 : 0);
const rangeEnd = computed(() => Math.min(page.value * pageSize, total.value));
const authenticityOptions: { value: Authenticity | ''; label: string }[] = [
  { value: '', label: '全部' }, { value: 'fake', label: '疑似虚假' }, { value: 'real', label: '真实' },
];
const actionTone = { keep: 'ok', review: 'warn', block: 'fake' } as const;
// 列表只有真实性和置信度，换算成虚假概率展示
const fakeProbability = (item: DetectionRecordItem) => item.authenticity === 'fake' ? item.confidence : 1 - item.confidence;

async function loadRecords() {
  loading.value = true;
  errorMessage.value = '';
  try {
    const response = await getDetectionRecords({
      page: page.value,
      page_size: pageSize,
      ...(filters.keyword.trim() ? { keyword: filters.keyword.trim() } : {}),
      ...(filters.authenticity ? { authenticity: filters.authenticity } : {}),
      ...(filters.action ? { action: filters.action } : {}),
      ...(filters.date_from ? { date_from: filters.date_from } : {}),
      ...(filters.date_to ? { date_to: filters.date_to } : {}),
    });
    records.value = response.items;
    total.value = response.total;
  } catch (error) {
    records.value = [];
    total.value = 0;
    errorMessage.value = error instanceof ApiError ? error.message : '检测记录加载失败，请稍后重试。';
  } finally {
    loading.value = false;
  }
}

function search() {
  page.value = 1;
  void loadRecords();
}

function chooseAuthenticity(value: Authenticity | '') {
  filters.authenticity = value;
  search();
}

function resetFilters() {
  Object.assign(filters, { keyword: '', authenticity: '', action: '', date_from: '', date_to: '' });
  search();
}

function changePage(nextPage: number) {
  if (nextPage < 1 || nextPage > totalPages.value || loading.value) return;
  page.value = nextPage;
  void loadRecords();
}

onMounted(loadRecords);
</script>

<template>
  <section class="page records-page">
    <nav class="crumb" aria-label="面包屑">检测工作台 / <b>检测记录</b></nav>
    <header class="page-title">
      <h1>检测记录</h1>
      <span class="page-id">单条检测与批量任务产生的全部检测结果</span>
      <div class="page-actions"><span class="tag primary num">共 {{ total }} 条</span></div>
    </header>

    <AppCard class="filter-card">
      <form class="filters" @submit.prevent="search">
        <label class="ui-field keyword-field">
          <span>关键词</span>
          <span class="input-icon"><Search :size="15" /><input v-model="filters.keyword" class="ui-input" placeholder="评论 ID、用户、商品或评论内容" /></span>
        </label>
        <div class="ui-field">
          <span>真实性</span>
          <div class="segmented" role="radiogroup" aria-label="真实性">
            <button
              v-for="option in authenticityOptions" :key="option.value" type="button" role="radio"
              :aria-checked="filters.authenticity === option.value" :class="{ on: filters.authenticity === option.value }"
              @click="chooseAuthenticity(option.value)"
            >{{ option.label }}</button>
          </div>
        </div>
        <label class="ui-field">
          <span>处置建议</span>
          <select v-model="filters.action" class="ui-input action-select">
            <option value="">全部</option><option value="keep">保留</option><option value="review">人工复核</option><option value="block">拦截</option>
          </select>
        </label>
        <label class="ui-field"><span>开始日期</span><input v-model="filters.date_from" class="ui-input" type="date" /></label>
        <label class="ui-field"><span>结束日期</span><input v-model="filters.date_to" class="ui-input" type="date" /></label>
        <div class="filter-actions">
          <button type="button" class="btn reset-filters" @click="resetFilters"><RefreshCw :size="15" />重置</button>
          <button type="submit" class="btn primary" :disabled="loading"><Search :size="15" />查询</button>
        </div>
      </form>
    </AppCard>

    <AppCard class="table-card">
      <div v-if="errorMessage" class="alert-bar" role="alert">
        <AlertCircle :size="16" />{{ errorMessage }}
        <button type="button" class="btn small retry" @click="loadRecords">重新加载</button>
      </div>

      <div class="table-wrap" :class="{ loading }">
        <table class="ui-table record-table">
          <thead>
            <tr><th>评论</th><th>用户 / 商品</th><th>虚假概率</th><th>语义 / 行为</th><th>处置建议</th><th>检测时间</th><th><span class="sr-only">操作</span></th></tr>
          </thead>
          <tbody v-if="records.length">
            <tr v-for="item in records" :key="item.result_id">
              <td class="review-cell">
                <strong class="num">{{ item.review_id || `结果 #${item.result_id}` }}</strong>
                <p :title="item.text_excerpt">{{ item.text_excerpt }}</p>
              </td>
              <td class="muted num"><span :title="item.user_key">{{ shortId(item.user_key, 4) }}</span><br />{{ item.product_id }}</td>
              <td class="prob-cell">
                <span class="tag auth-tag" :class="item.authenticity === 'fake' ? 'fake' : 'ok'">{{ authenticityLabels[item.authenticity] }}</span>
                <span class="prob" :class="item.authenticity"><i :style="{ width: percent(fakeProbability(item)) }"></i></span>
                <small class="num">{{ percent(fakeProbability(item)) }}</small>
              </td>
              <td class="type-cell">
                <span>{{ semanticLabels[item.semantic_type] }}</span>
                <small :class="{ warn: item.behavior_type === 'insufficient_evidence' }">{{ behaviorLabels[item.behavior_type] }}</small>
              </td>
              <td><span class="tag action-tag" :class="actionTone[item.action]">{{ actionLabels[item.action] }}</span></td>
              <td class="muted num time-cell">{{ formatDateTime(item.created_at) }}</td>
              <td class="op-cell">
                <RouterLink class="btn small" :to="`/results/${item.result_id}`" :aria-label="`查看结果 ${item.result_id} 详情`">查看分析<ArrowRight :size="14" /></RouterLink>
              </td>
            </tr>
          </tbody>
        </table>

        <div v-if="loading" class="empty-hint"><span class="spinner dark"></span>正在加载记录…</div>
        <div v-else-if="!records.length && !errorMessage" class="empty-hint"><FileClock :size="28" /><strong>未找到检测记录</strong>请调整筛选条件后重新查询。</div>
      </div>

      <footer class="table-foot">
        <span class="num">显示 {{ rangeStart }}–{{ rangeEnd }}，共 {{ total }} 条</span>
        <div class="pager">
          <button type="button" class="btn icon small" aria-label="上一页" :disabled="page === 1 || loading" @click="changePage(page - 1)"><ChevronLeft :size="16" /></button>
          <span class="num">{{ page }} / {{ totalPages }}</span>
          <button type="button" class="btn icon small" aria-label="下一页" :disabled="page === totalPages || loading" @click="changePage(page + 1)"><ChevronRight :size="16" /></button>
        </div>
      </footer>
    </AppCard>
  </section>
</template>

<style scoped>
.filter-card { margin-bottom: 16px; }
.filters { display: grid; grid-template-columns: minmax(220px, 1.6fr) auto minmax(120px, .8fr) minmax(130px, .8fr) minmax(130px, .8fr) auto; align-items: end; gap: 14px; }
.input-icon { position: relative; display: block; }
.input-icon svg { position: absolute; top: 50%; left: 11px; color: var(--color-text-muted); transform: translateY(-50%); }
.input-icon .ui-input { padding-left: 34px; }
.segmented { display: inline-flex; padding: 4px; border-radius: var(--radius-control); background: var(--color-track); }
.segmented button { padding: 5px 12px; border: 0; border-radius: 7px; background: transparent; color: var(--color-text-secondary); font: inherit; font-size: 13px; line-height: 20px; cursor: pointer; white-space: nowrap; }
.segmented button.on { background: var(--color-surface); box-shadow: 0 1px 2px rgb(22 26 51 / 10%); color: var(--color-primary); font-weight: 600; }
.filter-actions { display: flex; gap: 8px; }

.table-wrap { overflow-x: auto; }
.table-wrap.loading .record-table { opacity: .45; }
.record-table { min-width: 900px; }
.review-cell { max-width: 340px; }
.review-cell strong { font-size: 13px; }
.review-cell p { margin: 2px 0 0; overflow: hidden; color: var(--color-text-secondary); text-overflow: ellipsis; white-space: nowrap; }
.prob-cell { white-space: nowrap; }
.prob { display: inline-block; width: 56px; height: 6px; margin: 0 6px 0 8px; overflow: hidden; border-radius: 3px; background: var(--color-track); vertical-align: middle; }
.prob i { display: block; height: 100%; border-radius: 3px; }
.prob.fake i { background: var(--color-fake); }
.prob.real i { background: var(--color-primary); }
.prob-cell small { color: var(--color-text-muted); font-size: 12px; }
.type-cell span { display: block; font-weight: 500; }
.type-cell small { color: var(--color-text-muted); font-size: 12px; }
.type-cell small.warn { color: var(--color-warn); }
.time-cell { white-space: nowrap; }
.op-cell { text-align: right; }
.retry { margin-left: auto; }
.table-foot { display: flex; align-items: center; justify-content: space-between; margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--color-line); color: var(--color-text-muted); font-size: 13px; }
.pager { display: flex; align-items: center; gap: 10px; }

@media (max-width: 1120px) {
  .filters { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .keyword-field { grid-column: span 2; }
}
@media (max-width: 860px) {
  .filters { grid-template-columns: 1fr; }
  .keyword-field { grid-column: auto; }
}
</style>
