import { mount } from '@vue/test-utils';
import { createMemoryHistory, createRouter } from 'vue-router';
import { beforeEach, describe, expect, it } from 'vitest';
import App from './App.vue';

async function mountApp() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/overview', component: { template: '<div>overview</div>' } }],
  });
  await router.push('/overview');
  await router.isReady();
  return mount(App, { global: { plugins: [router] } });
}

describe('App sidebar', () => {
  beforeEach(() => localStorage.clear());

  it('collapses, expands and persists the sidebar state', async () => {
    const wrapper = await mountApp();
    const toggle = wrapper.get('.sidebar-toggle');

    expect(wrapper.classes()).not.toContain('sidebar-collapsed');
    expect(toggle.attributes('aria-label')).toBe('收起侧边栏');

    await toggle.trigger('click');
    expect(wrapper.classes()).toContain('sidebar-collapsed');
    expect(toggle.attributes('aria-label')).toBe('展开侧边栏');
    expect(localStorage.getItem('review-monitoring.sidebar-collapsed')).toBe('true');

    await toggle.trigger('click');
    expect(wrapper.classes()).not.toContain('sidebar-collapsed');
    expect(localStorage.getItem('review-monitoring.sidebar-collapsed')).toBe('false');
  });

  it('restores the collapsed state from local storage', async () => {
    localStorage.setItem('review-monitoring.sidebar-collapsed', 'true');
    const wrapper = await mountApp();
    expect(wrapper.classes()).toContain('sidebar-collapsed');
  });
});
