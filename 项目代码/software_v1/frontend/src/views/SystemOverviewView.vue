<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { AlertCircle, ArrowRight, ClipboardCheck, Database, FileSearch, Info, Layers3, RefreshCw, ShieldAlert, UserX } from 'lucide-vue-next';
import { ApiError, getDetectionRecords, getServiceHealth } from '../api/client';
import type { DetectionRecordItem } from '../types';
import AppCard from '../components/AppCard.vue';
import ScoreBars from '../components/ScoreBars.vue';
import DonutChart from '../components/charts/DonutChart.vue';
import TrendChart from '../components/charts/TrendChart.vue';
import { SEMANTIC_ORDER, actionLabels, actionTone, authenticityLabels, fakeProbabilityOf, formatDateTime, parseServerTime, percent, semanticLabels } from '../labels';
import { getSession } from '../auth';

const records = ref<DetectionRecordItem[]>([]);
const total = ref(0);
const loading = ref(true);
const errorMessage = ref('');
const health = ref<{ status: string; model?: string } | null>(null);
const username = getSession()?.username ?? '';

// 健康检查：ok = 模型已加载；degraded = 接口在线但模型未就绪；请求失败 = 服务不可用
const serviceState = computed(() => {
  if (!health.value) return { label: '检测服务不可用', tone: 'fake' };
  if (health.value.status === 'ok') return { label: '检测服务正常', tone: 'ok' };
  return { label: '模型未就绪', tone: 'warn' };
});
const modelState = computed(() => {
  if (!health.value) return '未知';
  return health.value.model === 'not_ready' || health.value.status !== 'ok' ? '未就绪' : '已加载';
});

const sampleSize = computed(() => records.value.length);
const countBy = (predicate: (item: DetectionRecordItem) => boolean) => records.value.filter(predicate).length;
const fakeCount = computed(() => countBy((item) => item.authenticity === 'fake'));
const reviewCount = computed(() => countBy((item) => item.action === 'review'));
const insufficientCount = computed(() => countBy((item) => item.behavior_type === 'insufficient_evidence'));
const fakeRate = computed(() => sampleSize.value ? fakeCount.value / sampleSize.value : 0);
const ratio = (count: number) => sampleSize.value ? count / sampleSize.value : 0;

const authenticityParts = computed(() => [
  { key: 'fake', label: authenticityLabels.fake, value: fakeCount.value, tone: 'fake' as const },
  { key: 'real', label: authenticityLabels.real, value: sampleSize.value - fakeCount.value, tone: 'primary' as const },
]);
const actionItems = computed(() => ([
  { key: 'keep', label: '保留', tone: 'success' as const },
  { key: 'review', label: '人工复核', tone: 'warn' as const },
  { key: 'block', label: '拦截', tone: 'fake' as const },
]).map((item) => {
  const count = countBy((record) => record.action === item.key);
  return { ...item, value: ratio(count), text: `${count} 条` };
}));
const semanticItems = computed(() => SEMANTIC_ORDER.map((key) => {
  const count = countBy((record) => record.semantic_type === key);
  return { key, label: semanticLabels[key], value: ratio(count), text: `${count} 条`, tone: 'primary' as const };
}));

// 近 7 天（含今天）每天的检测数，按本地日期归并
const trendDays = computed(() => {
  const pad = (n: number) => String(n).padStart(2, '0');
  const keyOf = (date: Date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  const today = new Date();
  const days = Array.from({ length: 7 }, (_, i) => {
    const date = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 6 + i);
    return { key: keyOf(date), label: `${pad(date.getMonth() + 1)}-${pad(date.getDate())}`, fake: 0, real: 0 };
  });
  const byKey = new Map(days.map((day) => [day.key, day]));
  for (const item of records.value) {
    const day = byKey.get(keyOf(parseServerTime(item.created_at)));
    if (day) day[item.authenticity] += 1;
  }
  return days;
});
const trendTotal = computed(() => trendDays.value.reduce((sum, day) => sum + day.fake + day.real, 0));
const today = new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' }).format(new Date());

