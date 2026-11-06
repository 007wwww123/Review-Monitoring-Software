<script setup lang="ts">
// 页面卡片：标题 + 可选说明，右上角放标签或操作（extra 插槽）
defineProps<{ title?: string; subtitle?: string }>();
</script>

<template>
  <section class="app-card">
    <header v-if="title" class="card-head">
      <div class="card-title">
        <h2>{{ title }}</h2>
        <p v-if="subtitle" class="card-sub">{{ subtitle }}</p>
      </div>
      <div v-if="$slots.extra" class="card-extra"><slot name="extra" /></div>
    </header>
    <slot />
  </section>
</template>

<style scoped>
.app-card { padding: 20px; border-radius: var(--radius-card); background: var(--color-surface); box-shadow: var(--shadow-card); }
.card-head { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 16px; }
.card-title { min-width: 0; }
.card-head h2 { margin: 0; font-size: 16px; font-weight: 600; line-height: 24px; }
.card-sub { margin: 2px 0 0; color: var(--color-text-muted); font-size: 12px; line-height: 18px; }
.card-extra { display: flex; flex: none; align-items: center; gap: 8px; margin-left: auto; }
</style>
