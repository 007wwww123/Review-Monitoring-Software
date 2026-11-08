<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRoute } from 'vue-router';
import { AlertCircle, ChevronLeft, ChevronRight, ClipboardCheck, FileClock, History, Info, RefreshCw, RotateCcw, Search } from 'lucide-vue-next';
import { ApiError, getDetectionRecords } from '../api/client';
import type { Action, Authenticity, DetectionRecordItem, DetectionRecordQuery } from '../types';
import AppCard from '../components/AppCard.vue';
import PageHeader from '../components/layout/PageHeader.vue';
import { actionLabels, actionTone, authenticityLabels, behaviorLabels, fakeProbabilityOf, formatDateTime, percent, semanticLabels, shortId } from '../labels';

// mode = review 时作为"待复核队列"：固定只看处置建议为人工复核的结果，隐藏处置建议筛选
const props = defineProps<{ mode?: 'all' | 'review' }>();
const isQueue = computed(() => props.mode === 'review');

// 顶栏搜索会带上 ?keyword=，进入页面时直接按关键词查询
const route = useRoute();
const filters = reactive({ keyword: typeof route?.query.keyword === 'string' ? route.query.keyword : '', authenticity: '' as Authenticity | '', action: '' as Action | '', date_from: '', date_to: '' });
const records = ref<DetectionRecordItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(10);
const pageSizeOptions = [10, 20, 50];
const loading = ref(false);
const errorMessage = ref('');
const updatedAt = ref('');

// 页头数字不受筛选影响；标签页上的条数随关键词、日期等筛选变化
const head = reactive({ total: null as number | null, fake: null as number | null, latest: '' });
const tabCounts = reactive({ fake: null as number | null, real: null as number | null });

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)));
const rangeStart = computed(() => total.value ? (page.value - 1) * pageSize.value + 1 : 0);
const rangeEnd = computed(() => Math.min(page.value * pageSize.value, total.value));
const authenticityOptions = computed(() => {
  const all = tabCounts.fake === null || tabCounts.real === null ? null : tabCounts.fake + tabCounts.real;
  return [
    { value: '' as const, label: '全部', count: all },
    { value: 'fake' as const, label: '疑似虚假', count: tabCounts.fake },
    { value: 'real' as const, label: '真实', count: tabCounts.real },
  ];
});
// 页码：不超过 7 页全部列出，否则保留首尾和当前页前后各一页，中间用省略号
const pageItems = computed<(number | '…')[]>(() => {
  const last = totalPages.value;
  if (last <= 7) return Array.from({ length: last }, (_, i) => i + 1);
  const start = Math.max(2, Math.min(page.value - 1, last - 4));
  const end = Math.min(last - 1, Math.max(page.value + 1, 5));
  return [1, ...(start > 2 ? ['…' as const] : []), ...Array.from({ length: end - start + 1 }, (_, i) => start + i), ...(end < last - 1 ? ['…' as const] : []), last];
});
// 虚假概率分三档着色：≥ 70% 高、≥ 50% 中、其余低
const probLevel = (value: number) => value >= 0.7 ? 'high' : value >= 0.5 ? 'mid' : 'low';

// 列表和计数共用的筛选条件（不含真实性，真实性由标签页决定）
function baseQuery(): Omit<DetectionRecordQuery, 'page' | 'page_size'> {
  const action = isQueue.value ? 'review' : filters.action;
  return {
    ...(filters.keyword.trim() ? { keyword: filters.keyword.trim() } : {}),
    ...(action ? { action } : {}),
    ...(filters.date_from ? { date_from: filters.date_from } : {}),
    ...(filters.date_to ? { date_to: filters.date_to } : {}),
  };
}
const countOf = (query: Omit<DetectionRecordQuery, 'page' | 'page_size'>) => getDetectionRecords({ ...query, page: 1, page_size: 1 });

async function loadRecords() {
  loading.value = true;
  errorMessage.value = '';
  const query = baseQuery();
  const counts = Promise.allSettled([countOf({ ...query, authenticity: 'fake' }), countOf({ ...query, authenticity: 'real' })]);
  try {
    const response = await getDetectionRecords({
      ...query,
      ...(filters.authenticity ? { authenticity: filters.authenticity } : {}),
      page: page.value,
      page_size: pageSize.value,
    });
    records.value = response.items;
    total.value = response.total;
    updatedAt.value = new Date().toLocaleTimeString('zh-CN', { hour12: false });
  } catch (error) {
    records.value = [];
    total.value = 0;
    errorMessage.value = error instanceof ApiError ? error.message : '检测记录加载失败，请稍后重试。';
  } finally {
    loading.value = false;
  }
  const [fake, real] = await counts;
  tabCounts.fake = fake.status === 'fulfilled' ? fake.value.total : null;
  tabCounts.real = real.status === 'fulfilled' ? real.value.total : null;
}

