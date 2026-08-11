<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  FileJson,
  FileSpreadsheet,
  RefreshCw,
  Scale,
  ShieldAlert,
} from 'lucide-vue-next';
import { ApiError, createTaskReport, downloadTaskReport, getDetectionResult } from '../api/client';
import type {
  Action,
  Authenticity,
  BehaviorType,
  DetectionResultResponse,
  ReportSummaryResponse,
  RiskSource,
  SemanticType,
} from '../types';

const route = useRoute();
const result = ref<DetectionResultResponse | null>(null);
const report = ref<ReportSummaryResponse | null>(null);
const loading = ref(true);
const errorMessage = ref('');
const reportError = ref('');
const creatingReport = ref(false);
const downloading = ref<'json' | 'csv' | null>(null);

const resultId = computed(() => Number(route.params.resultId));
const semanticOrder = ['real', 'misleading', 'exaggerated', 'advertising'] as const;
const behaviorOrder = ['normal', 'review_manipulation', 'crowdturfing', 'bot_like', 'insufficient_evidence'] as const;
const authenticityLabels: Record<Authenticity, string> = { real: '真实', fake: '疑似虚假' };
const semanticLabels: Record<SemanticType, string> = { real: '真实语义', misleading: '误导性', exaggerated: '夸张性', advertising: '广告性', none: '无', uncertain: '不确定' };
const behaviorLabels: Record<BehaviorType, string> = { normal: '行为正常', review_manipulation: '评论操纵', crowdturfing: '群体操纵', bot_like: '机器行为', insufficient_evidence: '行为证据不足' };
const riskLabels: Record<RiskSource, string> = { real: '未发现风险', language_fake: '语义风险', behavior_fake: '行为风险', language_behavior_composite: '语义与行为复合风险', uncertain: '风险不确定' };
const actionLabels: Record<Action, string> = { keep: '保留', review: '人工复核', block: '拦截' };
const evidenceLabels: Record<string, string> = { available: '可用', insufficient: '证据不足', uncalibrated: '未校准', calibrated: '已校准' };

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

function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

onMounted(loadResult);
watch(() => route.params.resultId, loadResult);
</script>

