<script setup lang="ts">
// 半圆仪表：显示融合虚假概率；接口给了判定阈值时画出阈值刻度
import { computed } from 'vue';
import { percent } from '../../labels';
import { arcPath, polar } from './geometry';

const props = defineProps<{ value: number; threshold?: number; tone: 'fake' | 'real'; label: string }>();

const CX = 130, CY = 140, R = 100, WIDTH = 18;
const toAngle = (ratio: number) => Math.PI * (1 + Math.min(Math.max(ratio, 0), 1));
const trackPath = arcPath(CX, CY, R, Math.PI, 2 * Math.PI);
const valuePath = computed(() => arcPath(CX, CY, R, Math.PI, toAngle(props.value)));
const tick = computed(() => {
  if (props.threshold === undefined) return null;
  const angle = toAngle(props.threshold);
  const inner = R - WIDTH / 2 - 4, outer = R + WIDTH / 2 + 4;
  return { from: polar(CX, CY, inner, angle), to: polar(CX, CY, outer, angle), text: polar(CX, CY, outer + 4, angle) };
});
</script>

<template>
  <svg class="gauge" :class="tone" viewBox="0 0 260 156" role="img" :aria-label="`${label} ${percent(value)}`">
    <path class="track" :d="trackPath" />
    <path class="value" :d="valuePath" />
    <template v-if="tick && threshold !== undefined">
      <line class="tick" :x1="tick.from[0]" :y1="tick.from[1]" :x2="tick.to[0]" :y2="tick.to[1]" />
      <text class="tick-label" :x="tick.text[0]" :y="tick.text[1]" text-anchor="middle">阈值 {{ percent(threshold, 0) }}</text>
    </template>
    <text class="figure" :x="CX" :y="CY - 26" text-anchor="middle">{{ percent(value) }}</text>
    <text class="caption" :x="CX" :y="CY - 4" text-anchor="middle">{{ label }}</text>
  </svg>
</template>

<style scoped>
.gauge { display: block; width: 100%; max-width: 260px; margin: 0 auto; }
.track, .value { fill: none; stroke-width: 18; stroke-linecap: round; }
.track { stroke: var(--color-track); }
.fake .value { stroke: var(--color-fake); }
.real .value { stroke: var(--color-primary); }
.tick { stroke: var(--color-text-muted); stroke-width: 1.5; stroke-dasharray: 3 3; }
.tick-label { fill: var(--color-text-muted); font-size: 11px; }
.figure { fill: var(--color-text); font-size: 40px; font-weight: 700; font-variant-numeric: tabular-nums; }
.caption { fill: var(--color-text-muted); font-size: 12px; }
</style>