async function loadHeadStats() {
  const query = isQueue.value ? { action: 'review' as const } : {};
  const [all, fake] = await Promise.allSettled([countOf(query), countOf({ ...query, authenticity: 'fake' })]);
  head.total = all.status === 'fulfilled' ? all.value.total : null;
  head.latest = all.status === 'fulfilled' ? all.value.items[0]?.created_at ?? '' : '';
  head.fake = fake.status === 'fulfilled' ? fake.value.total : null;
}

function search() {
  page.value = 1;
  void loadRecords();
}

function refresh() {
  void loadRecords();
  void loadHeadStats();
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

onMounted(() => {
  void loadRecords();
  void loadHeadStats();
});
</script>

<template>
  <section class="page records-page">
    <PageHeader
      :title="isQueue ? '待复核队列' : '检测记录'"
      :desc="isQueue ? '融合判定建议人工复核的检测结果。系统不会自动处置，请逐条查看分析后由审核员认定。' : '单条检测与批量任务产生的全部检测结果，可按关键词、处置建议和日期筛选。'"
      :icon="isQueue ? ClipboardCheck : History"
    >
      <template #actions>
        <dl class="head-stats">
          <div><dt>{{ isQueue ? '待复核' : '检测记录' }}</dt><dd class="num">{{ head.total ?? '—' }}<small>条</small></dd></div>
          <div><dt>其中疑似虚假</dt><dd class="num">{{ head.fake ?? '—' }}<small>条</small></dd></div>
          <div><dt>{{ isQueue ? '最近进入队列' : '最近检测' }}</dt><dd class="num text">{{ head.latest ? formatDateTime(head.latest) : '—' }}</dd></div>
        </dl>
      </template>
    </PageHeader>

    <AppCard class="list-card">
      <form class="filters" :class="{ queue: isQueue }" @submit.prevent="search">
        <label class="ui-field inline keyword-field">
          <span>关键词</span>
          <span class="input-icon"><Search :size="15" /><input v-model="filters.keyword" class="ui-input" placeholder="评论 ID、用户、商品或评论内容" /></span>
        </label>
        <label v-if="!isQueue" class="ui-field inline">
          <span>处置建议</span>
          <select v-model="filters.action" class="ui-input action-select">
            <option value="">全部</option><option value="keep">保留</option><option value="review">人工复核</option><option value="block">拦截</option>
          </select>
        </label>
        <div class="ui-field inline date-field">
          <span>检测日期</span>
          <div class="date-range">
            <input v-model="filters.date_from" class="ui-input" type="date" aria-label="开始日期" />
            <i>至</i>
            <input v-model="filters.date_to" class="ui-input" type="date" aria-label="结束日期" />
          </div>
        </div>
        <div class="filter-actions">
          <button type="submit" class="btn primary" :disabled="loading"><Search :size="15" />查询</button>
          <button type="button" class="btn reset-filters" @click="resetFilters"><RotateCcw :size="15" />重置</button>
        </div>
      </form>

      <div class="table-toolbar">
        <div class="auth-tabs" role="tablist" aria-label="真实性">
          <button
            v-for="option in authenticityOptions" :key="option.value" type="button" role="tab"
            :aria-selected="filters.authenticity === option.value" :class="{ on: filters.authenticity === option.value }"
            @click="chooseAuthenticity(option.value)"
          >{{ option.label }}<em class="num">{{ option.count ?? '—' }}</em></button>
        </div>
        <div class="toolbar-tools">
          <span v-if="updatedAt" class="num updated">更新于 {{ updatedAt }}</span>
          <button type="button" class="btn icon" title="刷新" aria-label="刷新列表" :disabled="loading" @click="refresh"><RefreshCw :size="15" /></button>
        </div>
      </div>

      <div v-if="errorMessage" class="alert-bar" role="alert">
        <AlertCircle :size="16" />{{ errorMessage }}
        <button type="button" class="btn small retry" @click="loadRecords">重新加载</button>
      </div>

      <div class="table-wrap" :class="{ loading }">
        <table class="ui-table record-table">
          <thead>
            <tr>
              <th class="review-head">评论</th><th>虚假概率</th><th>判定</th><th>语义类型</th>
              <th>行为证据<span class="tip head-tip" tabindex="0" aria-label="行为证据说明"><Info :size="13" /><span class="tip-body">“证据不足”表示缺少可用的历史行为，不等于行为正常。</span></span></th>
              <th>处置建议</th><th>检测时间</th><th class="op-head">操作</th>
            </tr>
          </thead>
          <tbody v-if="records.length">
            <tr v-for="item in records" :key="item.result_id">
              <td class="review-cell">
                <p :title="item.text_excerpt">{{ item.text_excerpt }}</p>
                <small class="num"><span>{{ item.review_id || `结果 #${item.result_id}` }}</span><span :title="item.user_key">用户 {{ shortId(item.user_key, 6) }}</span><span>商品 {{ item.product_id }}</span></small>
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
                <RouterLink class="btn text small" :to="`/results/${item.result_id}`" :aria-label="`查看结果 ${item.result_id} 详情`">{{ isQueue ? '去复核' : '查看分析' }}<ChevronRight :size="14" /></RouterLink>
              </td>
            </tr>
          </tbody>
        </table>

        <div v-if="loading && !records.length" class="empty-hint"><span class="spinner dark"></span>正在加载记录…</div>
        <div v-else-if="!records.length && !errorMessage" class="empty-hint"><FileClock :size="40" :stroke-width="1.4" /><strong>未找到检测记录</strong>请调整筛选条件后重新查询。</div>
      </div>

      <footer class="table-foot">
        <span class="num">显示 {{ rangeStart }}–{{ rangeEnd }}，共 {{ total }} 条</span>
        <div class="pager">
          <select v-model.number="pageSize" class="ui-input size-select" aria-label="每页条数" @change="search">
            <option v-for="size in pageSizeOptions" :key="size" :value="size">{{ size }} 条/页</option>
          </select>
          <button type="button" class="btn icon small" aria-label="上一页" :disabled="page === 1 || loading" @click="changePage(page - 1)"><ChevronLeft :size="16" /></button>
          <template v-for="(item, index) in pageItems" :key="`${item}-${index}`">
            <span v-if="item === '…'" class="ellipsis">…</span>
            <button
              v-else type="button" class="btn icon small num page-btn" :class="{ on: item === page }"
              :aria-current="item === page ? 'page' : undefined" :disabled="loading" @click="changePage(item)"
            >{{ item }}</button>
          </template>
          <button type="button" class="btn icon small" aria-label="下一页" :disabled="page === totalPages || loading" @click="changePage(page + 1)"><ChevronRight :size="16" /></button>
        </div>
      </footer>
    </AppCard>
  </section>
</template>

<style scoped>
.list-card { padding: 0; }

/* 查询区：标签在输入框左侧，查询/重置固定在最右列。日期范围要放两个输入框，列宽给得最多；
   待复核队列没有处置建议，留一段空列，让两页的输入框宽度接近 */
.filters { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, .8fr) minmax(0, 1.5fr) auto; align-items: center; gap: 16px 32px; padding: 20px 24px; border-bottom: 1px solid var(--color-line); }
.filters.queue { grid-template-columns: minmax(0, 1fr) minmax(0, 1.3fr) minmax(0, .5fr) auto; }
.ui-field.inline { flex-direction: row; align-items: center; gap: 12px; }
.ui-field.inline > span:first-child { flex: none; width: 56px; color: var(--color-text-secondary); font-size: 14px; }
.input-icon { position: relative; display: block; flex: 1; min-width: 0; }
.input-icon svg { position: absolute; top: 50%; left: 11px; color: var(--color-text-muted); transform: translateY(-50%); }
.input-icon .ui-input { padding-left: 34px; }
.action-select { flex: 1; }
.date-range { display: flex; flex: 1; min-width: 0; align-items: center; gap: 8px; }
.date-range i { color: var(--color-text-muted); font-size: 13px; font-style: normal; }
.filter-actions { display: flex; grid-column: -2; gap: 8px; }

