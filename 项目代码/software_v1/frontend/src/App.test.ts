import { mount } from '@vue/test-utils';
import { createMemoryHistory, createRouter } from 'vue-router';
import { beforeEach, describe, expect, it } from 'vitest';
import App from './App.vue';

async function mountApp() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/overview', component: { template: '<div>overview</div>' } },
      { path: '/login', component: { template: '<div class="login-test-view">login</div>' }, meta: { layout: 'auth' } },
    ],
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

  it('uses the auth layout without business navigation on the login route', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/overview', component: { template: '<div>overview</div>' } },
        { path: '/login', component: { template: '<div class="login-test-view">login</div>' }, meta: { layout: 'auth' } },
      ],
    });
    await router.push('/login');
    await router.isReady();
    const wrapper = mount(App, { global: { plugins: [router] } });

    expect(wrapper.find('.auth-shell').exists()).toBe(true);
    expect(wrapper.find('.auth-header').text()).toContain('全域电商异常评论监测平台');
    expect(wrapper.find('.sidebar').exists()).toBe(false);
    expect(wrapper.find('.topbar').exists()).toBe(false);
    expect(wrapper.find('.login-test-view').exists()).toBe(true);
  });
});