async function loadOverview() {
  loading.value = true;
  errorMessage.value = '';
  try {
    const [healthResponse, response] = await Promise.all([
      getServiceHealth(),
      getDetectionRecords({ page: 1, page_size: 100 }),
    ]);
    health.value = healthResponse;
    records.value = response.items;
    total.value = response.total;
  } catch (error) {
    health.value = null;
    errorMessage.value = error instanceof ApiError ? error.message : '概览数据加载失败，请稍后重试。';
  } finally {
    loading.value = false;
  }
}

onMounted(loadOverview);
</script>

<template>
  <section class="page overview-page">
    <nav class="crumb" aria-label="面包屑">工作台 / <b>系统概览</b></nav>
    <header class="page-title">
      <h1>系统概览</h1>
      <span class="page-id">{{ username ? `欢迎回来，${username}。` : '' }}今天是 {{ today }}</span>
      <div class="page-actions">
        <span class="tag dot service-tag" :class="serviceState.tone">{{ serviceState.label }}</span>
        <button type="button" class="btn" :disabled="loading" @click="loadOverview"><RefreshCw :size="14" />刷新</button>
      </div>
    </header>

    <div v-if="errorMessage" class="alert-bar" role="alert">
      <AlertCircle :size="16" />{{ errorMessage }}
      <button type="button" class="btn small retry" @click="loadOverview"><RefreshCw :size="14" />重新加载</button>
    </div>

    <div class="stats" :class="{ loading }">
      <article class="stat">
        <div class="stat-head"><span class="stat-label">检测记录总数</span><strong class="num">{{ loading ? '—' : total }}</strong></div>
        <span class="stat-icon blue"><Database :size="22" /></span>
        <small class="stat-foot">全部单条与批量检测结果</small>
      </article>
      <article class="stat">
        <div class="stat-head"><span class="stat-label">疑似虚假样本</span><strong class="num">{{ loading ? '—' : fakeCount }}</strong></div>
        <span class="stat-icon red"><ShieldAlert :size="22" /></span>
        <small class="stat-foot num">最近 {{ sampleSize }} 条中占 <b class="fake-rate">{{ percent(fakeRate) }}</b></small>
      </article>
      <article class="stat">
        <div class="stat-head"><span class="stat-label">待人工复核</span><strong class="num">{{ loading ? '—' : reviewCount }}</strong></div>
        <span class="stat-icon orange"><ClipboardCheck :size="22" /></span>
        <RouterLink to="/review" class="stat-foot link">进入待复核队列<ArrowRight :size="13" /></RouterLink>
      </article>
      <article class="stat">
        <div class="stat-head"><span class="stat-label">行为证据不足</span><strong class="num">{{ loading ? '—' : insufficientCount }}</strong></div>
        <span class="stat-icon purple"><UserX :size="22" /></span>
        <small class="stat-foot">缺少历史行为，不能视为行为正常</small>
      </article>
    </div>

    <div class="row-trend">
      <AppCard title="检测趋势" :subtitle="`近 7 天共 ${trendTotal} 条（最近 ${sampleSize} 条记录内）`">
        <template #extra>
          <ul class="legend inline"><li><i class="real"></i>真实</li><li><i class="fake"></i>疑似虚假</li></ul>
        </template>
        <TrendChart :days="trendDays" />
      </AppCard>
      <AppCard title="真实性分布" :subtitle="`最近 ${sampleSize} 条检测结果`" class="donut-card">
        <DonutChart :parts="authenticityParts" :center="percent(fakeRate)" caption="疑似虚假占比" />
        <ul class="legend">
          <li><i class="fake"></i>疑似虚假<b class="num">{{ fakeCount }} 条</b></li>
          <li><i class="real"></i>真实<b class="num">{{ sampleSize - fakeCount }} 条</b></li>
        </ul>
      </AppCard>
    </div>

    <div class="grid-3 row-dist">
      <AppCard title="处置建议分布" subtitle="融合判定给出的审核建议">
        <ScoreBars :items="actionItems" />
      </AppCard>
      <AppCard title="语义类型分布" subtitle="ALBERT 语义匹配度最高的类型">
        <ScoreBars :items="semanticItems" />
      </AppCard>
      <AppCard title="运行状态" subtitle="来自健康检查接口">
        <dl class="runtime">
          <div><dt>接口服务</dt><dd><span class="status-dot" :class="health ? 'ok' : 'fake'"></span>{{ health ? '可访问' : '不可访问' }}</dd></div>
          <div><dt>检测模型</dt><dd><span class="status-dot" :class="modelState === '已加载' ? 'ok' : 'warn'"></span>{{ modelState }}</dd></div>
          <div><dt>统计范围</dt><dd>最近 100 条</dd></div>
        </dl>
      </AppCard>
    </div>
    <p class="scope-note"><Info :size="14" />统计口径：当前加载的最近 100 条记录。页面统计用于工作量观察，不代表模型效果评估；检测结果仅辅助审核，不替代人工认定。</p>

    <div class="row-bottom">
      <AppCard title="最近检测">
        <template #extra><RouterLink to="/results" class="btn text small">查看全部<ArrowRight :size="14" /></RouterLink></template>
        <div v-if="loading" class="empty-hint"><span class="spinner dark"></span>正在加载记录…</div>
        <div v-else-if="!records.length" class="empty-hint">暂无检测记录</div>
        <div v-else class="recent">
          <RouterLink v-for="item in records.slice(0, 5)" :key="item.result_id" :to="`/results/${item.result_id}`" class="recent-row">
            <span class="prob num" :class="item.authenticity">{{ percent(fakeProbabilityOf(item), 0) }}</span>
            <div class="recent-text"><p>{{ item.text_excerpt }}</p><small class="num">{{ item.review_id || `结果 #${item.result_id}` }} · {{ formatDateTime(item.created_at) }}</small></div>
            <span class="tag fixed" :class="item.authenticity === 'fake' ? 'fake' : 'ok'">{{ authenticityLabels[item.authenticity] }}</span>
            <span class="tag fixed" :class="actionTone[item.action]">{{ actionLabels[item.action] }}</span>
          </RouterLink>
        </div>
      </AppCard>

      <AppCard title="快捷入口">
        <div class="quick-list">
          <RouterLink to="/detections/single" class="quick"><span class="quick-icon blue"><FileSearch :size="20" /></span><div><strong>单条评论检测</strong><small>录入一条评论及可选行为历史</small></div><ArrowRight :size="16" /></RouterLink>
          <RouterLink to="/detections/batch" class="quick"><span class="quick-icon purple"><Layers3 :size="20" /></span><div><strong>批量检测任务</strong><small>导入 CSV 或 TSV 文件</small></div><ArrowRight :size="16" /></RouterLink>
          <RouterLink to="/review" class="quick"><span class="quick-icon orange"><ClipboardCheck :size="20" /></span><div><strong>待复核队列</strong><small>处理建议人工复核的结果</small></div><ArrowRight :size="16" /></RouterLink>
        </div>
      </AppCard>
    </div>
  </section>
