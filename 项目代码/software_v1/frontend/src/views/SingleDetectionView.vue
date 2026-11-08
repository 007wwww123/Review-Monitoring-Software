<script setup lang="ts">
import { computed, nextTick, reactive, ref } from 'vue';
import { AlertCircle, ArrowRight, Clock3, FileSearch, Info, Plus, RotateCcw, ShieldCheck, Trash2 } from 'lucide-vue-next';
import { ApiError, submitSingleDetection } from '../api/client';
import type { BehaviorHistoryItem, DetectionResultSummary, SingleDetectionRequest } from '../types';
import AppCard from '../components/AppCard.vue';
import PageHeader from '../components/layout/PageHeader.vue';
import GaugeChart from '../components/charts/GaugeChart.vue';
import { actionLabels, actionTone, authenticityLabels, behaviorLabels, fakeProbabilityOf, percent, riskLabels, semanticLabels, shortId } from '../labels';

type EditableHistory = { review_id: string; prod_id: string; rating: number; date: string; text: string };
type FormState = { review_id: string; user_id: string; prod_id: string; rating: number; date: string; text: string; history: EditableHistory[] };

const initialForm = (): FormState => ({ review_id: '', user_id: '', prod_id: '', rating: 5, date: '', text: '', history: [] });
const form = reactive<FormState>(initialForm());
const submitting = ref(false);
const errorMessage = ref('');
const result = ref<DetectionResultSummary | null>(null);
// 结果卡在第一行右侧，提交按钮在页面底部；出结果后把结果卡滚进视野
const resultCard = ref<{ $el: HTMLElement } | null>(null);
const taskId = ref('');
const validationErrors = ref<Record<string, string>>({});

// 单条接口只返回真实性与置信度，由此换算融合虚假概率
const fakeProbability = computed(() => result.value ? fakeProbabilityOf(result.value) : 0);
const errorCount = computed(() => Object.keys(validationErrors.value).length);
const pipeline = [
  { title: '评论文本与行为序列', desc: '提交的评论正文和此前的历史行为' },
  { title: 'ALBERT 语义编码', desc: '判断文本的语义类型和虚假倾向' },
  { title: 'GRU 时序编码', desc: '从历史行为序列中提取行为特征' },
  { title: '自适应门控融合', desc: '按证据可用程度分配两路权重' },
  { title: '审核建议', desc: '给出真实性判定与处置建议' },
];

function addHistory() {
  if (form.history.length >= 30) return;
  form.history.push({ review_id: '', prod_id: '', rating: 5, date: '', text: '' });
}

function removeHistory(index: number) {
  form.history.splice(index, 1);
}

function resetForm() {
  Object.assign(form, initialForm());
  validationErrors.value = {};
  errorMessage.value = '';
  result.value = null;
  taskId.value = '';
}

function validate(): boolean {
  const errors: Record<string, string> = {};
  if (!form.user_id.trim()) errors.user_id = '请输入用户 ID';
  else if (form.user_id.length > 128) errors.user_id = '用户 ID 最多 128 个字符';
  if (!form.prod_id.trim()) errors.prod_id = '请输入商品 ID';
  else if (form.prod_id.length > 128) errors.prod_id = '商品 ID 最多 128 个字符';
  if (form.review_id.length > 100) errors.review_id = '评论 ID 最多 100 个字符';
  if (!Number.isFinite(form.rating) || form.rating < 1 || form.rating > 5) errors.rating = '评分范围为 1 到 5';
  if (!form.date) errors.date = '请选择评论时间';
  if (!form.text.trim()) errors.text = '请输入评论文本';
  else if (form.text.length > 10000) errors.text = '评论文本最多 10000 个字符';
  const targetTime = form.date ? new Date(form.date).getTime() : NaN;
  form.history.forEach((item, index) => {
    if (!item.date) errors[`history-${index}`] = `第 ${index + 1} 条历史缺少时间`;
    else if (Number.isFinite(targetTime) && new Date(item.date).getTime() >= targetTime) errors[`history-${index}`] = `第 ${index + 1} 条历史时间必须早于目标评论`;
    else if (item.review_id.length > 100) errors[`history-${index}`] = `第 ${index + 1} 条历史评论 ID 过长`;
    else if (!item.prod_id.trim()) errors[`history-${index}`] = `第 ${index + 1} 条历史缺少商品 ID`;
    else if (!Number.isFinite(item.rating) || item.rating < 0 || item.rating > 5) errors[`history-${index}`] = `第 ${index + 1} 条历史评分范围为 0 到 5`;
  });
  validationErrors.value = errors;
  return Object.keys(errors).length === 0;
}

