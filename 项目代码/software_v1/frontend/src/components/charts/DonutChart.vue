<script setup lang="ts">
// 环形图：按顺序画出各段占比，中间显示一行大字和一行说明
import { computed } from 'vue';
import { arcPath } from './geometry';

export type DonutTone = 'primary' | 'behavior' | 'fake' | 'warn' | 'accent' | 'neutral';
const props = defineProps<{ parts: { key: string; label: string; value: number; tone: DonutTone }[]; center: string; caption: string }>();

const CX = 150, CY = 80, R = 62, START = -Math.PI / 2;
const segments = computed(() => {
  const total = props.parts.reduce((sum, part) => sum + Math.max(part.value, 0), 0);
  if (!total) return [];
  let angle = START;
  return props.parts.filter((part) => part.value > 0).map((part) => {
    const sweep = (2 * Math.PI * part.value) / total;
    // 整圈时终点与起点重合会画不出来，留一点点缝
    const path = arcPath(CX, CY, R, angle, angle + Math.min(sweep, 2 * Math.PI - 0.0001));
    angle += sweep;
    return { key: part.key, tone: part.tone, path };
  });
});
</script>

<template>
  <svg class="donut" viewBox="0 0 300 160" role="img" :aria-label="`${caption} ${center}`">
    <circle class="track" :cx="CX" :cy="CY" :r="R" />
    <path v-for="segment in segments" :key="segment.key" :class="segment.tone" :d="segment.path" />
    <text class="figure" :x="CX" :y="CY - 2" text-anchor="middle">{{ center }}</text>
    <text class="caption" :x="CX" :y="CY + 18" text-anchor="middle">{{ caption }}</text>
  </svg>
</template>

<style scoped>
.donut { display: block; width: 100%; max-width: 300px; margin: 0 auto; }
.track, path { fill: none; stroke-width: 16; }
.track { stroke: var(--color-track); }
.primary { stroke: var(--color-primary); }
.behavior { stroke: var(--color-behavior); }
.fake { stroke: var(--color-fake); }
.warn { stroke: var(--color-warn); }
.accent { stroke: var(--color-accent); }
.neutral { stroke: #c9cedd; }
.figure { fill: var(--color-text); font-size: 17px; font-weight: 700; font-variant-numeric: tabular-nums; }
.caption { fill: var(--color-text-muted); font-size: 12px; }
</style>
