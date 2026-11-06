<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRoute } from 'vue-router';
import { AlertCircle, ChevronLeft, ChevronRight, ClipboardCheck, FileClock, Info, RefreshCw, Search } from 'lucide-vue-next';
import { ApiError, getDetectionRecords } from '../api/client';
import type { Action, Authenticity, DetectionRecordItem } from '../types';
import AppCard from '../components/AppCard.vue';
import { actionLabels, actionTone, authenticityLabels, behaviorLabels, fakeProbabilityOf, formatDateTime, percent, semanticLabels } from '../labels';

// mode = review 时作为"待复核队列"：固定只看处置建议为人工复核的结果，隐藏处置建议筛选
const props = defineProps<{ mode?: 'all' | 'review' }>();
const isQueue = computed(() => props.mode === 'review');

// 顶栏搜索会带上 ?keyword=，进入页面时直接按关键词查询
const route = useRoute();
const filters = reactive({ keyword: typeof route?.query.keyword === 'string' ? route.query.keyword : '', authenticity: '' as Authenticity | '', action: '' as Action | '', date_from: '', date_to: '' });
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
// 虚假概率分三档着色：≥ 70% 高、≥ 50% 中、其余低
const probLevel = (value: number) => value >= 0.7 ? 'high' : value >= 0.5 ? 'mid' : 'low';

