<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { AlertCircle, CheckCircle2, Cpu, RefreshCw, ShieldCheck } from 'lucide-vue-next';
import { activateModelVersion, ApiError, getModelVersions } from '../api/client';
import type { ModelVersionResponse } from '../types';
defineProps<{ embedded?: boolean }>();

const models = ref<ModelVersionResponse[]>([]);
const selectedVersion = ref('');
const loading = ref(true);
const activating = ref('');
const errorMessage = ref('');
const successMessage = ref('');
const selected = computed(() => models.value.find((item) => item.version === selectedVersion.value) ?? models.value[0]);
const configEntries = computed(() => Object.entries(selected.value?.config ?? {}));

function displayValue(value: unknown) {
  if (Array.isArray(value)) return value.join(' → ');
  if (typeof value === 'boolean') return value ? '启用' : '禁用';
  if (value && typeof value === 'object') return JSON.stringify(value);
  return String(value ?? '未配置');
}

async function loadModels() {
  loading.value = true; errorMessage.value = ''; successMessage.value = '';
  try {
    models.value = await getModelVersions();
    if (!models.value.some((item) => item.version === selectedVersion.value)) selectedVersion.value = models.value.find((item) => item.is_active)?.version ?? models.value[0]?.version ?? '';
  } catch (error) {
    errorMessage.value = error instanceof ApiError ? error.message : '模型版本加载失败，请稍后重试。';
  } finally { loading.value = false; }
}

async function activate(model: ModelVersionResponse) {
  if (model.is_active || activating.value) return;
  activating.value = model.version; errorMessage.value = ''; successMessage.value = '';
  try {
    await activateModelVersion(model.version);
    models.value = models.value.map((item) => ({ ...item, is_active: item.version === model.version }));
    successMessage.value = `已激活模型版本 ${model.version}`;
  } catch (error) {
    errorMessage.value = error instanceof ApiError ? error.message : '模型激活失败，请稍后重试。';
  } finally { activating.value = ''; }
}

onMounted(loadModels);
</script>

<template>
  <section :class="embedded ? 'settings-embedded-models' : 'page-content models-page'">
    <header v-if="!embedded" class="page-heading"><div><span class="eyebrow">模型管理</span><h1>模型版本与配置</h1><p>只读核对模型登记信息，并切换服务器已登记且检查点可用的版本</p></div><span class="api-state"><span></span>配置来源：模型登记表</span></header>
    <div v-if="errorMessage" class="alert error models-alert" role="alert"><AlertCircle :size="17" /><span>{{ errorMessage }}</span><button type="button" @click="loadModels"><RefreshCw :size="15" />重新加载</button></div>
    <div v-if="successMessage" class="alert success models-alert"><CheckCircle2 :size="17" />{{ successMessage }}</div>

    <div class="models-layout">
      <section class="models-list-panel">
        <div class="section-heading"><div><h2>已登记版本</h2><p>共 {{ models.length }} 个版本</p></div></div>
        <div v-if="loading" class="models-state"><span class="spinner dark"></span>正在加载模型版本…</div>
        <div v-else-if="!models.length" class="models-state">尚未登记模型版本</div>
        <button v-for="model in models" v-else :key="model.version" type="button" class="model-version-row" :class="{ selected: selected?.version === model.version }" @click="selectedVersion = model.version">
          <span class="model-icon"><Cpu :size="18" /></span><span><strong>{{ model.version }}</strong><small>{{ model.model_name }}</small></span><em v-if="model.is_active">当前使用</em>
        </button>
      </section>

      <main v-if="selected" class="model-detail-panel">
        <div class="model-detail-head"><div><span class="eyebrow">版本详情</span><h2>{{ selected.version }}</h2><p>{{ selected.model_name }}</p></div><button type="button" class="primary-button" :disabled="selected.is_active || Boolean(activating)" @click="activate(selected)">{{ selected.is_active ? '当前使用' : activating ? '激活中…' : '激活此版本' }}</button></div>
        <dl class="model-identity"><div><dt>Tokenizer</dt><dd>{{ selected.tokenizer_name }}</dd></div><div><dt>登记时间</dt><dd>{{ new Date(selected.created_at).toLocaleString('zh-CN') }}</dd></div><div class="span-2"><dt>检查点 SHA-256</dt><dd class="mono">{{ selected.checkpoint_sha256 }}</dd></div></dl>

        <section class="model-subsection"><div class="section-heading"><div><h2>运行配置</h2><p>由后端模型登记信息返回，页面只读展示</p></div></div><dl class="config-grid"><div v-for="([key, value]) in configEntries" :key="key"><dt class="mono">{{ key }}</dt><dd>{{ displayValue(value) }}</dd></div></dl></section>
        <section class="model-subsection metrics-state"><ShieldCheck :size="21" /><div><h2>评估指标</h2><template v-if="selected.metrics"><dl><div v-for="(value, key) in selected.metrics" :key="key"><dt>{{ key }}</dt><dd>{{ value }}</dd></div></dl></template><p v-else>当前版本没有可验证的历史指标快照。页面不会生成或补造准确率、F1、AUC 等指标。</p></div></section>
        <div class="model-boundary"><AlertCircle :size="17" /><p>激活操作只会切换后端已登记版本。真实环境若检查点文件不可用，后端会拒绝激活；请求不能指定任意服务器文件路径。</p></div>
      </main>
    </div>
  </section>
</template>