function toPayload(): SingleDetectionRequest {
  const history = form.history.map((item): BehaviorHistoryItem => ({
    ...(item.review_id.trim() ? { review_id: item.review_id.trim() } : {}),
    prod_id: item.prod_id.trim(),
    rating: item.rating,
    date: new Date(item.date).toISOString(),
    text: item.text.trim(),
  }));
  return {
    ...(form.review_id.trim() ? { review_id: form.review_id.trim() } : {}),
    user_id: form.user_id.trim(),
    prod_id: form.prod_id.trim(),
    rating: form.rating,
    date: new Date(form.date).toISOString(),
    text: form.text.trim(),
    behavior_history: history,
  };
}

async function submit() {
  if (submitting.value || !validate()) return;
  submitting.value = true;
  errorMessage.value = '';
  try {
    const response = await submitSingleDetection(toPayload());
    result.value = response.result;
    void nextTick(() => resultCard.value?.$el.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' }));
    taskId.value = response.task.task_id;
  } catch (error) {
    errorMessage.value = error instanceof ApiError ? error.message : '检测请求失败，请稍后重试。';
    result.value = null;
    taskId.value = '';
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <section class="page single-page">
    <PageHeader title="单条评论检测" desc="提交一条评论及可选的历史行为，获取语义与行为融合后的审核建议" :icon="FileSearch">
      <template #actions>
        <button type="button" class="btn" @click="resetForm"><RotateCcw :size="15" />重置表单</button>
      </template>
    </PageHeader>

    <div class="single-layout">
      <form class="single-form" novalidate @submit.prevent="submit">
        <AppCard title="评论信息" subtitle="带 * 的字段为必填项" class="info-card">
          <div v-if="errorCount" class="alert-bar" role="alert"><AlertCircle :size="16" />请检查表单中的 {{ errorCount }} 处问题。</div>
          <div v-if="errorMessage" class="alert-bar" role="alert"><AlertCircle :size="16" />{{ errorMessage }}</div>

          <div class="fields-grid">
            <label class="ui-field" :class="{ invalid: validationErrors.review_id }"><span>评论 ID<small>选填</small></span><input v-model="form.review_id" class="ui-input" maxlength="101" placeholder="例如 REV-20261102-001" /><em v-if="validationErrors.review_id" class="error-text">{{ validationErrors.review_id }}</em></label>
            <label class="ui-field" :class="{ invalid: validationErrors.user_id }"><span>用户 ID<em>*</em></span><input v-model="form.user_id" class="ui-input" maxlength="129" placeholder="匿名用户标识" /><em v-if="validationErrors.user_id" class="error-text">{{ validationErrors.user_id }}</em></label>
            <label class="ui-field" :class="{ invalid: validationErrors.prod_id }"><span>商品 ID<em>*</em></span><input v-model="form.prod_id" class="ui-input" maxlength="129" placeholder="商品或服务标识" /><em v-if="validationErrors.prod_id" class="error-text">{{ validationErrors.prod_id }}</em></label>
            <label class="ui-field" :class="{ invalid: validationErrors.rating }"><span>评分<em>*</em><small>1 – 5</small></span><input v-model.number="form.rating" class="ui-input" type="number" min="1" max="5" step="0.5" /><em v-if="validationErrors.rating" class="error-text">{{ validationErrors.rating }}</em></label>
            <label class="ui-field span-2" :class="{ invalid: validationErrors.date }"><span>评论时间<em>*</em></span><input v-model="form.date" class="ui-input" type="datetime-local" /><em v-if="validationErrors.date" class="error-text">{{ validationErrors.date }}</em></label>
            <label class="ui-field span-2" :class="{ invalid: validationErrors.text }">
              <span>评论文本<em>*</em></span>
              <textarea v-model="form.text" class="ui-input comment-text" maxlength="10001" rows="3" placeholder="请输入需要检测的原始评论内容"></textarea>
              <span class="field-meta"><em v-if="validationErrors.text" class="error-text">{{ validationErrors.text }}</em><small class="num">{{ form.text.length }} / 10000</small></span>
            </label>
          </div>
        </AppCard>

        <AppCard title="历史行为" subtitle="可选，最多 30 条，只能是目标评论之前的事件" class="history-card">
          <template #extra>
            <button type="button" class="btn small" data-testid="add-history" :disabled="form.history.length >= 30" @click="addHistory"><Plus :size="14" />添加历史</button>
          </template>
          <div v-if="!form.history.length" class="empty-hint history-empty"><Clock3 :size="28" :stroke-width="1.5" />暂无历史行为，本次结果的行为证据将标记为“证据不足”。</div>
          <div v-for="(item, index) in form.history" :key="index" class="history-row">
            <div class="history-head">
              <strong>历史事件 {{ index + 1 }}</strong>
              <button type="button" class="btn icon small" title="删除历史事件" :aria-label="`删除历史事件 ${index + 1}`" @click="removeHistory(index)"><Trash2 :size="15" /></button>
            </div>
            <div class="history-fields">
              <label class="ui-field"><span>历史评论 ID<small>选填</small></span><input v-model="item.review_id" class="ui-input" maxlength="101" placeholder="历史评论标识" /></label>
              <label class="ui-field"><span>历史商品 ID<em>*</em></span><input v-model="item.prod_id" class="ui-input" maxlength="128" placeholder="商品或服务标识" /></label>
              <label class="ui-field"><span>历史评分<em>*</em></span><input v-model.number="item.rating" class="ui-input" type="number" min="0" max="5" step="0.5" /></label>
              <label class="ui-field"><span>历史时间<em>*</em></span><input v-model="item.date" class="ui-input" type="datetime-local" /></label>
            </div>
            <label class="ui-field"><span>历史评论文本<small>选填</small></span><textarea v-model="item.text" class="ui-input history-text" maxlength="10000" rows="2" placeholder="用于计算历史文本长度特征"></textarea></label>
            <p v-if="validationErrors[`history-${index}`]" class="row-error">{{ validationErrors[`history-${index}`] }}</p>
          </div>
        </AppCard>

        <div class="submit-bar">
          <p><ShieldCheck :size="15" />用户标识会在服务端哈希后，用于查询目标时间之前的历史行为。</p>
          <button class="btn primary large submit-button" data-testid="submit" type="submit" :disabled="submitting">
            <span v-if="submitting" class="spinner"></span><ArrowRight v-else :size="16" />{{ submitting ? '检测中…' : '开始检测' }}
          </button>
        </div>
      </form>

      <AppCard ref="resultCard" title="检测结果" :subtitle="result ? '融合模型输出摘要' : '提交后在此显示'" class="result-card" aria-live="polite">
        <template v-if="result" #extra><span class="tag ok">已完成</span></template>

        <div v-if="!result" class="pipeline">
          <p class="pipeline-intro">每条评论都会依次经过以下环节：</p>
          <ol>
            <li v-for="(step, index) in pipeline" :key="step.title"><b>{{ index + 1 }}</b><span><strong>{{ step.title }}</strong><small>{{ step.desc }}</small></span></li>
          </ol>
        </div>

        <template v-else>
          <GaugeChart :value="fakeProbability" :tone="result.authenticity" label="融合虚假概率" />
          <div class="verdict-tags">
            <span class="tag" :class="result.authenticity === 'fake' ? 'fake' : 'ok'">{{ authenticityLabels[result.authenticity] }}</span>
            <span class="tag" :class="actionTone[result.action]">建议{{ actionLabels[result.action] }}</span>
          </div>
          <dl class="result-fields">
            <div><dt>置信度</dt><dd class="num">{{ percent(result.confidence) }}</dd></div>
            <div><dt>语义类型</dt><dd>{{ semanticLabels[result.semantic_type] }}</dd></div>
            <div><dt>行为类型</dt><dd :class="{ muted: result.behavior_type === 'insufficient_evidence' }">{{ behaviorLabels[result.behavior_type] }}</dd></div>
            <div><dt>风险来源</dt><dd>{{ riskLabels[result.risk_source] }}</dd></div>
            <div><dt>模型版本</dt><dd class="num">{{ result.model_version }}</dd></div>
            <div><dt>任务编号</dt><dd class="num" :title="taskId">{{ shortId(taskId, 6) }}</dd></div>
          </dl>
          <p v-if="result.behavior_type === 'insufficient_evidence'" class="alert-bar warn insufficient-note">
            <Info :size="15" /><span><b>行为证据不足</b>未提供可用历史，该状态不表示用户行为正常。</span>
          </p>
          <RouterLink :to="`/results/${result.result_id}`" class="btn primary full-analysis">查看完整分析<ArrowRight :size="15" /></RouterLink>
        </template>

        <p class="boundary"><Info :size="14" />检测结果仅作为辅助审核建议，不替代人工事实认定。</p>
      </AppCard>
    </div>
  </section>
</template>

<style scoped>
/* 只有第一行左右配对（评论信息 | 检测结果），历史行为和提交栏横跨整行，两栏不会一高一矮。
   第一行两张卡等高，高度差由评论文本框吸收；form 用 display: contents，让里面的卡片直接参与网格 */
.single-layout { display: grid; grid-template-columns: minmax(0, 1fr) 360px; grid-template-areas: "info result" "history history" "submit submit"; align-items: start; gap: 16px; }
.single-form { display: contents; }
.info-card { display: flex; flex-direction: column; grid-area: info; align-self: stretch; }
.history-card { grid-area: history; }
.fields-grid { display: grid; flex: 1; grid-template-columns: repeat(2, minmax(0, 1fr)); grid-template-rows: auto auto auto 1fr; gap: 18px 20px; }
/* 自然高度略小于右侧步骤，第一行的高度差总由文本框吸收，右卡不留空白 */
.comment-text { flex: 1; min-height: 96px; }
.span-2 { grid-column: span 2; }
.field-meta { display: flex; justify-content: space-between; gap: 8px; }
.field-meta small { margin-left: auto; color: var(--color-text-muted); font-size: 12px; }
.history-empty { padding: 24px 16px; border: 1px dashed var(--color-line-strong); border-radius: var(--radius-card); background: var(--color-surface-muted); }
.history-row { display: flex; flex-direction: column; gap: 12px; padding: 16px; border: 1px solid var(--color-line); border-radius: var(--radius-card); background: var(--color-surface-muted); }
.history-row + .history-row { margin-top: 12px; }
.history-head { display: flex; align-items: center; justify-content: space-between; }
.history-head strong { font-size: 14px; font-weight: 500; }
.history-fields { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.history-text { min-height: 64px; }
.row-error { margin: 0; color: var(--color-fake); font-size: 12px; }
.submit-bar { display: flex; grid-area: submit; align-items: center; justify-content: space-between; gap: 16px; padding: 16px 20px; border-radius: var(--radius-card); background: var(--color-surface); box-shadow: var(--shadow-card); }
.submit-bar p { display: flex; align-items: center; gap: 6px; margin: 0; color: var(--color-text-muted); font-size: 13px; }
.submit-button { min-width: 140px; }

.result-card { display: flex; flex-direction: column; grid-area: result; align-self: stretch; }
.pipeline { margin-bottom: 16px; }
.pipeline-intro { margin: 0 0 12px; color: var(--color-text-secondary); font-size: 13px; }
.pipeline ol { position: relative; display: flex; flex-direction: column; gap: 6px; margin: 0; padding: 0; list-style: none; }
.pipeline ol::before { position: absolute; top: 16px; bottom: 30px; left: 13px; width: 2px; background: var(--color-line); content: ""; }
.pipeline li { position: relative; display: flex; align-items: flex-start; gap: 12px; padding: 6px 0; }
.pipeline li b { z-index: 1; display: grid; flex: none; width: 28px; height: 28px; place-items: center; border: 3px solid var(--color-surface); border-radius: 50%; background: var(--color-primary-soft); color: var(--color-primary); font-size: 12px; }
.pipeline li:nth-child(3) b { background: var(--color-behavior-soft); color: var(--color-behavior); }
.pipeline li:last-child b { background: var(--color-primary); color: var(--color-on-primary); }
.pipeline li strong { display: block; font-size: 14px; font-weight: 500; line-height: 22px; }
.pipeline li small { color: var(--color-text-muted); font-size: 12px; }
.verdict-tags { display: flex; justify-content: center; gap: 8px; margin: 8px 0 16px; }
.result-fields { display: grid; grid-template-columns: 1fr 1fr; gap: 14px 16px; margin: 0; padding: 14px 16px; border-radius: var(--radius-card); background: var(--color-surface-muted); }
.result-fields dt { color: var(--color-text-muted); font-size: 12px; }
.result-fields dd { margin: 2px 0 0; font-size: 14px; font-weight: 500; word-break: break-all; }
.result-fields dd.muted { color: var(--color-text-muted); }
.insufficient-note { align-items: flex-start; margin: 12px 0 0; }
.insufficient-note svg { margin-top: 2px; }
.insufficient-note b { margin-right: 4px; }
.full-analysis { width: 100%; margin: 16px 0; }
/* 右卡比左卡矮时，说明贴底，多出的高度落在步骤与说明之间 */
.boundary { display: flex; align-items: center; gap: 6px; margin: auto 0 0; padding-top: 14px; border-top: 1px solid var(--color-line); color: var(--color-text-muted); font-size: 12px; }

@media (max-width: 1120px) {
  .single-layout { grid-template-columns: 1fr; grid-template-areas: "info" "history" "submit" "result"; }
}
@media (max-width: 860px) {
  .fields-grid, .history-fields { grid-template-columns: 1fr; }
  .span-2 { grid-column: auto; }
  .submit-bar { flex-direction: column; align-items: stretch; }
}
</style>
