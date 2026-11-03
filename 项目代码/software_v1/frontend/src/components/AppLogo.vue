<template>
  <span class="app-logo" aria-hidden="true"></span>
</template>

<style scoped>
/* 深青底 + 靛紫横条 + 浅青圆点：三种主色各占一处 */
.app-logo { position: relative; display: block; flex: none; width: 34px; height: 34px; border-radius: 10px; background: var(--color-brand-deep); }
.app-logo::before { position: absolute; right: 8px; bottom: 9px; left: 8px; height: 4px; border-radius: 2px; background: var(--color-behavior); content: ""; }
.app-logo::after { position: absolute; top: 8px; right: 8px; width: 7px; height: 7px; border-radius: 50%; background: var(--color-accent); content: ""; }
</style>
