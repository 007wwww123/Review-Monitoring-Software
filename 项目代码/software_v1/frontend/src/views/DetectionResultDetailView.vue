<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { AlertCircle, CheckCircle2, FileJson, FileSpreadsheet, RefreshCw } from 'lucide-vue-next';
import { ApiError, createTaskReport, downloadTaskReport, getDetectionResult } from '../api/client';
import type { DetectionResultResponse, ReportSummaryResponse } from '../types';
import AppCard from '../components/AppCard.vue';
import { reportSummaryRows } from '../utils/report-summary';
import ScoreBars from '../components/ScoreBars.vue';
import DonutChart from '../components/charts/DonutChart.vue';
import GaugeChart from '../components/charts/GaugeChart.vue';
import RadarChart from '../components/charts/RadarChart.vue';
import {
  BEHAVIOR_ORDER, SEMANTIC_ORDER, actionLabels, authenticityLabels, behaviorLabels, evidenceStateLabels,
  formatDateTime, percent, riskLabels, semanticLabels, shortId,
} from '../labels';

const route = useRoute();
const result = ref<DetectionResultResponse | null>(null);
const report = ref<ReportSummaryResponse | null>(null);
const loading = ref(true);
const errorMessage = ref('');
const reportError = ref('');
const creatingReport = ref(false);
const downloading = ref<'json' | 'csv' | null>(null);

const resultId = computed(() => Number(route.params.resultId));
const explanation = computed(() => result.value?.explanation ?? null);
// 没有解释快照时，由真实性和置信度反推虚假概率
const fakeProbability = computed(() => {
  const r = result.value;
  if (!r) return 0;
  return r.explanation?.final.fake_probability ?? (r.authenticity === 'fake' ? r.confidence : 1 - r.confidence);
});
const semanticItems = computed(() => SEMANTIC_ORDER.map((key) => ({ key, label: semanticLabels[key], value: explanation.value?.semantic.scores[key] ?? 0 })));
const behaviorItems = computed(() => BEHAVIOR_ORDER.map((key) => ({ key, label: behaviorLabels[key], value: explanation.value?.behavior.scores[key] ?? 0 })));
const actionTone = { keep: 'ok', review: 'warn', block: 'fake' } as const;
const fusionParts = computed(() => explanation.value ? [
  { key: 'semantic', label: '语义', value: explanation.value.fusion.semantic_weight, tone: 'primary' as const },
  { key: 'behavior', label: '行为', value: explanation.value.fusion.behavior_weight, tone: 'behavior' as const },
] : []);
const fusionRatio = computed(() => explanation.value
  ? `${(explanation.value.fusion.semantic_weight * 100).toFixed(1)} : ${(explanation.value.fusion.behavior_weight * 100).toFixed(1)}`
  : '');
const stateLabel = (state: string) => evidenceStateLabels[state] ?? state;

async function loadResult() {
  if (!Number.isInteger(resultId.value) || resultId.value <= 0) {
    errorMessage.value = '结果编号无效。';
    loading.value = false;
    return;
  }
  loading.value = true;
  errorMessage.value = '';
  report.value = null;
  reportError.value = '';
  try {
    result.value = await getDetectionResult(resultId.value);
  } catch (error) {
    result.value = null;
    errorMessage.value = error instanceof ApiError
      ? (error.status === 404 ? '未找到该检测结果，记录可能已被移除。' : error.message)
      : '结果详情加载失败，请稍后重试。';
  } finally {
    loading.value = false;
  }
}

async function generateReport() {
  if (!result.value || creatingReport.value) return;
  creatingReport.value = true;
  reportError.value = '';
  try {
    report.value = await createTaskReport(result.value.task_id);
  } catch (error) {
    reportError.value = error instanceof ApiError ? error.message : '任务报告生成失败，请稍后重试。';
  } finally {
    creatingReport.value = false;
  }
}

async function download(format: 'json' | 'csv') {
  if (!report.value || downloading.value) return;
  downloading.value = format;
  reportError.value = '';
  try {
    const blob = await downloadTaskReport(report.value.report_id, format);
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `task-report-${report.value.report_id}.${format}`;
    anchor.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    reportError.value = error instanceof ApiError ? error.message : '报告下载失败，请稍后重试。';
  } finally {
    downloading.value = null;
  }
}

onMounted(loadResult);
watch(() => route.params.resultId, loadResult);
</script>

