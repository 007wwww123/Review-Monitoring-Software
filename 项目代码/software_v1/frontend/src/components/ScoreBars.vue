<script setup lang="ts">
// 横向分数条：value 为 0–1 的占比。默认显示百分比，传 text 可改显示内容（如条数）；
// 传单项 tone 时该条用实色，否则按整组 tone 显示、selected 高亮
import { percent } from '../labels';

type Tone = 'primary' | 'behavior' | 'fake' | 'warn' | 'success' | 'cyan' | 'neutral';
defineProps<{ items: { key: string; label: string; value: number; text?: string; tone?: Tone }[]; selected?: string; tone?: Tone }>();
</script>

<template>
  <div class="score-bars" :class="tone">
    <div v-for="item in items" :key="item.key" class="score-row" :class="{ selected: item.key === selected }">
      <span class="label">{{ item.label }}</span>
      <span class="track"><i :class="item.tone ? `solid ${item.tone}` : ''" :style="{ width: percent(item.value) }"></i></span>
      <span class="value num">{{ item.text ?? percent(item.value) }}</span>
    </div>
  </div>
</template>

<style scoped>
.score-bars { display: flex; flex-direction: column; gap: 14px; }
.score-row { display: grid; grid-template-columns: 84px 1fr 56px; gap: 12px; align-items: center; font-size: 13px; }
.label { color: var(--color-text-secondary); }
.track { height: 8px; overflow: hidden; border-radius: 4px; background: var(--color-track); }
.track i { display: block; height: 100%; border-radius: 4px; background: var(--color-primary-soft-2); }
.primary .selected .track i { background: var(--color-primary); }
.behavior .track i { background: color-mix(in srgb, var(--color-behavior) 30%, var(--color-mix-base)); }
.behavior .selected .track i { background: var(--color-behavior); }
.track i.solid.primary { background: var(--color-primary); }
.track i.solid.behavior { background: var(--color-behavior); }
.track i.solid.fake { background: var(--color-fake); }
.track i.solid.warn { background: var(--color-warn); }
.track i.solid.success { background: var(--color-success); }
.track i.solid.cyan { background: var(--color-cyan); }
.track i.solid.neutral { background: var(--color-line-strong); }
.selected .label { color: var(--color-text); font-weight: 600; }
.value { color: var(--color-text-muted); text-align: right; }
.selected .value { color: var(--color-text); font-weight: 600; }
</style>