async function loadRecords() {
  loading.value = true;
  errorMessage.value = '';
  const action = isQueue.value ? 'review' : filters.action;
  try {
    const response = await getDetectionRecords({
      page: page.value,
      page_size: pageSize,
      ...(filters.keyword.trim() ? { keyword: filters.keyword.trim() } : {}),
      ...(filters.authenticity ? { authenticity: filters.authenticity } : {}),
      ...(action ? { action } : {}),
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
    <header class="page-title">
      <h1>{{ isQueue ? '待复核队列' : '检测记录' }}</h1>
      <span class="page-id">{{ isQueue ? '融合判定建议人工复核的检测结果，逐条查看分析后由审核员认定' : '单条检测与批量任务产生的全部检测结果' }}</span>
      <div class="page-actions"><span class="total-count num">共 <b>{{ total }}</b> 条</span></div>
    </header>

    <div v-if="isQueue" class="alert-bar warn queue-note"><ClipboardCheck :size="16" />以下结果的融合判定给出了“人工复核”建议，系统不会自动处置，请查看分析后由审核员认定。</div>

    <AppCard class="list-card">
      <form class="filters" :class="{ queue: isQueue }" @submit.prevent="search">
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
        <label v-if="!isQueue" class="ui-field">
          <span>处置建议</span>
          <select v-model="filters.action" class="ui-input action-select">
            <option value="">全部</option><option value="keep">保留</option><option value="review">人工复核</option><option value="block">拦截</option>
          </select>
        </label>
        <div class="ui-field date-field">
          <span>检测日期</span>
          <div class="date-range">
            <input v-model="filters.date_from" class="ui-input" type="date" aria-label="开始日期" />
            <i>至</i>
            <input v-model="filters.date_to" class="ui-input" type="date" aria-label="结束日期" />
          </div>
        </div>
        <div class="filter-actions">
          <button type="submit" class="btn primary" :disabled="loading"><Search :size="15" />查询</button>
          <button type="button" class="btn reset-filters" @click="resetFilters"><RefreshCw :size="15" />重置</button>
        </div>
      </form>

      <div v-if="errorMessage" class="alert-bar" role="alert">
        <AlertCircle :size="16" />{{ errorMessage }}
        <button type="button" class="btn small retry" @click="loadRecords">重新加载</button>
      </div>

      <div class="table-wrap" :class="{ loading }">
        <table class="ui-table record-table">
          <thead>
            <tr><th>评论</th><th>虚假概率</th><th>判定</th><th>语义类型</th><th>行为证据</th><th>处置建议</th><th>检测时间</th><th class="op-head">操作</th></tr>
          </thead>
          <tbody v-if="records.length">
            <tr v-for="item in records" :key="item.result_id">
              <td class="review-cell">
                <p :title="item.text_excerpt">{{ item.text_excerpt }}</p>
                <small class="num"><span>{{ item.review_id || `结果 #${item.result_id}` }}</span><span>商品 {{ item.product_id }}</span></small>
              </td>
              <td class="prob-cell">
                <span class="prob" :class="probLevel(fakeProbabilityOf(item))"><i :style="{ width: percent(fakeProbabilityOf(item)) }"></i></span>
                <b class="num" :class="probLevel(fakeProbabilityOf(item))">{{ percent(fakeProbabilityOf(item)) }}</b>
              </td>
              <td><span class="tag fixed auth-tag" :class="item.authenticity === 'fake' ? 'fake' : 'ok'">{{ authenticityLabels[item.authenticity] }}</span></td>
              <td>{{ semanticLabels[item.semantic_type] }}</td>
              <td class="behavior-cell" :class="{ insufficient: item.behavior_type === 'insufficient_evidence' }">{{ item.behavior_type === 'insufficient_evidence' ? '证据不足' : behaviorLabels[item.behavior_type] }}</td>
              <td><span class="tag dot action-tag" :class="actionTone[item.action]">{{ actionLabels[item.action] }}</span></td>
              <td class="muted num time-cell">{{ formatDateTime(item.created_at) }}</td>
              <td class="op-cell">
                <RouterLink class="btn text small" :to="`/results/${item.result_id}`" :aria-label="`查看结果 ${item.result_id} 详情`">{{ isQueue ? '去复核' : '查看分析' }}</RouterLink>
              </td>
            </tr>
          </tbody>
        </table>

        <div v-if="loading" class="empty-hint"><span class="spinner dark"></span>正在加载记录…</div>
        <div v-else-if="!records.length && !errorMessage" class="empty-hint"><FileClock :size="40" :stroke-width="1.4" /><strong>未找到检测记录</strong>请调整筛选条件后重新查询。</div>
      </div>

      <footer class="table-foot">
        <span class="num">显示 {{ rangeStart }}–{{ rangeEnd }}，共 {{ total }} 条</span>
        <div class="pager">
          <button type="button" class="btn icon small" aria-label="上一页" :disabled="page === 1 || loading" @click="changePage(page - 1)"><ChevronLeft :size="16" /></button>
          <span class="num page-no">{{ page }} / {{ totalPages }}</span>
          <button type="button" class="btn icon small" aria-label="下一页" :disabled="page === totalPages || loading" @click="changePage(page + 1)"><ChevronRight :size="16" /></button>
        </div>
      </footer>
    </AppCard>
    <p v-if="!isQueue" class="foot-note"><Info :size="13" />“证据不足”表示缺少可用的历史行为，不等于行为正常。</p>
  </section>
</template>

<style scoped>
.total-count { color: var(--color-text-secondary); font-size: 14px; }
.total-count b { color: var(--color-text); font-size: 18px; }
.queue-note { margin-bottom: 16px; }

/* 筛选区在列表卡片顶部，与表格之间用分隔线隔开 */
.filters { display: grid; grid-template-columns: minmax(220px, 1.4fr) auto minmax(120px, .7fr) minmax(300px, 1.4fr) auto; align-items: end; gap: 16px; margin-bottom: 20px; padding-bottom: 20px; border-bottom: 1px solid var(--color-line); }
.filters.queue { grid-template-columns: minmax(240px, 1.4fr) auto minmax(300px, 1.4fr) auto; }
.input-icon { position: relative; display: block; }
.input-icon svg { position: absolute; top: 50%; left: 11px; color: var(--color-text-muted); transform: translateY(-50%); }
.input-icon .ui-input { padding-left: 34px; }
.segmented { display: inline-flex; height: 32px; padding: 2px; border-radius: var(--radius-control); background: var(--color-track); }
.segmented button { padding: 0 12px; border: 0; border-radius: 4px; background: transparent; color: var(--color-text-secondary); font: inherit; font-size: 13px; cursor: pointer; white-space: nowrap; }
.segmented button:hover { color: var(--color-text); }
.segmented button.on { background: var(--color-surface); box-shadow: 0 1px 2px rgb(0 0 0 / 8%); color: var(--color-primary); font-weight: 500; }
.date-range { display: flex; align-items: center; gap: 8px; }
.date-range i { color: var(--color-text-muted); font-size: 13px; font-style: normal; }
.filter-actions { display: flex; gap: 8px; }

.table-wrap { overflow-x: auto; }
.table-wrap.loading .record-table { opacity: .45; }
.record-table { min-width: 1040px; }
.record-table th, .record-table td { padding-right: 12px; padding-left: 12px; }
.record-table td { white-space: nowrap; }
.review-cell { max-width: 300px; }
.review-cell p { margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.review-cell small { display: flex; max-width: 300px; gap: 12px; margin-top: 3px; overflow: hidden; color: var(--color-text-muted); font-size: 12px; white-space: nowrap; }
.prob-cell { white-space: nowrap; }
.prob { display: inline-block; width: 64px; height: 6px; margin-right: 8px; overflow: hidden; border-radius: 3px; background: var(--color-track); vertical-align: middle; }
.prob i { display: block; height: 100%; border-radius: 3px; }
.prob.high i { background: var(--color-fake); }
.prob.mid i { background: var(--color-warn); }
.prob.low i { background: var(--color-primary); }
.prob-cell b { font-size: 13px; font-weight: 600; }
.prob-cell b.high { color: var(--color-fake); }
.prob-cell b.mid { color: var(--color-warn); }
.prob-cell b.low { color: var(--color-text-secondary); }
.behavior-cell { white-space: nowrap; }
.behavior-cell.insufficient { color: var(--color-text-muted); }
.time-cell { white-space: nowrap; }
.op-head, .op-cell { text-align: right; }
.retry { margin-left: auto; }
.table-foot { display: flex; align-items: center; justify-content: space-between; margin-top: 16px; color: var(--color-text-muted); font-size: 13px; }
.pager { display: flex; align-items: center; gap: 10px; }
.page-no { min-width: 48px; color: var(--color-text); text-align: center; }
.foot-note { display: flex; align-items: center; gap: 6px; margin: 12px 0 0; color: var(--color-text-muted); font-size: 12px; }

@media (max-width: 1240px) {
  .filters, .filters.queue { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 860px) {
  .filters, .filters.queue { grid-template-columns: 1fr; }
}
</style>