/* 表格上方：左侧真实性标签页（带条数），右侧更新时间与刷新 */
.table-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 0 24px; border-bottom: 1px solid var(--color-line); }
.auth-tabs { display: flex; gap: 28px; }
.auth-tabs button { position: relative; display: flex; align-items: center; gap: 6px; height: 52px; padding: 0; border: 0; background: transparent; color: var(--color-text-secondary); font: inherit; font-size: 14px; cursor: pointer; }
.auth-tabs button:hover { color: var(--color-text); }
.auth-tabs button em { min-width: 22px; height: 20px; padding: 0 6px; border-radius: 10px; background: var(--color-track); color: var(--color-text-secondary); font-size: 12px; font-style: normal; line-height: 20px; text-align: center; }
.auth-tabs button.on { color: var(--color-primary); font-weight: 500; }
.auth-tabs button.on em { background: var(--color-primary-soft); color: var(--color-primary); }
.auth-tabs button.on::after { position: absolute; right: 0; bottom: -1px; left: 0; height: 2px; border-radius: 1px; background: var(--color-primary); content: ""; }
.toolbar-tools { display: flex; align-items: center; gap: 12px; }
.updated { color: var(--color-text-muted); font-size: 12px; }

.list-card > .alert-bar { margin: 16px 24px 0; }
.retry { margin-left: auto; }
.table-wrap { padding: 0 24px; overflow-x: auto; }
.table-wrap.loading .record-table { opacity: .45; }
.record-table { min-width: 960px; }
.record-table th { height: 44px; background: transparent; }
.record-table th, .record-table td { padding-right: 12px; padding-left: 12px; }
.record-table td { padding-top: 14px; padding-bottom: 14px; white-space: nowrap; }
/* 评论列吃掉多余宽度，超出部分省略 */
.review-head { width: 36%; }
.review-cell { max-width: 0; }
.review-cell p { margin: 0; overflow: hidden; color: var(--color-text); font-weight: 500; text-overflow: ellipsis; white-space: nowrap; }
.review-cell small { display: flex; gap: 14px; margin-top: 4px; overflow: hidden; color: var(--color-text-muted); font-size: 12px; white-space: nowrap; }
.head-tip { margin-left: 4px; vertical-align: -2px; }
.head-tip .tip-body { right: auto; left: -12px; width: 240px; }
.prob-cell { white-space: nowrap; }
.prob { display: inline-block; width: 72px; height: 6px; margin-right: 8px; overflow: hidden; border-radius: 3px; background: var(--color-track); vertical-align: middle; }
.prob i { display: block; height: 100%; border-radius: 3px; }
.prob.high i { background: var(--color-fake); }
.prob.mid i { background: var(--color-warn); }
.prob.low i { background: var(--color-primary); }
.prob-cell b { font-size: 13px; font-weight: 600; }
.prob-cell b.high { color: var(--color-fake); }
.prob-cell b.mid { color: var(--color-warn); }
.prob-cell b.low { color: var(--color-text-secondary); }
.behavior-cell.insufficient { color: var(--color-text-muted); }
.op-head, .op-cell { text-align: right; }
.op-cell .btn { gap: 2px; }
.record-table tbody tr:last-child td { border-bottom: 0; }

/* 底部：左侧范围与总数，右侧每页条数 + 页码 */
.table-foot { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 14px 24px; border-top: 1px solid var(--color-line); color: var(--color-text-muted); font-size: 13px; }
.pager { display: flex; align-items: center; gap: 6px; }
.size-select { width: auto; height: 28px; margin-right: 8px; padding-left: 10px; font-size: 13px; }
.page-btn { min-width: 28px; width: auto; padding: 0 6px; border-color: transparent; color: var(--color-text-secondary); font-size: 13px; }
.page-btn.on { border-color: var(--color-primary); background: var(--color-primary-soft); color: var(--color-primary); font-weight: 600; }
.ellipsis { width: 20px; color: var(--color-text-muted); text-align: center; }

@media (max-width: 1360px) {
  .filters, .filters.queue { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .filter-actions { grid-column: auto; justify-content: flex-end; }
}
@media (max-width: 860px) {
  .filters, .filters.queue { grid-template-columns: 1fr; padding: 16px; }
  .table-toolbar, .table-wrap, .table-foot { padding-right: 16px; padding-left: 16px; }
  .updated { display: none; }
  .table-foot { flex-direction: column; align-items: flex-start; }
}
</style>