<template>
  <section class="page-content detail-page">
    <div class="detail-back-row">
      <RouterLink to="/results" class="back-link"><ArrowLeft :size="16" />返回检测记录</RouterLink>
      <span v-if="result" class="mono">结果 #{{ result.result_id }}</span>
    </div>

    <div v-if="loading" class="detail-state"><span class="spinner dark"></span><strong>正在加载结果与证据…</strong></div>
    <div v-else-if="errorMessage" class="detail-state error-state">
      <AlertCircle :size="30" /><strong>{{ errorMessage }}</strong>
      <button type="button" class="icon-text-button secondary" @click="loadResult"><RefreshCw :size="16" />重新加载</button>
    </div>

    <template v-else-if="result">
      <header class="detail-hero">
        <div>
          <span class="eyebrow">检测结果 / 证据详情</span>
          <h1>{{ result.review_id || `结果 ${result.result_id}` }}</h1>
          <p>{{ result.text_excerpt || '未保存评论摘要' }}</p>
        </div>
        <div class="detail-verdict" :class="result.authenticity">
          <CheckCircle2 v-if="result.authenticity === 'real'" :size="23" />
          <AlertCircle v-else :size="23" />
          <span><small>真实性判断</small><strong>{{ authenticityLabels[result.authenticity] }}</strong></span>
          <b>{{ percent(result.confidence) }}</b>
        </div>
      </header>

      <div class="detail-layout">
        <main class="detail-main">
          <section class="detail-section summary-section">
            <div class="section-heading"><div><h2>结果摘要</h2><p>最终融合输出与审核建议</p></div><span class="action-badge" :class="result.action">{{ actionLabels[result.action] }}</span></div>
            <dl class="summary-grid">
              <div><dt>融合虚假概率</dt><dd>{{ percent(result.explanation?.final.fake_probability ?? (result.authenticity === 'fake' ? result.confidence : 1 - result.confidence)) }}</dd></div>
              <div><dt>判断阈值</dt><dd>{{ result.explanation ? percent(result.explanation.final.threshold) : '未保存' }}</dd></div>
              <div><dt>风险来源</dt><dd>{{ riskLabels[result.risk_source] }}</dd></div>
              <div><dt>语义类型</dt><dd>{{ semanticLabels[result.semantic_type] }}</dd></div>
              <div><dt>行为类型</dt><dd :class="{ warning: result.behavior_type === 'insufficient_evidence' }">{{ behaviorLabels[result.behavior_type] }}</dd></div>
              <div><dt>模型版本</dt><dd class="mono">{{ result.model_version }}</dd></div>
            </dl>
          </section>

          <template v-if="result.explanation">
            <section class="detail-section evidence-section">
              <div class="section-heading"><div><h2>语义相对匹配度</h2><p>固定四标签顺序，分数未经独立校准时不代表确定类别</p></div><span class="selected-type">{{ semanticLabels[result.explanation.semantic.selected_type] }}</span></div>
              <dl class="evidence-meta">
                <div><dt>ALBERT真实辅助概率</dt><dd>{{ percent(result.explanation.semantic.authenticity_scores.real) }}</dd></div>
                <div><dt>ALBERT虚假辅助概率</dt><dd>{{ percent(result.explanation.semantic.authenticity_scores.fake) }}</dd></div>
              </dl>
              <div class="score-list semantic-scores">
                <div v-for="label in semanticOrder" :key="label" class="score-row">
                  <span>{{ semanticLabels[label] }}</span><div><i :style="{ width: percent(result.explanation.semantic.scores[label]) }"></i></div><strong>{{ percent(result.explanation.semantic.scores[label]) }}</strong>
                </div>
              </div>
            </section>

            <section class="detail-section evidence-section">
              <div class="section-heading"><div><h2>行为相对匹配度</h2><p>行为分支属于真实性代理任务，不是独立异常行为真值</p></div><span class="selected-type" :class="{ warning: !result.explanation.behavior.available }">{{ behaviorLabels[result.explanation.behavior.selected_type] }}</span></div>
              <div v-if="!result.explanation.behavior.available" class="evidence-note detail-warning"><AlertCircle :size="17" /><p><strong>行为证据不足</strong><span>历史长度为 0，该状态不能解释为用户行为正常。</span></p></div>
              <div class="score-list behavior-scores">
                <div v-for="label in behaviorOrder" :key="label" class="score-row">
                  <span>{{ behaviorLabels[label] }}</span><div><i :style="{ width: percent(result.explanation.behavior.scores[label]) }"></i></div><strong>{{ percent(result.explanation.behavior.scores[label]) }}</strong>
                </div>
              </div>
              <dl class="evidence-meta">
                <div><dt>GRU正常辅助概率</dt><dd>{{ percent(result.explanation.behavior.normality_scores.normal) }}</dd></div>
                <div><dt>GRU异常辅助概率</dt><dd>{{ percent(result.explanation.behavior.normality_scores.abnormal) }}</dd></div>
                <div><dt>证据可用性</dt><dd>{{ result.explanation.behavior.available ? '可用' : '不可用' }}</dd></div>
                <div><dt>历史长度</dt><dd>{{ result.explanation.behavior.history_length }}</dd></div>
                <div><dt>任务性质</dt><dd>{{ result.explanation.behavior.is_proxy_task ? '真实性代理任务' : '独立监督任务' }}</dd></div>
              </dl>
            </section>

            <section class="detail-section fusion-section">
              <div class="section-heading"><div><h2>融合权重摘要</h2><p>权重描述本次融合比例，不构成因果归因</p></div><Scale :size="19" /></div>
              <div class="fusion-bar"><span class="semantic-part" :style="{ width: percent(result.explanation.fusion.semantic_weight) }"></span><span class="behavior-part" :style="{ width: percent(result.explanation.fusion.behavior_weight) }"></span></div>
              <div class="fusion-legend"><span><i class="semantic-dot"></i>语义 {{ percent(result.explanation.fusion.semantic_weight) }}</span><span><i class="behavior-dot"></i>行为 {{ percent(result.explanation.fusion.behavior_weight) }}</span></div>
              <p class="weight-summary">{{ result.explanation.fusion.weight_summary }}</p>
              <dl class="evidence-states">
                <div><dt>语义证据</dt><dd>{{ evidenceLabels[result.explanation.evidence.semantic_evidence_state] || result.explanation.evidence.semantic_evidence_state }}</dd></div>
                <div><dt>行为证据</dt><dd>{{ evidenceLabels[result.explanation.evidence.behavior_evidence_state] || result.explanation.evidence.behavior_evidence_state }}</dd></div>
                <div><dt>校准状态</dt><dd>{{ evidenceLabels[result.explanation.evidence.calibration_state] || result.explanation.evidence.calibration_state }}</dd></div>
              </dl>
            </section>

            <section class="detail-section disclaimer-section">
              <div class="section-heading"><div><h2>解释边界</h2><p>审核和报告必须保留以下说明</p></div><ShieldAlert :size="19" /></div>
              <ol><li v-for="(item, index) in result.explanation.limitations" :key="index"><span>{{ index + 1 }}</span><p>{{ item }}</p></li></ol>
            </section>
          </template>

          <section v-else class="detail-section explanation-empty">
            <AlertCircle :size="24" /><div><h2>解释数据不可用</h2><p>该结果没有保存 Explanation 快照，页面不会补造证据或细分类结论。</p></div>
          </section>
        </main>

        <aside class="detail-side">
          <section class="detail-section metadata-section">
            <div class="section-heading"><div><h2>检测信息</h2><p>结果追溯字段</p></div></div>
            <dl class="result-list detail-metadata">
              <div><dt>匿名用户</dt><dd class="mono">{{ result.user_key || '未提供' }}</dd></div>
              <div><dt>商品标识</dt><dd class="mono">{{ result.product_id || '未提供' }}</dd></div>
              <div><dt>任务编号</dt><dd class="mono task-id">{{ result.task_id }}</dd></div>
              <div><dt>检测时间</dt><dd>{{ new Date(result.created_at).toLocaleString('zh-CN') }}</dd></div>
            </dl>
          </section>

          <section class="detail-section report-section">
            <div class="section-heading"><div><h2>任务报告</h2><p>报告覆盖整个检测任务，不是单条结果报告</p></div></div>
            <div v-if="!report" class="report-create">
              <FileJson :size="24" /><p>生成任务计数摘要后可下载 JSON 或 CSV。</p>
              <button type="button" class="primary-button" :disabled="creatingReport" @click="generateReport">{{ creatingReport ? '生成中…' : '生成任务报告' }}</button>
            </div>
            <template v-else>
              <div class="report-ready"><CheckCircle2 :size="19" /><div><strong>报告已生成</strong><span class="mono">#{{ report.report_id }}</span></div></div>
              <dl class="report-summary">
                <div v-for="(value, key) in report.summary" :key="key"><dt>{{ key }}</dt><dd>{{ value }}</dd></div>
              </dl>
              <div class="report-downloads">
                <button type="button" class="icon-text-button secondary" :disabled="Boolean(downloading)" @click="download('json')"><FileJson :size="16" />{{ downloading === 'json' ? '下载中…' : 'JSON' }}</button>
                <button type="button" class="icon-text-button secondary" :disabled="Boolean(downloading)" @click="download('csv')"><FileSpreadsheet :size="16" />{{ downloading === 'csv' ? '下载中…' : 'CSV' }}</button>
              </div>
            </template>
            <div v-if="reportError" class="alert error report-error" role="alert"><AlertCircle :size="17" /><span>{{ reportError }}</span></div>
          </section>
        </aside>
      </div>
    </template>
  </section>
</template>
