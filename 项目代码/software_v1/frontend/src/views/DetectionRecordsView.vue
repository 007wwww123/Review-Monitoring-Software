<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import {
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  Eye,
  FileClock,
  RefreshCw,
  Search,
  SlidersHorizontal,
} from 'lucide-vue-next';
import { ApiError, getDetectionRecords } from '../api/client';
import type { Action, Authenticity, BehaviorType, DetectionRecordItem, SemanticType } from '../types';

const filters = reactive({ keyword: '', authenticity: '' as Authenticity | '', action: '' as Action | '', date_from: '', date_to: '' });
const records = ref<DetectionRecordItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = 10;
const loading = ref(false);
const errorMessage = ref('');
const evidenceMode = new URLSearchParams(window.location.search).get('mode') === 'evidence';

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)));
const rangeStart = computed(() => total.value ? (page.value - 1) * pageSize + 1 : 0);
const rangeEnd = computed(() => Math.min(page.value * pageSize, total.value));
const authenticityLabels: Record<Authenticity, string> = { real: '真实', fake: '疑似虚假' };
const semanticLabels: Record<SemanticType, string> = { real: '真实语义', misleading: '误导性', exaggerated: '夸张性', advertising: '广告性', none: '无', uncertain: '不确定' };
const behaviorLabels: Record<BehaviorType, string> = { normal: '行为正常', review_manipulation: '评论操纵', crowdturfing: '群体操纵', bot_like: '机器行为', insufficient_evidence: '证据不足' };
const actionLabels: Record<Action, string> = { keep: '保留', review: '人工复核', block: '拦截' };

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

function resetFilters() {
  Object.assign(filters, { keyword: '', authenticity: '', action: '', date_from: '', date_to: '' });
  page.value = 1;
  void loadRecords();
}

function changePage(nextPage: number) {
  if (nextPage < 1 || nextPage > totalPages.value || loading.value) return;
  page.value = nextPage;
  void loadRecords();
}

onMounted(loadRecords);
</script>

<template>
  <section class="page-content">
    <div class="page-heading records-heading">
      <div>
        <span class="eyebrow">{{ evidenceMode ? '内容审核 / 证据查询' : '内容审核 / 记录查询' }}</span>
        <h1>{{ evidenceMode ? '结果与证据' : '检测记录' }}</h1>
        <p>{{ evidenceMode ? '选择一条检测记录，查看模型输出、证据状态与解释边界。' : '查询单条与批量任务产生的检测结果摘要。' }}</p>
      </div>
      <span class="api-state"><span></span>Mock 数据集 · {{ total }} 条</span>
    </div>

    <section class="records-panel">
      <form class="records-filters" @submit.prevent="search">
        <label class="filter-field keyword-filter"><span>关键词</span><div class="input-with-icon"><Search :size="15" /><input v-model="filters.keyword" placeholder="评论 ID、用户、商品或内容" /></div></label>
        <label class="filter-field"><span>真实性</span><select v-model="filters.authenticity"><option value="">全部</option><option value="real">真实</option><option value="fake">疑似虚假</option></select></label>
        <label class="filter-field"><span>处置建议</span><select v-model="filters.action"><option value="">全部</option><option value="keep">保留</option><option value="review">人工复核</option><option value="block">拦截</option></select></label>
        <label class="filter-field"><span>开始日期</span><input v-model="filters.date_from" type="date" /></label>
        <label class="filter-field"><span>结束日期</span><input v-model="filters.date_to" type="date" /></label>
        <div class="filter-actions">
          <button type="button" class="icon-text-button secondary" @click="resetFilters"><RefreshCw :size="15" />重置</button>
          <button type="submit" class="primary-button records-search" :disabled="loading"><SlidersHorizontal :size="16" />筛选</button>
        </div>
      </form>

      <div v-if="errorMessage" class="alert error records-alert" role="alert"><AlertCircle :size="18" /><span>{{ errorMessage }}</span><button type="button" @click="loadRecords">重新加载</button></div>

      <div class="records-table-wrap" :class="{ loading }">
        <table class="records-table">
          <thead><tr><th>检测时间</th><th>评论信息</th><th>真实性</th><th>语义 / 行为</th><th>处置</th><th>模型版本</th><th><span class="sr-only">操作</span></th></tr></thead>
          <tbody v-if="records.length">
            <tr v-for="item in records" :key="item.result_id">
              <td class="record-time"><strong>{{ new Date(item.created_at).toLocaleDateString('zh-CN') }}</strong><span>{{ new Date(item.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }}</span></td>
              <td class="record-review"><div><strong>{{ item.review_id || `结果 ${item.result_id}` }}</strong><span>{{ item.user_key }} · {{ item.product_id }}</span></div><p>{{ item.text_excerpt }}</p></td>
              <td><span class="authenticity-label" :class="item.authenticity">{{ authenticityLabels[item.authenticity] }}</span><small class="confidence-text">{{ Math.round(item.confidence * 100) }}%</small></td>
              <td class="type-stack"><span>{{ semanticLabels[item.semantic_type] }}</span><small :class="{ warning: item.behavior_type === 'insufficient_evidence' }">{{ behaviorLabels[item.behavior_type] }}</small></td>
              <td><span class="action-badge" :class="item.action">{{ actionLabels[item.action] }}</span></td>
              <td class="mono model-cell">{{ item.model_version }}</td>
              <td><RouterLink class="icon-button record-view" :to="`/results/${item.result_id}`" title="查看结果与证据" :aria-label="`查看结果 ${item.result_id} 详情`"><Eye :size="17" /></RouterLink></td>
            </tr>
          </tbody>
        </table>

        <div v-if="loading" class="records-loading"><span class="spinner dark"></span><span>正在加载记录…</span></div>
        <div v-else-if="!records.length && !errorMessage" class="records-empty"><FileClock :size="28" /><strong>未找到检测记录</strong><p>请调整筛选条件后重新查询。</p></div>
      </div>

      <footer class="records-footer">
        <span>显示 {{ rangeStart }}–{{ rangeEnd }}，共 {{ total }} 条</span>
        <div class="pagination">
          <button type="button" class="icon-button" aria-label="上一页" :disabled="page === 1 || loading" @click="changePage(page - 1)"><ChevronLeft :size="17" /></button>
          <span>{{ page }} / {{ totalPages }}</span>
          <button type="button" class="icon-button" aria-label="下一页" :disabled="page === totalPages || loading" @click="changePage(page + 1)"><ChevronRight :size="17" /></button>
        </div>
      </footer>
    </section>
  </section>
</template>
