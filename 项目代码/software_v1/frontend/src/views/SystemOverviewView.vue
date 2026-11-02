<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { AlertCircle, ArrowRight, ClipboardCheck, Database, FileSearch, Layers3, RefreshCw, ShieldAlert, UserX } from 'lucide-vue-next';
import { ApiError, getDetectionRecords, getServiceHealth } from '../api/client';
import type { DetectionRecordItem } from '../types';
import AppCard from '../components/AppCard.vue';
import ScoreBars from '../components/ScoreBars.vue';
import DonutChart from '../components/charts/DonutChart.vue';
import { SEMANTIC_ORDER, authenticityLabels, formatDateTime, percent, semanticLabels } from '../labels';

const records = ref<DetectionRecordItem[]>([]);
const total = ref(0);
const loading = ref(true);
const errorMessage = ref('');
const health = ref<{ status: string; model?: string } | null>(null);

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
  { key: 'keep', label: '保留', tone: 'accent' as const },
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
    <nav class="crumb" aria-label="面包屑">审核工作台 / <b>系统概览</b></nav>
    <header class="page-title">
      <h1>系统概览</h1>
      <span class="page-id">服务状态、近期检测样本与待处理风险</span>
      <div class="page-actions">
        <span class="tag service-tag" :class="serviceState.tone">{{ serviceState.label }}</span>
        <button type="button" class="btn small" :disabled="loading" @click="loadOverview"><RefreshCw :size="14" />刷新</button>
      </div>
    </header>

    <div v-if="errorMessage" class="alert-bar" role="alert">
      <AlertCircle :size="16" />{{ errorMessage }}
      <button type="button" class="btn small retry" @click="loadOverview"><RefreshCw :size="14" />重新加载</button>
    </div>

    <div class="stats" :class="{ loading }">
      <article class="stat brand"><span class="stat-icon"><Database :size="18" /></span><span class="stat-label">检测记录总数</span><strong class="num">{{ loading ? '—' : total }}</strong><small>全部单条与批量检测结果</small></article>
      <article class="stat"><span class="stat-icon fake"><ShieldAlert :size="18" /></span><span class="stat-label">疑似虚假样本</span><strong class="num">{{ loading ? '—' : fakeCount }}</strong><small class="num">最近 {{ sampleSize }} 条中占 {{ percent(fakeRate) }}</small></article>
      <article class="stat"><span class="stat-icon warn"><ClipboardCheck :size="18" /></span><span class="stat-label">待人工复核</span><strong class="num">{{ loading ? '—' : reviewCount }}</strong><small>处置建议为人工复核</small></article>
      <article class="stat"><span class="stat-icon behavior"><UserX :size="18" /></span><span class="stat-label">行为证据不足</span><strong class="num">{{ loading ? '—' : insufficientCount }}</strong><small>不得解释为行为正常</small></article>
    </div>

    <div class="grid-3 charts">
      <AppCard title="真实性分布" :subtitle="`最近 ${sampleSize} 条检测结果`">
        <DonutChart :parts="authenticityParts" :center="percent(fakeRate)" caption="疑似虚假占比" />
        <ul class="legend">
          <li><i class="fake"></i>疑似虚假<b class="num">{{ fakeCount }} 条</b></li>
          <li><i class="real"></i>真实<b class="num">{{ sampleSize - fakeCount }} 条</b></li>
        </ul>
      </AppCard>
      <AppCard title="处置建议分布" subtitle="融合判定给出的审核建议">
        <ScoreBars :items="actionItems" />
      </AppCard>
      <AppCard title="语义类型分布" subtitle="ALBERT 语义匹配度最高的类型">
        <ScoreBars :items="semanticItems" />
      </AppCard>
    </div>
    <p class="scope-note"><ShieldAlert :size="14" />统计口径：当前加载的最近 100 条记录。页面统计用于工作量观察，不代表模型效果评估；检测结果仅辅助审核，不替代人工认定。</p>

    <div class="bottom">
      <AppCard title="最近检测记录" subtitle="按检测时间倒序">
        <template #extra><RouterLink to="/results" class="btn text small">查看全部<ArrowRight :size="14" /></RouterLink></template>
        <div v-if="loading" class="empty-hint"><span class="spinner dark"></span>正在加载记录…</div>
        <div v-else-if="!records.length" class="empty-hint">暂无检测记录</div>
        <div v-else class="recent">
          <RouterLink v-for="item in records.slice(0, 5)" :key="item.result_id" :to="`/results/${item.result_id}`" class="recent-row">
            <span class="tag fixed" :class="item.authenticity === 'fake' ? 'fake' : 'ok'">{{ authenticityLabels[item.authenticity] }}</span>
            <div class="recent-text"><strong class="num">{{ item.review_id || `结果 #${item.result_id}` }}</strong><p>{{ item.text_excerpt }}</p></div>
            <time class="num">{{ formatDateTime(item.created_at) }}</time>
            <ArrowRight :size="15" />
          </RouterLink>
        </div>
      </AppCard>

      <div class="stack">
        <AppCard title="开始检测" subtitle="选择审核方式">
          <RouterLink to="/detections/single" class="quick"><span class="quick-icon"><FileSearch :size="19" /></span><div><strong>单条评论检测</strong><small>录入一条评论及可选行为历史</small></div><ArrowRight :size="16" /></RouterLink>
          <RouterLink to="/detections/batch" class="quick"><span class="quick-icon behavior"><Layers3 :size="19" /></span><div><strong>批量检测任务</strong><small>导入 CSV 或 TSV 文件</small></div><ArrowRight :size="16" /></RouterLink>
        </AppCard>
        <AppCard title="运行状态" subtitle="来自健康检查接口">
          <dl class="runtime">
            <div><dt>接口服务</dt><dd><span class="dot" :class="health ? 'ok' : 'fake'"></span>{{ health ? '可访问' : '不可访问' }}</dd></div>
            <div><dt>检测模型</dt><dd><span class="dot" :class="modelState === '已加载' ? 'ok' : 'warn'"></span>{{ modelState }}</dd></div>
            <div><dt>统计口径</dt><dd>最近 100 条</dd></div>
          </dl>
        </AppCard>
      </div>
    </div>
  </section>
