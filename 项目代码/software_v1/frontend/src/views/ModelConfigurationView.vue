<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { AlertCircle, Cpu, RefreshCw, ShieldCheck } from 'lucide-vue-next';
import { ApiError, getModelVersions } from '../api/client';
import type { ModelVersionResponse } from '../types';
import { formatDateTime } from '../labels';
defineProps<{ embedded?: boolean }>();

const models = ref<ModelVersionResponse[]>([]);
const selectedVersion = ref('');
const loading = ref(true);
const errorMessage = ref('');
const selected = computed(() => models.value.find((item) => item.version === selectedVersion.value) ?? models.value[0]);
const configEntries = computed(() => Object.entries(selected.value?.config ?? {}));

// 模型配置项的中文说明；键名照原样保留，便于和 base.json 对照
const CONFIG_LABELS: Record<string, string> = {
  albert_name_or_path: '预训练语义模型', max_length: '最大文本长度', semantic_num_labels: '语义类别数', behavior_num_labels: '行为类别数',
  behavior_type_num_labels: '异常行为细类数', behavior_input_size: '行为特征维度', behavior_hidden_size: 'GRU 隐层大小', behavior_num_layers: 'GRU 层数',
  behavior_dropout: '行为分支丢弃率', fusion_hidden_size: '融合隐层大小', fusion_dropout: '融合层丢弃率', classifier_dropout: '分类头丢弃率',
  use_behavior_attention: '行为注意力', real_exit_threshold: '真实提前退出阈值', semantic_exit_threshold: '语义提前退出阈值',
  behavior_trigger_threshold: '行为触发阈值', uncertainty_entropy_threshold: '不确定性熵阈值', authenticity_threshold: '真实性判定阈值',
  allow_type_override: '允许类型覆盖', minimum_history: '最少历史条数', maximum_history: '最多历史条数',
  semantic_labels: '语义标签顺序', behavior_labels: '行为标签顺序',
};

function displayValue(value: unknown) {
  if (Array.isArray(value)) return value.join(' → ');
  if (typeof value === 'boolean') return value ? '启用' : '禁用';
  if (value && typeof value === 'object') return JSON.stringify(value);
  return String(value ?? '未配置');
}

async function loadModels() {
  loading.value = true; errorMessage.value = '';
  try {
    models.value = await getModelVersions();
    if (!models.value.some((item) => item.version === selectedVersion.value)) selectedVersion.value = models.value.find((item) => item.is_active)?.version ?? models.value[0]?.version ?? '';
  } catch (error) {
    errorMessage.value = error instanceof ApiError ? error.message : '模型版本加载失败，请稍后重试。';
  } finally { loading.value = false; }
}

onMounted(loadModels);
</script>

<template>
  <section class="model-config" :class="{ standalone: !embedded }">
    <div v-if="errorMessage" class="alert-bar" role="alert">
      <AlertCircle :size="16" />{{ errorMessage }}
      <button type="button" class="btn small retry" @click="loadModels"><RefreshCw :size="14" />重新加载</button>
    </div>

    <div class="models-layout">
      <div class="version-list">
        <p class="list-title">已登记版本 <span class="num">{{ models.length }}</span></p>
        <div v-if="loading" class="empty-hint"><span class="spinner dark"></span>正在加载模型版本…</div>
        <div v-else-if="!models.length" class="empty-hint">尚未登记模型版本</div>
        <button
          v-for="model in models" v-else :key="model.version" type="button"
          class="model-version-row" :class="{ selected: selected?.version === model.version }" @click="selectedVersion = model.version"
        >
          <span class="model-icon"><Cpu :size="17" /></span>
          <span class="version-text"><strong class="num">{{ model.version }}</strong><small>{{ model.model_name }}</small></span>
          <span v-if="model.is_active" class="tag ok">当前使用</span>
        </button>
      </div>

      <div v-if="selected" class="model-detail">
        <div class="model-detail-head">
          <div><span class="hint">版本详情</span><h3 class="num">{{ selected.version }}</h3><p>{{ selected.model_name }}</p></div>
          <button type="button" class="btn" disabled>{{ selected.is_active ? '当前使用' : '需重启切换' }}</button>
        </div>
        <dl class="identity">
          <div><dt>分词器</dt><dd>{{ selected.tokenizer_name }}</dd></div>
          <div><dt>登记时间</dt><dd class="num">{{ formatDateTime(selected.created_at) }}</dd></div>
          <div class="wide"><dt>检查点 SHA-256</dt><dd class="mono">{{ selected.checkpoint_sha256 }}</dd></div>
        </dl>

        <h4>运行配置<span class="hint">由后端模型登记信息返回，只读展示</span></h4>
        <dl class="config-grid">
          <div v-for="([key, value]) in configEntries" :key="key">
            <dt>{{ CONFIG_LABELS[key] ?? key }}<code>{{ key }}</code></dt>
            <dd>{{ displayValue(value) }}</dd>
          </div>
        </dl>

        <div class="metrics-state">
          <ShieldCheck :size="20" />
          <div>
            <h4>评估指标</h4>
            <dl v-if="selected.metrics" class="metric-pairs"><div v-for="(value, key) in selected.metrics" :key="key"><dt>{{ key }}</dt><dd>{{ value }}</dd></div></dl>
            <p v-else>当前版本没有可验证的历史指标快照。页面不会生成或补造准确率、F1、AUC 等指标。</p>
          </div>
        </div>
        <p class="model-boundary"><AlertCircle :size="15" />V1.0 不支持在线热切换。更换模型后必须更新并校验模型清单，再重启后端和 GPU Worker。</p>
      </div>
    </div>
  </section>
