<script setup lang="ts">
import { computed, reactive, ref } from 'vue';
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Clock3,
  Plus,
  RotateCcw,
  ShieldAlert,
  Trash2,
} from 'lucide-vue-next';
import { ApiError, submitSingleDetection } from '../api/client';
import type {
  Action,
  Authenticity,
  BehaviorHistoryItem,
  BehaviorType,
  DetectionResultSummary,
  RiskSource,
  SemanticType,
  SingleDetectionRequest,
} from '../types';

type EditableHistory = { review_id: string; date: string; features: number[] };
type FormState = { review_id: string; user_id: string; prod_id: string; rating: number; date: string; text: string; history: EditableHistory[] };

const initialForm = (): FormState => ({ review_id: '', user_id: '', prod_id: '', rating: 5, date: '', text: '', history: [] });
const form = reactive<FormState>(initialForm());
const submitting = ref(false);
const errorMessage = ref('');
const result = ref<DetectionResultSummary | null>(null);
const taskId = ref('');
const validationErrors = ref<Record<string, string>>({});

const semanticLabels: Record<SemanticType, string> = { real: '真实语义', misleading: '误导性', exaggerated: '夸张性', advertising: '广告性', none: '无', uncertain: '不确定' };
const behaviorLabels: Record<BehaviorType, string> = { normal: '行为正常', review_manipulation: '评论操纵', crowdturfing: '群体操纵', bot_like: '机器行为', insufficient_evidence: '行为证据不足' };
const riskLabels: Record<RiskSource, string> = { real: '未发现风险', language_fake: '语义风险', behavior_fake: '行为风险', language_behavior_composite: '语义与行为复合风险', uncertain: '风险不确定' };
const actionLabels: Record<Action, string> = { keep: '保留', review: '人工复核', block: '拦截' };
const authenticityLabels: Record<Authenticity, string> = { real: '真实', fake: '疑似虚假' };
const featureLabels = ['评分偏差', '时间间隔', '文本长度', '重复度', '评分变化', '活跃频率', '商品集中度', '极端评分比', '时间密度', '历史数量'];

const resultTone = computed(() => result.value?.authenticity === 'fake' ? 'danger' : 'success');

function addHistory() {
  if (form.history.length >= 30) return;
  form.history.push({ review_id: '', date: '', features: Array(10).fill(0) });
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
    else if (item.features.length !== 10 || item.features.some((value) => !Number.isFinite(value))) errors[`history-${index}`] = `第 ${index + 1} 条历史必须包含 10 个有效数值`;
  });
  validationErrors.value = errors;
  return Object.keys(errors).length === 0;
}