</template>

<style scoped>
.retry { margin-left: auto; }

/* 指标卡：左上标签和数字，右上彩色图标块，底部一行说明 */
.stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; margin-bottom: 16px; }
.stats.loading { opacity: .6; }
.stat { display: grid; grid-template-columns: 1fr auto; row-gap: 14px; padding: 20px; border-radius: var(--radius-card); background: var(--color-surface); box-shadow: var(--shadow-card); }
.stat-head { display: flex; flex-direction: column; gap: 6px; }
.stat-label { color: var(--color-text-secondary); font-size: 14px; }
.stat strong { font-size: 30px; font-weight: 600; line-height: 38px; }
.stat-icon { display: grid; width: 48px; height: 48px; place-items: center; border-radius: 12px; }
.stat-icon.blue, .quick-icon.blue { background: var(--color-primary-soft); color: var(--color-primary); }
.stat-icon.red { background: var(--color-fake-soft); color: var(--color-fake); }
.stat-icon.orange, .quick-icon.orange { background: var(--color-warn-soft); color: var(--color-warn); }
.stat-icon.purple, .quick-icon.purple { background: var(--color-behavior-soft); color: var(--color-behavior); }
.stat-foot { display: flex; grid-column: span 2; align-items: center; gap: 4px; padding-top: 12px; border-top: 1px solid var(--color-line); color: var(--color-text-muted); font-size: 13px; text-decoration: none; }
.stat-foot .fake-rate { color: var(--color-fake); font-weight: 600; }
.stat-foot.link { color: var(--color-primary); }
.stat-foot.link:hover { color: var(--color-primary-hover); }

