<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { AlertCircle, ArrowRight, CheckCircle2, FileSearch, Layers3, RefreshCw, ShieldAlert } from 'lucide-vue-next';
import { ApiError, getDetectionRecords, getServiceHealth } from '../api/client';
import type { DetectionRecordItem } from '../types';

const records = ref<DetectionRecordItem[]>([]);
const total = ref(0);
const loading = ref(true);
const errorMessage = ref('');
const serviceOnline = ref(false);
const runtimeMode = import.meta.env.VITE_USE_MOCK_API === 'false' ? 'FastAPI' : 'MSW Mock';

const fakeCount = computed(() => records.value.filter((item) => item.authenticity === 'fake').length);
const reviewCount = computed(() => records.value.filter((item) => item.action === 'review').length);
const blockedCount = computed(() => records.value.filter((item) => item.action === 'block').length);
const insufficientCount = computed(() => records.value.filter((item) => item.behavior_type === 'insufficient_evidence').length);
const sampleSize = computed(() => records.value.length);
const fakeRate = computed(() => sampleSize.value ? fakeCount.value / sampleSize.value : 0);
const actionBars = computed(() => [
  { label: '保留', count: records.value.filter((item) => item.action === 'keep').length, className: 'keep' },
  { label: '人工复核', count: reviewCount.value, className: 'review' },
  { label: '拦截', count: blockedCount.value, className: 'block' },
]);

function percent(value: number) { return `${Math.round(value * 100)}%`; }
function barWidth(count: number) { return sampleSize.value ? `${Math.round(count / sampleSize.value * 100)}%` : '0%'; }

async function loadOverview() {
  loading.value = true;
  errorMessage.value = '';
  try {
    const [health, response] = await Promise.all([
      getServiceHealth(),
      getDetectionRecords({ page: 1, page_size: 100 }),
    ]);
    serviceOnline.value = health.status === 'ok';
    records.value = response.items;
    total.value = response.total;
  } catch (error) {
    serviceOnline.value = false;
    errorMessage.value = error instanceof ApiError ? error.message : '概览数据加载失败，请稍后重试。';
  } finally {
    loading.value = false;
  }
}

onMounted(loadOverview);
</script>

<template>
  <section class="page-content overview-page">
    <header class="page-heading overview-heading">
      <div><span class="eyebrow">审核工作台</span><h1>系统概览</h1><p>快速查看服务状态、近期检测样本和待处理风险</p></div>
      <div class="api-state" :class="{ offline: !serviceOnline }"><span></span>{{ serviceOnline ? '检测服务正常' : '检测服务不可用' }}</div>
    </header>

    <div v-if="errorMessage" class="alert error overview-alert" role="alert">
      <AlertCircle :size="17" /><span>{{ errorMessage }}</span>
      <button type="button" @click="loadOverview"><RefreshCw :size="15" />重新加载</button>
    </div>

    <div class="overview-metrics" :class="{ loading }">
      <article><span>检测记录总数</span><strong>{{ loading ? '—' : total }}</strong><small>接口返回的记录总量</small></article>
      <article><span>疑似虚假样本</span><strong>{{ loading ? '—' : fakeCount }}</strong><small>当前加载 {{ sampleSize }} 条中的 {{ percent(fakeRate) }}</small></article>
      <article><span>待人工复核</span><strong>{{ loading ? '—' : reviewCount }}</strong><small>处置建议为人工复核</small></article>
      <article><span>行为证据不足</span><strong>{{ loading ? '—' : insufficientCount }}</strong><small>不得解释为行为正常</small></article>
    </div>

    <div class="overview-layout">
      <main class="overview-main">
        <section class="overview-panel">
          <div class="section-heading"><div><h2>处置建议分布</h2><p>统计口径：当前加载的最近 100 条记录</p></div><span class="sample-badge">样本 {{ sampleSize }}</span></div>
          <div class="overview-bars">
            <div v-for="item in actionBars" :key="item.label" class="overview-bar-row">
              <span>{{ item.label }}</span><div><i :class="item.className" :style="{ width: barWidth(item.count) }"></i></div><strong>{{ item.count }}</strong>
            </div>
          </div>
          <div class="overview-boundary"><ShieldAlert :size="17" /><p>页面统计用于工作量观察，不代表模型效果评估。检测结果仅辅助审核，不替代人工认定。</p></div>
        </section>

        <section class="overview-panel recent-panel">
          <div class="section-heading"><div><h2>最近检测记录</h2><p>按检测时间倒序展示</p></div><RouterLink to="/results" class="text-link">查看全部<ArrowRight :size="15" /></RouterLink></div>
          <div v-if="loading" class="overview-loading"><span class="spinner dark"></span>正在加载记录…</div>
          <div v-else-if="!records.length" class="overview-empty">暂无检测记录</div>
          <div v-else class="recent-list">
            <RouterLink v-for="item in records.slice(0, 5)" :key="item.result_id" :to="`/results/${item.result_id}`" class="recent-item">
              <span class="authenticity-label" :class="item.authenticity">{{ item.authenticity === 'real' ? '真实' : '疑似虚假' }}</span>
              <div><strong>{{ item.review_id || `结果 ${item.result_id}` }}</strong><p>{{ item.text_excerpt }}</p></div>
              <time>{{ new Date(item.created_at).toLocaleDateString('zh-CN') }}</time><ArrowRight :size="15" />
            </RouterLink>
          </div>
        </section>
      </main>

      <aside class="overview-side">
        <section class="overview-panel quick-panel">
          <div class="section-heading"><div><h2>开始检测</h2><p>选择当前审核方式</p></div></div>
          <RouterLink to="/detections/single" class="quick-action"><FileSearch :size="20" /><div><strong>单条评论检测</strong><span>录入一条评论及可选行为历史</span></div><ArrowRight :size="16" /></RouterLink>
          <RouterLink to="/detections/batch" class="quick-action"><Layers3 :size="20" /><div><strong>批量检测任务</strong><span>导入 CSV 或 TSV 文件</span></div><ArrowRight :size="16" /></RouterLink>
        </section>
        <section class="overview-panel service-panel">
          <div class="section-heading"><div><h2>运行状态</h2><p>来自现有健康检查接口</p></div></div>
          <div class="service-status" :class="{ offline: !serviceOnline }"><CheckCircle2 v-if="serviceOnline" :size="20" /><AlertCircle v-else :size="20" /><div><strong>{{ serviceOnline ? 'API 可访问' : 'API 不可访问' }}</strong><span>{{ serviceOnline ? '健康检查返回 ok' : '请检查后端或 Mock 服务' }}</span></div></div>
          <dl class="overview-facts"><div><dt>运行模式</dt><dd>{{ runtimeMode }}</dd></div><div><dt>数据口径</dt><dd>最近 100 条</dd></div></dl>
        </section>
      </aside>
    </div>
  </section>
</template>