function toPayload(): SingleDetectionRequest {
  const history = form.history.map((item): BehaviorHistoryItem => ({
    ...(item.review_id.trim() ? { review_id: item.review_id.trim() } : {}),
    date: new Date(item.date).toISOString(),
    features: item.features as BehaviorHistoryItem['features'],
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
  <section class="page-content">
    <div class="page-heading">
      <div>
        <span class="eyebrow">内容审核 / 单条检测</span>
        <h1>单条评论检测</h1>
        <p>提交评论与可选历史行为，获取语义和行为融合后的审核建议。</p>
      </div>
      <span class="api-state"><span></span>Mock API 已连接</span>
    </div>

    <div class="detection-layout">
      <form class="form-panel" novalidate @submit.prevent="submit">
        <div class="section-heading">
          <div><h2>评论信息</h2><p>带 * 的字段为必填项</p></div>
          <button type="button" class="icon-text-button secondary" @click="resetForm"><RotateCcw :size="16" />重置</button>
        </div>

        <div v-if="Object.keys(validationErrors).length" class="alert error" role="alert">
          <AlertCircle :size="18" /><span>请检查表单中的 {{ Object.keys(validationErrors).length }} 处问题。</span>
        </div>
        <div v-if="errorMessage" class="alert error" role="alert">
          <AlertCircle :size="18" /><span>{{ errorMessage }}</span>
        </div>

        <div class="form-grid">
          <label class="field"><span>评论 ID <small>选填</small></span><input v-model="form.review_id" maxlength="101" placeholder="例如 REV-20260811-001" /><em v-if="validationErrors.review_id">{{ validationErrors.review_id }}</em></label>
          <label class="field"><span>用户 ID *</span><input v-model="form.user_id" maxlength="129" placeholder="匿名用户标识" /><em v-if="validationErrors.user_id">{{ validationErrors.user_id }}</em></label>
          <label class="field"><span>商品 ID *</span><input v-model="form.prod_id" maxlength="129" placeholder="商品或服务标识" /><em v-if="validationErrors.prod_id">{{ validationErrors.prod_id }}</em></label>
          <label class="field"><span>评分 *</span><input v-model.number="form.rating" type="number" min="1" max="5" step="0.5" /><em v-if="validationErrors.rating">{{ validationErrors.rating }}</em></label>
          <label class="field span-2"><span>评论时间 *</span><input v-model="form.date" type="datetime-local" /><em v-if="validationErrors.date">{{ validationErrors.date }}</em></label>
          <label class="field span-2"><span>评论文本 *</span><textarea v-model="form.text" maxlength="10001" rows="5" placeholder="请输入需要检测的原始评论内容"></textarea><span class="field-meta"><em v-if="validationErrors.text">{{ validationErrors.text }}</em><small>{{ form.text.length }} / 10000</small></span></label>
        </div>

        <div class="history-section">
          <div class="section-heading compact">
            <div><h2>历史行为</h2><p>可选，最多 30 条，仅允许目标评论之前的事件</p></div>
            <button type="button" class="icon-text-button secondary" data-testid="add-history" :disabled="form.history.length >= 30" @click="addHistory"><Plus :size="16" />添加历史</button>
          </div>

          <div v-if="!form.history.length" class="empty-history">
            <Clock3 :size="20" /><span>暂无历史行为，本次结果将标记为“行为证据不足”。</span>
          </div>

          <div v-for="(item, index) in form.history" :key="index" class="history-row">
            <div class="history-row-head">
              <strong>历史事件 {{ index + 1 }}</strong>
              <button type="button" class="icon-button danger-button" title="删除历史事件" :aria-label="`删除历史事件 ${index + 1}`" @click="removeHistory(index)"><Trash2 :size="16" /></button>
            </div>
            <div class="history-base">
              <label class="field"><span>历史评论 ID <small>选填</small></span><input v-model="item.review_id" maxlength="101" placeholder="历史评论标识" /></label>
              <label class="field"><span>历史时间 *</span><input v-model="item.date" type="datetime-local" /></label>
            </div>
            <div class="feature-grid">
              <label v-for="(feature, featureIndex) in featureLabels" :key="feature" class="feature-field">
                <span>{{ featureIndex + 1 }}. {{ feature }}</span>
                <input v-model.number="item.features[featureIndex]" type="number" step="any" />
              </label>
            </div>
            <p v-if="validationErrors[`history-${index}`]" class="row-error">{{ validationErrors[`history-${index}`] }}</p>
          </div>
        </div>

        <div class="form-actions">
          <p><ShieldAlert :size="16" />用户标识仅用于本次模拟检测，不会发送至真实模型服务。</p>
          <button class="primary-button" data-testid="submit" type="submit" :disabled="submitting">
            <span v-if="submitting" class="spinner"></span><ArrowRight v-else :size="18" />{{ submitting ? '检测中…' : '开始检测' }}
          </button>
        </div>
      </form>

      <aside class="result-panel" aria-live="polite">
        <div class="section-heading"><div><h2>检测结果</h2><p>模型输出摘要</p></div><span v-if="result" class="status-pill">已完成</span></div>

        <div v-if="!result" class="result-empty">
          <div class="result-empty-icon"><ShieldAlert :size="25" /></div>
          <strong>等待检测</strong>
          <p>完成左侧表单并提交后，结果摘要将在此显示。</p>
        </div>

        <template v-else>
          <div class="verdict" :class="resultTone">
            <CheckCircle2 v-if="result.authenticity === 'real'" :size="22" />
            <AlertCircle v-else :size="22" />
            <div><small>真实性判断</small><strong>{{ authenticityLabels[result.authenticity] }}</strong></div>
            <span>{{ Math.round(result.confidence * 100) }}%</span>
          </div>
          <div class="confidence-bar"><span :style="{ width: `${result.confidence * 100}%` }"></span></div>

          <dl class="result-list">
            <div><dt>语义类型</dt><dd>{{ semanticLabels[result.semantic_type] }}</dd></div>
            <div><dt>行为类型</dt><dd :class="{ muted: result.behavior_type === 'insufficient_evidence' }">{{ behaviorLabels[result.behavior_type] }}</dd></div>
            <div><dt>风险来源</dt><dd>{{ riskLabels[result.risk_source] }}</dd></div>
            <div><dt>处置建议</dt><dd><span class="action-badge" :class="result.action">{{ actionLabels[result.action] }}</span></dd></div>
            <div><dt>模型版本</dt><dd class="mono">{{ result.model_version }}</dd></div>
            <div><dt>任务编号</dt><dd class="mono task-id">{{ taskId }}</dd></div>
          </dl>

          <div v-if="result.behavior_type === 'insufficient_evidence'" class="evidence-note">
            <AlertCircle :size="17" /><p><strong>行为证据不足</strong><span>未提供可用历史，该状态不表示用户行为正常。</span></p>
          </div>
        </template>

        <div class="review-boundary">
          <ShieldAlert :size="17" /><p>检测结果仅作为辅助审核建议，不替代人工事实认定。</p>
        </div>
      </aside>
    </div>
  </section>
</template>