<template>
  <section class="page detail-page">
    <nav class="crumb" aria-label="面包屑"><RouterLink to="/results">检测记录</RouterLink> / <b>结果详情</b></nav>
    <header class="page-title">
      <h1>检测结果分析</h1>
      <span v-if="result" class="page-id num">评论编号 {{ result.review_id || `#${result.result_id}` }}</span>
      <div class="page-actions">
        <RouterLink to="/results" class="btn">返回列表</RouterLink>
        <button v-if="result" type="button" class="btn primary report-create" :disabled="creatingReport" @click="generateReport">
          {{ creatingReport ? '生成中…' : report ? '重新生成报告' : '生成任务报告' }}
        </button>
      </div>
    </header>

    <div v-if="loading" class="state-card"><span class="spinner dark"></span><strong>正在加载结果与证据…</strong></div>
    <div v-else-if="errorMessage" class="state-card error">
      <AlertCircle :size="30" /><strong>{{ errorMessage }}</strong>
      <button type="button" class="btn" @click="loadResult"><RefreshCw :size="15" />重新加载</button>
    </div>

    <template v-else-if="result">
      <div v-if="reportError" class="alert-bar" role="alert"><AlertCircle :size="16" />{{ reportError }}</div>

      <div class="row-hero">
        <AppCard title="融合判定" subtitle="融合真实性头输出" class="verdict-card">
          <GaugeChart :value="fakeProbability" :threshold="explanation?.final.threshold" :tone="result.authenticity" label="融合虚假概率" />
          <div class="tag-row">
            <span class="tag" :class="result.authenticity === 'fake' ? 'fake' : 'ok'">{{ authenticityLabels[result.authenticity] }}</span>
            <span class="tag" :class="actionTone[result.action]">建议{{ actionLabels[result.action] }}</span>
          </div>
        </AppCard>

        <AppCard title="评论与结论" subtitle="原始评论与最终判定字段" class="summary-card">
          <blockquote class="quote">
            {{ result.text_excerpt || '未保存评论摘要' }}
            <small class="num">商品 {{ result.product_id || '未提供' }} · 检测于 {{ formatDateTime(result.created_at) }}</small>
          </blockquote>
          <dl class="facts">
            <div><dt>融合虚假概率</dt><dd class="num" :class="{ fake: result.authenticity === 'fake' }">{{ percent(fakeProbability) }}</dd></div>
            <div><dt>判定阈值</dt><dd class="num">{{ explanation ? percent(explanation.final.threshold, 0) : '未保存' }}</dd></div>
            <div><dt>风险来源</dt><dd>{{ riskLabels[result.risk_source] }}</dd></div>
            <div><dt>语义类型</dt><dd>{{ semanticLabels[result.semantic_type] }}</dd></div>
            <div><dt>行为类型</dt><dd :class="{ warn: result.behavior_type === 'insufficient_evidence' }">{{ behaviorLabels[result.behavior_type] }}</dd></div>
            <div><dt>模型版本</dt><dd class="num">{{ result.model_version }}</dd></div>
          </dl>
        </AppCard>
      </div>

      <template v-if="explanation">
        <AppCard title="双流融合检测过程" subtitle="每条评论都经过语义流、行为流和门控融合；数值为本条评论的模型输出" class="flow-card">
          <div class="flow">
            <div class="flow-col">
              <div class="node input"><span class="node-tag">输入 · 评论文本</span><strong>“{{ result.text_excerpt || '未保存评论摘要' }}”</strong></div>
              <div class="node input">
                <span class="node-tag">输入 · 用户行为序列</span>
                <strong v-if="explanation.behavior.available">历史 {{ explanation.behavior.history_length }} 条 · 10 维行为特征</strong>
                <strong v-else>无可用历史行为</strong>
              </div>
            </div>
            <div class="flow-arrows"><i></i><i></i></div>
            <div class="flow-col">
              <div class="node semantic">
                <span class="node-tag"><i></i>ALBERT 语义编码</span><strong>语义虚假辅助概率</strong>
                <b class="node-figure num">{{ percent(explanation.semantic.authenticity_scores.fake) }}</b>
              </div>
              <div class="node behavior">
                <span class="node-tag"><i></i>GRU 时序编码</span><strong>行为异常辅助概率</strong>
                <b v-if="explanation.behavior.available" class="node-figure num">{{ percent(explanation.behavior.normality_scores.abnormal) }}</b>
                <b v-else class="node-figure muted">证据不足</b>
              </div>
            </div>
            <div class="flow-arrows single"><i></i></div>
            <div class="flow-col">
              <div class="node gate">
                <span class="node-tag">自适应门控融合</span>
                <span class="split"><i class="s" :style="{ width: percent(explanation.fusion.semantic_weight) }"></i><i class="b" :style="{ width: percent(explanation.fusion.behavior_weight) }"></i></span>
                <small class="num">语义 {{ percent(explanation.fusion.semantic_weight) }} · 行为 {{ percent(explanation.fusion.behavior_weight) }}</small>
              </div>
              <div class="node outcome" :class="result.authenticity">
                <span class="node-tag">融合结论</span>
                <strong class="outcome-title">{{ authenticityLabels[result.authenticity] }} · <span class="num">{{ percent(fakeProbability) }}</span></strong>
                <small>{{ semanticLabels[result.semantic_type] }} · {{ behaviorLabels[result.behavior_type] }} · 建议{{ actionLabels[result.action] }}</small>
              </div>
            </div>
          </div>
        </AppCard>

        <div class="row-evidence">
          <AppCard title="语义相对匹配度" subtitle="ALBERT 四分类 · 未经校准" class="semantic-card">
            <template #extra><span class="tag primary">{{ semanticLabels[explanation.semantic.selected_type] }}</span></template>
            <RadarChart :items="semanticItems" :selected="explanation.semantic.selected_type" />
          </AppCard>

          <AppCard title="行为相对匹配度" subtitle="GRU 五分类 · 真实性代理任务" class="behavior-card">
            <template #extra><span class="tag behavior">{{ behaviorLabels[explanation.behavior.selected_type] }}</span></template>
            <div class="aux">
              <div>行为正常<b class="num">{{ percent(explanation.behavior.normality_scores.normal) }}</b></div>
              <div>行为异常<b class="num">{{ percent(explanation.behavior.normality_scores.abnormal) }}</b></div>
            </div>
            <p v-if="!explanation.behavior.available" class="insufficient-note">
              <AlertCircle :size="15" />历史长度为 0，行为证据不足，该状态不能解释为用户行为正常。
            </p>
            <ScoreBars :items="behaviorItems" :selected="explanation.behavior.selected_type" tone="behavior" />
          </AppCard>

          <AppCard title="门控权重" subtitle="融合比例摘要，不构成因果归因" class="fusion-card">
            <DonutChart :parts="fusionParts" :center="fusionRatio" caption="语义 : 行为" />
            <ul class="legend">
              <li><i class="s"></i>语义证据<em :class="{ ok: explanation.evidence.semantic_evidence_state === 'available' }">{{ stateLabel(explanation.evidence.semantic_evidence_state) }}</em><b class="num">{{ percent(explanation.fusion.semantic_weight) }}</b></li>
              <li><i class="b"></i>行为证据<em :class="{ ok: explanation.evidence.behavior_evidence_state === 'available' }">{{ stateLabel(explanation.evidence.behavior_evidence_state) }}</em><b class="num">{{ percent(explanation.fusion.behavior_weight) }}</b></li>
              <li><i class="n"></i>分数校准<b>{{ stateLabel(explanation.evidence.calibration_state) }}</b></li>
            </ul>
          </AppCard>
        </div>
      </template>

      <AppCard v-else title="解释数据不可用" class="explanation-empty">
        <p class="empty-text">该结果没有保存解释快照，页面不会补造证据或细分类结论。</p>
      </AppCard>

      <AppCard v-if="report" title="任务报告" subtitle="报告覆盖整个检测任务，不是单条结果报告" class="report-card">
        <template #extra><span class="tag ok report-ready"><CheckCircle2 :size="13" />报告已生成 #{{ report.report_id }}</span></template>
        <div class="report-body">
          <dl class="report-summary">
            <div v-for="row in reportSummaryRows(report.summary)" :key="row.key"><dt>{{ row.label }}</dt><dd class="num">{{ row.value }}</dd></div>
          </dl>
          <div class="report-downloads">
            <button type="button" class="btn" :disabled="Boolean(downloading)" @click="download('json')"><FileJson :size="15" />{{ downloading === 'json' ? '下载中…' : '下载 JSON' }}</button>
            <button type="button" class="btn" :disabled="Boolean(downloading)" @click="download('csv')"><FileSpreadsheet :size="15" />{{ downloading === 'csv' ? '下载中…' : '下载 CSV' }}</button>
          </div>
        </div>
      </AppCard>

      <div class="row-foot" :class="{ single: !explanation }">
        <AppCard title="检测信息" subtitle="结果追溯字段" class="metadata-card">
          <dl class="meta">
            <dt>商品标识</dt><dd>{{ result.product_id || '未提供' }}</dd>
            <dt>匿名用户</dt><dd class="num" :title="result.user_key || ''">{{ result.user_key ? shortId(result.user_key) : '未提供' }}</dd>
            <dt>所属任务</dt><dd class="num" :title="result.task_id">{{ shortId(result.task_id, 6) }}</dd>
            <dt>检测时间</dt><dd class="num">{{ formatDateTime(result.created_at) }}</dd>
          </dl>
        </AppCard>
        <AppCard v-if="explanation" title="解释边界" subtitle="审核与报告须保留以下说明" class="limitations-card">
          <ol class="limitations"><li v-for="(item, index) in explanation.limitations" :key="index">{{ item }}</li></ol>
        </AppCard>
      </div>
    </template>
  </section>
