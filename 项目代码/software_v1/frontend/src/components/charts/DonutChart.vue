<script setup lang="ts">
// 环形图：门控融合中语义与行为的权重
import { computed } from 'vue';
import { arcPath } from './geometry';

const props = defineProps<{ semantic: number; behavior: number }>();

const CX = 150, CY = 80, R = 62, START = -Math.PI / 2;
const total = computed(() => props.semantic + props.behavior || 1);
const split = computed(() => START + (2 * Math.PI * props.semantic) / total.value);
const semanticPath = computed(() => arcPath(CX, CY, R, START, split.value));
const behaviorPath = computed(() => arcPath(CX, CY, R, split.value, START + 2 * Math.PI - 0.0001));
const ratio = computed(() => `${(props.semantic * 100).toFixed(1)} : ${(props.behavior * 100).toFixed(1)}`);
</script>

<template>
  <svg class="donut" viewBox="0 0 300 160" role="img" :aria-label="`门控权重 语义:行为 ${ratio}`">
    <path class="semantic" :d="semanticPath" />
    <path class="behavior" :d="behaviorPath" />
    <text class="figure" :x="CX" :y="CY - 2" text-anchor="middle">{{ ratio }}</text>
    <text class="caption" :x="CX" :y="CY + 18" text-anchor="middle">语义 : 行为</text>
  </svg>
</template>

<style scoped>
.donut { display: block; width: 100%; max-width: 300px; margin: 0 auto; }
.semantic, .behavior { fill: none; stroke-width: 16; }
.semantic { stroke: var(--color-primary); }
.behavior { stroke: var(--color-behavior); }
.figure { fill: var(--color-text); font-size: 17px; font-weight: 700; font-variant-numeric: tabular-nums; }
.caption { fill: var(--color-text-muted); font-size: 12px; }
</style>
