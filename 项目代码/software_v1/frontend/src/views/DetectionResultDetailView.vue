<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { AlertCircle, ArrowLeft, CheckCircle2, FileJson, FileSpreadsheet, FileText, Info, RefreshCw } from 'lucide-vue-next';
import { ApiError, createTaskReport, downloadTaskReport, getDetectionRecords, getDetectionResult } from '../api/client';
import type { DetectionRecordItem, DetectionResultResponse, ReportSummaryResponse } from '../types';
import AppCard from '../components/AppCard.vue';
import { reportSummaryRows } from '../utils/report-summary';
import ScoreBars from '../components/ScoreBars.vue';
import DonutChart from '../components/charts/DonutChart.vue';
import GaugeChart from '../components/charts/GaugeChart.vue';
import RadarChart from '../components/charts/RadarChart.vue';
import {
  BEHAVIOR_ORDER, SEMANTIC_ORDER, actionLabels, actionTone, authenticityLabels, behaviorLabels, evidenceStateLabels,
  fakeProbabilityOf, formatDateTime, percent, riskLabels, semanticLabels, shortId,
} from '../labels';

const route = useRoute();
const result = ref<DetectionResultResponse | null>(null);
const report = ref<ReportSummaryResponse | null>(null);
const related = ref<DetectionRecordItem[]>([]);
const relatedTotal = ref(0);
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
  return r.explanation?.final.fake_probability ?? fakeProbabilityOf(r);
});
const semanticItems = computed(() => SEMANTIC_ORDER.map((key) => ({ key, label: semanticLabels[key], value: explanation.value?.semantic.scores[key] ?? 0 })));
const behaviorItems = computed(() => BEHAVIOR_ORDER.map((key) => ({ key, label: behaviorLabels[key], value: explanation.value?.behavior.scores[key] ?? 0 })));
const fusionParts = computed(() => explanation.value ? [
  { key: 'semantic', label: '语义', value: explanation.value.fusion.semantic_weight, tone: 'primary' as const },
  { key: 'behavior', label: '行为', value: explanation.value.fusion.behavior_weight, tone: 'behavior' as const },
] : []);
const fusionRatio = computed(() => explanation.value
  ? `${(explanation.value.fusion.semantic_weight * 100).toFixed(1)} : ${(explanation.value.fusion.behavior_weight * 100).toFixed(1)}`
  : '');
const stateLabel = (state: string) => evidenceStateLabels[state] ?? state;