</template>

<style scoped>
.row-hero { display: grid; grid-template-columns: 300px minmax(0, 1fr); gap: 16px; margin-bottom: 16px; }
.verdict-card { text-align: center; }
.verdict-card :deep(.card-head), .verdict-card :deep(.card-sub) { text-align: left; }
.tag-row { display: flex; justify-content: center; gap: 8px; margin-top: 6px; }
.quote { margin: 0; padding: 14px 18px; border-radius: 10px; background: var(--color-surface-muted); font-size: 17px; line-height: 1.7; }
.quote small { display: block; margin-top: 6px; color: var(--color-text-muted); font-size: 12px; }
.facts { display: grid; grid-template-columns: repeat(3, 1fr); margin: 14px 0 0; overflow: hidden; border: 1px solid var(--color-line); border-radius: 10px; }
.facts div { padding: 11px 16px; border-right: 1px solid var(--color-line); border-bottom: 1px solid var(--color-line); }
.facts div:nth-child(3n) { border-right: 0; }
.facts div:nth-child(n + 4) { border-bottom: 0; }
.facts dt { color: var(--color-text-muted); font-size: 12px; }
.facts dd { margin: 0; font-size: 15px; font-weight: 600; }
.facts dd.fake { color: var(--color-fake); }
.facts dd.warn { color: var(--color-warn); }