</template>

<style scoped>
.model-config.standalone { padding: 22px 28px; }
.retry { margin-left: auto; }
.models-layout { display: grid; grid-template-columns: 250px minmax(0, 1fr); gap: 18px; }
.list-title { margin: 0 0 8px; color: var(--color-text-muted); font-size: 12px; font-weight: 600; }
.version-list { display: flex; flex-direction: column; gap: 8px; }
.model-version-row { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 10px; padding: 10px 12px; border: 1px solid var(--color-line); border-radius: var(--radius-card); background: var(--color-surface); color: var(--color-text); font: inherit; text-align: left; cursor: pointer; }
.model-version-row:hover { border-color: var(--color-primary); }
.model-version-row.selected { border-color: var(--color-primary); background: var(--color-primary-soft); }
.model-icon { display: grid; width: 32px; height: 32px; place-items: center; border-radius: 8px; background: var(--color-primary-soft); color: var(--color-primary); }
.version-text { min-width: 0; }
.version-text strong { display: block; font-size: 13px; }
.version-text small { display: block; overflow: hidden; color: var(--color-text-muted); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.model-detail { min-width: 0; }
.model-detail-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; padding-bottom: 14px; border-bottom: 1px solid var(--color-line); }
.model-detail-head h3 { margin: 2px 0 0; font-size: 18px; }
.model-detail-head p { margin: 2px 0 0; color: var(--color-text-secondary); font-size: 13px; }
.identity { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 20px; margin: 14px 0 18px; font-size: 13px; }
.identity .wide { grid-column: span 2; }
.identity dt { color: var(--color-text-muted); font-size: 12px; }
.identity dd { margin: 2px 0 0; word-break: break-all; }
.mono { font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 12px; }
h4 { display: flex; align-items: baseline; gap: 8px; margin: 0 0 10px; font-size: 14px; }
.config-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 8px; margin: 0 0 18px; }
.config-grid div { padding: 10px 12px; border-radius: var(--radius-control); background: var(--color-surface-muted); }
.config-grid dt { display: flex; flex-direction: column; color: var(--color-text-secondary); font-size: 12px; }
.config-grid code { color: var(--color-text-muted); font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 11px; font-weight: 400; }
.config-grid dd { margin: 4px 0 0; font-size: 13px; font-weight: 500; word-break: break-word; }
.metrics-state { display: flex; gap: 12px; padding: 14px; border: 1px solid var(--color-primary-soft-2); border-radius: var(--radius-card); background: var(--color-primary-soft); color: var(--color-primary); }
.metrics-state p { margin: 0; color: var(--color-text-secondary); font-size: 13px; }
.metric-pairs { display: flex; flex-wrap: wrap; gap: 6px 20px; margin: 0; font-size: 13px; }
.metric-pairs dd { margin: 0; font-weight: 600; }
.model-boundary { display: flex; align-items: center; gap: 6px; margin: 14px 0 0; color: var(--color-warn); font-size: 12px; }

@media (max-width: 1120px) {
  .models-layout { grid-template-columns: 1fr; }
}
</style>