.row-trend { display: grid; grid-template-columns: minmax(0, 2fr) minmax(300px, 1fr); gap: 16px; margin-bottom: 16px; }
.donut-card { display: flex; flex-direction: column; }
.donut-card .donut { margin-top: auto; }
.legend { display: flex; justify-content: center; gap: 24px; margin: 8px 0 auto; padding: 0; list-style: none; color: var(--color-text-secondary); font-size: 13px; }
.legend.inline { margin: 0; gap: 16px; }
.legend li { display: flex; align-items: center; gap: 6px; }
.legend i { width: 8px; height: 8px; border-radius: 2px; }
.legend i.fake { background: var(--color-fake); }
.legend i.real { background: var(--color-primary); }
.legend b { color: var(--color-text); font-weight: 600; }

.row-dist { margin-bottom: 10px; }
.runtime { margin: 0; }
.runtime div { display: flex; justify-content: space-between; padding: 11px 0; border-bottom: 1px solid var(--color-line); font-size: 14px; }
.runtime div:first-child { padding-top: 2px; }
.runtime div:last-child { border-bottom: 0; }
.runtime dt { color: var(--color-text-secondary); }
.runtime dd { display: flex; align-items: center; gap: 8px; margin: 0; font-weight: 500; }
.scope-note { display: flex; align-items: center; gap: 6px; margin: 0 0 16px; color: var(--color-text-muted); font-size: 12px; }

.row-bottom { display: grid; grid-template-columns: minmax(0, 2fr) minmax(300px, 1fr); align-items: stretch; gap: 16px; }
.recent { display: flex; flex-direction: column; margin: -4px 0; }
.recent-row { display: grid; grid-template-columns: 48px minmax(0, 1fr) auto auto; align-items: center; gap: 14px; padding: 11px 8px; border-bottom: 1px solid var(--color-line); border-radius: 4px; color: inherit; text-decoration: none; }
.recent-row:last-child { border-bottom: 0; }
.recent-row:hover { background: var(--color-surface-muted); }
.prob { font-size: 16px; font-weight: 600; text-align: right; }
.prob.fake { color: var(--color-fake); }
.prob.real { color: var(--color-text-secondary); }
.recent-text { min-width: 0; }
.recent-text p { margin: 0; overflow: hidden; font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
.recent-text small { color: var(--color-text-muted); font-size: 12px; }
.quick-list { display: flex; flex-direction: column; gap: 12px; }
.quick { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 12px; padding: 12px; border: 1px solid var(--color-line); border-radius: var(--radius-card); color: inherit; text-decoration: none; transition: border-color .15s, box-shadow .15s; }
.quick:hover { border-color: var(--color-primary-soft-2); box-shadow: var(--shadow-raised); }
.quick > svg { color: var(--color-text-muted); }
.quick-icon { display: grid; width: 40px; height: 40px; place-items: center; border-radius: 10px; }
.quick strong { display: block; font-size: 14px; font-weight: 500; }
.quick small { color: var(--color-text-muted); font-size: 12px; }

@media (max-width: 1120px) {
  .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .row-trend, .row-bottom { grid-template-columns: 1fr; }
}
@media (max-width: 860px) {
  .stats { grid-template-columns: 1fr; }
}
</style>