</template>

<style scoped>
.retry { margin-left: auto; }
.stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; margin-bottom: 16px; }
.stats.loading { opacity: .6; }
.stat { display: grid; grid-template-columns: auto 1fr; align-items: center; column-gap: 10px; padding: 18px 20px; border-radius: var(--radius-card); background: var(--color-surface); box-shadow: var(--shadow-card); }
.stat-icon { display: grid; grid-row: span 1; width: 34px; height: 34px; place-items: center; border-radius: 10px; background: var(--color-primary-soft); color: var(--color-primary); }
.stat-icon.fake { background: var(--color-fake-soft); color: var(--color-fake); }
.stat-icon.warn { background: var(--color-warn-soft); color: var(--color-warn); }
.stat-icon.behavior { background: var(--color-behavior-soft); color: var(--color-behavior); }
.stat-label { color: var(--color-text-secondary); font-size: 13px; }
.stat strong { grid-column: span 2; margin-top: 10px; font-size: 32px; line-height: 1.1; }
.stat small { grid-column: span 2; margin-top: 4px; color: var(--color-text-muted); font-size: 12px; }
.stat.brand { background: var(--color-brand-deep); color: #fff; }
.stat.brand .stat-icon { background: rgb(255 255 255 / 12%); color: var(--color-accent); }
.stat.brand .stat-label, .stat.brand small { color: rgb(255 255 255 / 72%); }

.charts { margin-bottom: 10px; }
.legend { display: flex; justify-content: center; gap: 22px; margin: 6px 0 0; padding: 0; list-style: none; color: var(--color-text-secondary); font-size: 13px; }
.legend li { display: flex; align-items: center; gap: 6px; }
.legend i { width: 9px; height: 9px; border-radius: 2px; }
.legend i.fake { background: var(--color-fake); }
.legend i.real { background: var(--color-primary); }
.legend b { color: var(--color-text); font-weight: 600; }
.scope-note { display: flex; align-items: center; gap: 6px; margin: 0 0 16px; color: var(--color-text-muted); font-size: 12px; }

/* 底部两栏等高：右栏最后一张卡片填满剩余高度 */
.bottom { display: grid; grid-template-columns: minmax(0, 2fr) minmax(280px, 1fr); align-items: stretch; gap: 16px; }
.bottom .stack > :last-child { flex: 1; }
.recent { display: flex; flex-direction: column; }
.recent-row { display: grid; grid-template-columns: 76px minmax(0, 1fr) auto 16px; align-items: center; gap: 12px; padding: 11px 6px; border-bottom: 1px solid var(--color-line); color: inherit; text-decoration: none; }
.recent-row:last-child { border-bottom: 0; }
.recent-row:hover { background: var(--color-surface-muted); }
.recent-row .tag { justify-self: start; }
.recent-text strong { font-size: 13px; }
.recent-text p { margin: 1px 0 0; overflow: hidden; color: var(--color-text-secondary); font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.recent-row time { color: var(--color-text-muted); font-size: 12px; white-space: nowrap; }
.recent-row svg { color: var(--color-text-muted); }
.quick { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 12px; padding: 12px; border: 1px solid var(--color-line); border-radius: 10px; color: inherit; text-decoration: none; }
.quick + .quick { margin-top: 10px; }
.quick:hover { border-color: var(--color-primary); }
.quick-icon { display: grid; width: 38px; height: 38px; place-items: center; border-radius: 10px; background: var(--color-brand-deep); color: var(--color-accent); }
.quick-icon.behavior { background: var(--color-behavior); color: #fff; }
.quick strong { display: block; font-size: 14px; }
.quick small { color: var(--color-text-muted); font-size: 12px; }
.runtime { margin: 0; }
.runtime div { display: flex; justify-content: space-between; padding: 9px 0; border-bottom: 1px dashed var(--color-line); font-size: 13px; }
.runtime div:last-child { border-bottom: 0; }
.runtime dt { color: var(--color-text-muted); }
.runtime dd { display: flex; align-items: center; gap: 6px; margin: 0; font-weight: 600; }
.dot { width: 8px; height: 8px; border-radius: 50%; }
.dot.ok { background: var(--color-accent); box-shadow: 0 0 0 1.5px var(--color-brand-deep); }
.dot.warn { background: var(--color-warn); }
.dot.fake { background: var(--color-fake); }

@media (max-width: 1120px) {
  .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .bottom { grid-template-columns: 1fr; }
}
@media (max-width: 860px) {
  .stats { grid-template-columns: 1fr; }
}
</style>