// 同一匿名用户的其他检测：用关键词按 user_key 查询，排除当前这条
async function loadRelated(current: DetectionResultResponse) {
  related.value = [];
  relatedTotal.value = 0;
  if (!current.user_key) return;
  try {
    const response = await getDetectionRecords({ page: 1, page_size: 6, keyword: current.user_key });
    related.value = response.items.filter((item) => item.result_id !== current.result_id).slice(0, 5);
    relatedTotal.value = Math.max(response.total - 1, 0);
  } catch {
    related.value = [];
  }
}

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
    void loadRelated(result.value);
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
    <header class="page-title">
      <h1>检测结果详情</h1>
      <span class="page-id num">{{ result ? `评论编号 ${result.review_id || `#${result.result_id}`} · 检测于 ${formatDateTime(result.created_at)}` : '正在读取检测结果' }}</span>
      <div class="page-actions">
        <RouterLink to="/results" class="btn"><ArrowLeft :size="15" />返回列表</RouterLink>
        <button v-if="result" type="button" class="btn primary report-create" :disabled="creatingReport" @click="generateReport">
          <FileText :size="15" />{{ creatingReport ? '生成中…' : report ? '重新生成报告' : '生成任务报告' }}
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

      <div class="detail-layout">
        <!-- 主栏：评论本身 → 检测过程 → 两路证据 → 解释边界 -->
        <div class="stack main-col">
          <AppCard v-if="report" title="任务报告" subtitle="报告覆盖整个检测任务，不是单条结果报告" class="report-card">
            <template #extra><span class="tag ok report-ready"><CheckCircle2 :size="13" />报告已生成 #{{ report.report_id }}</span></template>
            <dl class="report-summary">
              <div v-for="row in reportSummaryRows(report.summary)" :key="row.key"><dt>{{ row.label }}</dt><dd class="num">{{ row.value }}</dd></div>
            </dl>
            <div class="report-downloads">
              <button type="button" class="btn" :disabled="Boolean(downloading)" @click="download('json')"><FileJson :size="15" />{{ downloading === 'json' ? '下载中…' : '下载 JSON' }}</button>
              <button type="button" class="btn" :disabled="Boolean(downloading)" @click="download('csv')"><FileSpreadsheet :size="15" />{{ downloading === 'csv' ? '下载中…' : '下载 CSV' }}</button>
            </div>
          </AppCard>

          <AppCard title="评论与结论" class="summary-card">
            <blockquote class="quote">{{ result.text_excerpt || '未保存评论摘要' }}</blockquote>
            <dl class="facts">
              <div><dt>语义类型</dt><dd>{{ semanticLabels[result.semantic_type] }}</dd></div>
              <div><dt>行为类型</dt><dd :class="{ muted: result.behavior_type === 'insufficient_evidence' }">{{ behaviorLabels[result.behavior_type] }}</dd></div>
              <div><dt>风险来源</dt><dd>{{ riskLabels[result.risk_source] }}</dd></div>
              <div><dt>判定阈值</dt><dd class="num">{{ explanation ? percent(explanation.final.threshold, 0) : '未保存' }}</dd></div>
              <div><dt>处置建议</dt><dd><span class="tag dot" :class="actionTone[result.action]">{{ actionLabels[result.action] }}</span></dd></div>
              <div><dt>模型版本</dt><dd class="num">{{ result.model_version }}</dd></div>
            </dl>
          </AppCard>

          <template v-if="explanation">
            <AppCard title="双流融合检测过程" subtitle="语义流与行为流分别编码，再由自适应门控融合；数值为本条评论的模型输出" class="flow-card">
              <div class="flow">
                <div class="flow-col">
                  <div class="node input"><span class="node-tag">输入 · 评论文本</span><strong class="ellipsis">{{ result.text_excerpt || '未保存评论摘要' }}</strong></div>
                  <div class="node input">
                    <span class="node-tag">输入 · 用户行为序列</span>
                    <strong v-if="explanation.behavior.available">历史 {{ explanation.behavior.history_length }} 条 · 10 维行为特征</strong>
                    <strong v-else>无可用历史行为</strong>
                  </div>
                </div>
                <div class="flow-arrows"><i></i><i></i></div>
                <div class="flow-col">
                  <div class="node semantic">
                    <span class="node-tag"><i></i>ALBERT 语义编码</span><small>语义虚假辅助概率</small>
                    <b class="node-figure num">{{ percent(explanation.semantic.authenticity_scores.fake) }}</b>
                  </div>
                  <div class="node behavior">
                    <span class="node-tag"><i></i>GRU 时序编码</span><small>行为异常辅助概率</small>
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
                    <small>建议{{ actionLabels[result.action] }}</small>
                  </div>
                </div>
              </div>
            </AppCard>

            <div class="grid-2 evidence-row">
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
                <p v-if="!explanation.behavior.available" class="alert-bar warn insufficient-note">
                  <Info :size="15" />历史长度为 0，行为证据不足，该状态不能解释为用户行为正常。
                </p>
                <ScoreBars :items="behaviorItems" :selected="explanation.behavior.selected_type" tone="behavior" />
              </AppCard>
            </div>
          </template>

          <AppCard v-else title="解释数据不可用" class="explanation-empty">
            <p class="empty-text">该结果没有保存解释快照，页面不会补造证据或细分类结论。</p>
          </AppCard>
          <AppCard v-if="explanation" title="解释边界" subtitle="审核与报告须保留以下说明" class="limitations-card">
            <ol class="limitations"><li v-for="(item, index) in explanation.limitations" :key="index">{{ item }}</li></ol>
          </AppCard>
        </div>

        <!-- 侧栏：结论 → 融合权重 → 追溯信息 → 关联记录 -->
        <aside class="stack side-col">
          <AppCard title="融合判定" class="verdict-card">
            <GaugeChart :value="fakeProbability" :threshold="explanation?.final.threshold" :tone="result.authenticity" label="融合虚假概率" />
            <div class="tag-row">
              <span class="tag" :class="result.authenticity === 'fake' ? 'fake' : 'ok'">{{ authenticityLabels[result.authenticity] }}</span>
              <span class="tag" :class="actionTone[result.action]">建议{{ actionLabels[result.action] }}</span>
            </div>
          </AppCard>

          <AppCard v-if="explanation" title="门控权重" subtitle="融合比例摘要，不构成因果归因" class="fusion-card">
            <DonutChart :parts="fusionParts" :center="fusionRatio" caption="语义 : 行为" />
            <ul class="legend">
              <li><i class="s"></i>语义证据<em :class="{ ok: explanation.evidence.semantic_evidence_state === 'available' }">{{ stateLabel(explanation.evidence.semantic_evidence_state) }}</em><b class="num">{{ percent(explanation.fusion.semantic_weight) }}</b></li>
              <li><i class="b"></i>行为证据<em :class="{ ok: explanation.evidence.behavior_evidence_state === 'available' }">{{ stateLabel(explanation.evidence.behavior_evidence_state) }}</em><b class="num">{{ percent(explanation.fusion.behavior_weight) }}</b></li>
              <li><i class="n"></i>分数校准<b>{{ stateLabel(explanation.evidence.calibration_state) }}</b></li>
            </ul>
          </AppCard>

          <AppCard title="检测信息" class="metadata-card">
            <dl class="meta">
              <dt>商品标识</dt><dd>{{ result.product_id || '未提供' }}</dd>
              <dt>匿名用户</dt><dd class="num" :title="result.user_key || ''">{{ result.user_key ? shortId(result.user_key) : '未提供' }}</dd>
              <dt>所属任务</dt><dd class="num" :title="result.task_id">{{ shortId(result.task_id, 6) }}</dd>
              <dt>检测时间</dt><dd class="num">{{ formatDateTime(result.created_at) }}</dd>
            </dl>
          </AppCard>

          <AppCard v-if="result.user_key" title="该用户的其他检测" :subtitle="relatedTotal ? `共 ${relatedTotal} 条` : '暂无其他检测'" class="related-card">
            <div v-if="related.length" class="related">
              <RouterLink v-for="item in related" :key="item.result_id" :to="`/results/${item.result_id}`" class="related-row">
                <span class="related-text"><p>{{ item.text_excerpt }}</p><small class="num">{{ formatDateTime(item.created_at) }}</small></span>
                <b class="num" :class="item.authenticity">{{ percent(fakeProbabilityOf(item), 0) }}</b>
              </RouterLink>
            </div>
          </AppCard>

        </aside>
      </div>
    </template>
  </section>
</template>

<style scoped>
.detail-layout { display: grid; grid-template-columns: minmax(0, 1fr) 340px; align-items: start; gap: 16px; }

.quote { margin: 0; padding: 16px 20px; border-left: 3px solid var(--color-primary); border-radius: 0 var(--radius-control) var(--radius-control) 0; background: var(--color-surface-muted); font-size: 18px; line-height: 1.7; }
.facts { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px 24px; margin: 20px 0 0; }
.facts dt { color: var(--color-text-muted); font-size: 13px; }
.facts dd { margin: 4px 0 0; font-size: 15px; font-weight: 500; }
.facts dd.muted { color: var(--color-text-muted); }

.flow { display: grid; grid-template-columns: 1fr 28px 1fr 28px 1fr; align-items: center; }
.flow-col { display: flex; min-width: 0; flex-direction: column; gap: 12px; }
.flow-arrows { display: flex; flex-direction: column; gap: 70px; }
.flow-arrows i { position: relative; display: block; height: 1.5px; margin: 0 4px; background: var(--color-line-strong); }
.flow-arrows i::after { position: absolute; top: -4px; right: -1px; border: 4.5px solid transparent; border-left: 6px solid var(--color-line-strong); content: ""; }
.node { display: flex; min-width: 0; min-height: 76px; flex-direction: column; justify-content: center; gap: 2px; padding: 10px 14px; border: 1px solid var(--color-line); border-radius: var(--radius-card); background: var(--color-surface); }
.node-tag { display: flex; align-items: center; gap: 6px; color: var(--color-text-muted); font-size: 12px; }
.node-tag i { width: 6px; height: 6px; border-radius: 50%; }
.node strong { font-size: 14px; font-weight: 500; }
.node .ellipsis { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.node small { color: var(--color-text-secondary); font-size: 12px; }
.node-figure { font-size: 22px; font-weight: 600; line-height: 1.3; }
.node-figure.muted { color: var(--color-text-muted); font-size: 17px; }
.node.input { background: var(--color-surface-muted); }
.node.semantic { border-color: var(--color-primary-soft-2); background: var(--color-primary-soft); }
.node.semantic .node-tag i { background: var(--color-primary); }
.node.semantic .node-figure { color: var(--color-primary); }
.node.behavior { border-color: color-mix(in srgb, var(--color-behavior) 25%, var(--color-mix-base)); background: var(--color-behavior-soft); }
.node.behavior .node-tag i { background: var(--color-behavior); }
.node.behavior .node-figure:not(.muted) { color: var(--color-behavior); }
.split { display: flex; height: 8px; margin: 6px 0 4px; overflow: hidden; border-radius: 4px; background: var(--color-track); }
.split .s { background: var(--color-primary); }
.split .b { background: var(--color-behavior); }
.node.outcome.fake { border-color: color-mix(in srgb, var(--color-fake) 25%, var(--color-mix-base)); background: var(--color-fake-soft); }
.node.outcome.fake .outcome-title { color: var(--color-fake); }
.node.outcome.real { border-color: color-mix(in srgb, var(--color-success) 25%, var(--color-mix-base)); background: var(--color-success-soft); }
.node.outcome.real .outcome-title { color: var(--color-success); }
.outcome-title { font-size: 16px !important; font-weight: 600 !important; }

.evidence-row { align-items: stretch; }
.aux { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 14px; }
.aux div { padding: 8px 12px; border-radius: var(--radius-control); background: var(--color-surface-muted); color: var(--color-text-muted); font-size: 12px; }
.aux b { display: block; color: var(--color-text); font-size: 18px; font-weight: 600; }
.insufficient-note { margin: 0 0 14px; }

.verdict-card { text-align: center; }
.verdict-card :deep(.card-head) { text-align: left; }
.tag-row { display: flex; justify-content: center; gap: 8px; margin-top: 8px; }
.legend { display: flex; flex-direction: column; gap: 10px; margin: 8px 0 0; padding: 0; list-style: none; color: var(--color-text-secondary); font-size: 13px; }
.legend li { display: flex; align-items: center; gap: 8px; }
.legend i { width: 8px; height: 8px; border-radius: 2px; }
.legend i.s { background: var(--color-primary); }
.legend i.b { background: var(--color-behavior); }
.legend i.n { background: var(--color-line-strong); }
.legend em { padding: 0 6px; border-radius: 4px; background: var(--color-warn-soft); color: var(--color-warn); font-size: 12px; font-style: normal; line-height: 20px; }
.legend em.ok { background: var(--color-success-soft); color: var(--color-success); }
.legend b { margin-left: auto; color: var(--color-text); font-weight: 500; }

.meta { display: grid; grid-template-columns: 72px 1fr; row-gap: 10px; margin: 0; font-size: 13px; }
.meta dt { color: var(--color-text-muted); }
.meta dd { margin: 0; word-break: break-all; }
.related { display: flex; flex-direction: column; margin: -6px 0; }
.related-row { display: flex; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--color-line); color: inherit; text-decoration: none; }
.related-row:last-child { border-bottom: 0; }
.related-row:hover p { color: var(--color-primary); }
.related-text { min-width: 0; flex: 1; }
.related-text p { margin: 0; overflow: hidden; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.related-text small { color: var(--color-text-muted); font-size: 12px; }
.related-row b { font-size: 14px; font-weight: 600; }
.related-row b.fake { color: var(--color-fake); }
.related-row b.real { color: var(--color-text-secondary); }
.limitations { display: grid; grid-template-columns: 1fr 1fr; column-gap: 32px; margin: 0; padding: 0; list-style: none; counter-reset: n; color: var(--color-text-secondary); font-size: 13px; line-height: 1.6; }
.limitations li { display: flex; gap: 10px; padding: 10px 0; border-bottom: 1px solid var(--color-line); counter-increment: n; }
.limitations li:nth-last-child(-n + 2) { border-bottom: 0; }
.limitations li::before { display: grid; flex: none; width: 20px; height: 20px; margin-top: 1px; place-items: center; border-radius: 50%; background: var(--color-track); color: var(--color-text-secondary); content: counter(n); font-size: 12px; }

.empty-text { margin: 0; color: var(--color-text-secondary); font-size: 13px; }
.report-summary { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 10px; margin: 0 0 16px; }
.report-summary div { padding: 8px 12px; border-radius: var(--radius-control); background: var(--color-surface-muted); }
.report-summary dt { color: var(--color-text-muted); font-size: 12px; }
.report-summary dd { margin: 2px 0 0; font-size: 13px; font-weight: 600; }
.report-downloads { display: flex; gap: 8px; }

@media (max-width: 1180px) {
  .detail-layout { grid-template-columns: 1fr; }
}
@media (max-width: 860px) {
  .flow { grid-template-columns: 1fr; gap: 12px; }
  .flow-arrows { display: none; }
  .facts { grid-template-columns: repeat(2, 1fr); }
}
</style>