.flow-card { margin-bottom: 16px; }
.flow { display: grid; grid-template-columns: 1fr 34px 1fr 34px 1fr; align-items: center; }
.flow-col { display: flex; flex-direction: column; gap: 12px; }
.flow-arrows { display: flex; flex-direction: column; gap: 76px; }
.flow-arrows i { position: relative; display: block; height: 2px; margin: 0 5px; background: #c9cedd; }
.flow-arrows i::after { position: absolute; top: -4px; right: -1px; border: 5px solid transparent; border-left: 7px solid #c9cedd; content: ""; }
.node { display: flex; flex-direction: column; padding: 10px 14px; border: 1px solid var(--color-line); border-radius: 10px; background: var(--color-surface); }
.node-tag { display: flex; align-items: center; gap: 7px; color: var(--color-text-muted); font-size: 12px; }
.node-tag i { width: 6px; height: 6px; border-radius: 50%; }
.node strong { font-size: 14px; }
.node small { color: var(--color-text-muted); font-size: 12px; }
.node-figure { font-size: 22px; line-height: 1.3; }
.node-figure.muted { color: var(--color-text-muted); font-size: 18px; }
.node.input { background: var(--color-surface-muted); }
.node.semantic { border-color: color-mix(in srgb, var(--color-primary) 18%, #fff); background: linear-gradient(180deg, color-mix(in srgb, var(--color-primary) 4%, #fff), #fff 70%); }
.node.semantic .node-tag i { background: var(--color-primary); }
.node.semantic .node-figure { color: var(--color-primary); }
.node.behavior { border-color: color-mix(in srgb, var(--color-behavior) 22%, #fff); background: linear-gradient(180deg, color-mix(in srgb, var(--color-behavior) 5%, #fff), #fff 70%); }
.node.behavior .node-tag i { background: var(--color-behavior); }
.node.behavior .node-figure:not(.muted) { color: var(--color-behavior); }
.node.gate { border-color: color-mix(in srgb, var(--color-primary) 22%, #fff); background: linear-gradient(180deg, color-mix(in srgb, var(--color-primary) 5%, #fff), #fff); }
.split { display: flex; height: 8px; margin: 8px 0 4px; overflow: hidden; border-radius: 4px; }
.split .s { background: var(--color-primary); }
.split .b { background: var(--color-behavior); }
.node.outcome.fake { border-color: color-mix(in srgb, var(--color-fake) 22%, #fff); background: var(--color-fake-soft); }
.node.outcome.fake .outcome-title { color: var(--color-fake); }
.node.outcome.real { border-color: color-mix(in srgb, var(--color-primary) 22%, #fff); background: var(--color-primary-soft); }
.node.outcome.real .outcome-title { color: var(--color-primary); }

.row-evidence { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin-bottom: 16px; }
.aux { display: flex; gap: 10px; margin-bottom: 6px; }
.aux div { flex: 1; padding: 6px 12px; border-radius: 8px; background: var(--color-surface-muted); color: var(--color-text-muted); font-size: 12px; }
.aux b { display: block; color: var(--color-text); font-size: 16px; }
.insufficient-note { display: flex; align-items: flex-start; gap: 6px; margin: 10px 0 0; padding: 8px 10px; border-radius: 8px; background: var(--color-warn-soft); color: var(--color-warn); font-size: 12px; }
.insufficient-note svg { flex: none; margin-top: 2px; }
.legend { display: flex; flex-direction: column; gap: 6px; margin: 4px 0 0; padding: 0; list-style: none; color: var(--color-text-muted); font-size: 13px; }
.legend li { display: flex; align-items: center; gap: 8px; }
.legend i { width: 8px; height: 8px; border-radius: 2px; }
.legend i.s { background: var(--color-primary); }
.legend i.b { background: var(--color-behavior); }
.legend i.n { background: var(--color-line); }
.legend em { padding: 0 6px; border-radius: 4px; background: var(--color-warn-soft); color: var(--color-warn); font-size: 11px; font-style: normal; font-weight: 700; }
.legend em.ok { background: var(--color-accent); color: var(--color-primary); }
.legend b { margin-left: auto; color: var(--color-text); font-weight: 500; }

.explanation-empty, .report-card { margin-bottom: 16px; }
.empty-text { margin: 12px 0 0; color: var(--color-text-secondary); font-size: 13px; }
.report-body { display: flex; align-items: flex-end; gap: 24px; }
.report-summary { display: grid; flex: 1; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 10px; margin: 0; }
.report-summary div { display: flex; flex-direction: column; gap: 2px; padding: 8px 12px; border: 0; border-radius: 8px; background: var(--color-surface-muted); }
.report-summary dt { color: var(--color-text-muted); font-size: 12px; }
.report-summary dd { margin: 0; font-size: 13px; font-weight: 600; }
.report-downloads { flex: none; }
.report-downloads { display: flex; gap: 8px; }

.row-foot { display: grid; grid-template-columns: 1fr 1.25fr; gap: 16px; }
.row-foot.single { grid-template-columns: 1fr; }
.meta { display: grid; grid-template-columns: 76px 1fr; row-gap: 9px; margin: 0; font-size: 13px; }
.meta dt { color: var(--color-text-muted); }
.meta dd { margin: 0; word-break: break-all; }
.limitations { margin: 0; padding: 0; list-style: none; counter-reset: n; color: var(--color-text-secondary); font-size: 13px; }
.limitations li { display: flex; gap: 10px; padding: 7px 0; border-bottom: 1px dashed var(--color-line); counter-increment: n; }
.limitations li:last-child { border-bottom: 0; }
.limitations li::before { display: grid; flex: none; width: 20px; height: 20px; place-items: center; border-radius: 50%; background: var(--color-primary-soft); color: var(--color-primary); content: counter(n); font-size: 12px; font-weight: 600; }

@media (max-width: 1120px) {
  .row-evidence { grid-template-columns: 1fr 1fr; }
  .fusion-card { grid-column: span 2; }
}
@media (max-width: 860px) {
  .row-hero, .row-foot, .row-evidence { grid-template-columns: 1fr; }
  .fusion-card { grid-column: auto; }
  .flow { grid-template-columns: 1fr; gap: 12px; }
  .flow-arrows { display: none; }
  .facts { grid-template-columns: repeat(2, 1fr); }
}
</style>
