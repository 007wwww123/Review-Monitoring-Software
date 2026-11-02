import { mount } from '@vue/test-utils';
import { createMemoryHistory, createRouter } from 'vue-router';
import { beforeEach, describe, expect, it } from 'vitest';
import App from './App.vue';
import { APP_NAME } from './brand';

async function mountApp(path = '/overview') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/overview', component: { template: '<div>overview</div>' } },
      { path: '/results/:id', component: { template: '<div>detail</div>' } },
      { path: '/login', component: { template: '<div class="login-test-view">login</div>' }, meta: { layout: 'auth' } },
    ],
  });
  await router.push(path);
  await router.isReady();
  return mount(App, { global: { plugins: [router] } });
}

describe('App sidebar', () => {
  beforeEach(() => localStorage.clear());

  it('collapses, expands and persists the sidebar state', async () => {
    const wrapper = await mountApp();
    const toggle = wrapper.get('.side-toggle');

    expect(wrapper.classes()).not.toContain('collapsed');
    expect(toggle.attributes('aria-label')).toBe('收起侧边栏');

    await toggle.trigger('click');
    expect(wrapper.classes()).toContain('collapsed');
    expect(toggle.attributes('aria-label')).toBe('展开侧边栏');
    expect(localStorage.getItem('review-monitoring.sidebar-collapsed')).toBe('true');

    await toggle.trigger('click');
    expect(wrapper.classes()).not.toContain('collapsed');
    expect(localStorage.getItem('review-monitoring.sidebar-collapsed')).toBe('false');
  });

  it('restores the collapsed state from local storage', async () => {
    localStorage.setItem('review-monitoring.sidebar-collapsed', 'true');
    const wrapper = await mountApp();
    expect(wrapper.classes()).toContain('collapsed');
  });

  it('keeps the records entry active on a result detail route', async () => {
    const wrapper = await mountApp('/results/28');
    expect(wrapper.get('.side-nav a.active').text()).toBe('检测记录');
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
    expect(wrapper.find('.auth-header').text()).toContain(APP_NAME);
    expect(wrapper.find('.side').exists()).toBe(false);
    expect(wrapper.find('.login-test-view').exists()).toBe(true);
  });
});
