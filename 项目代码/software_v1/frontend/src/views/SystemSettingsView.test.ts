import { flushPromises, mount } from '@vue/test-utils';
import { HttpResponse, http } from 'msw';
import { createMemoryHistory, createRouter } from 'vue-router';
import { beforeEach, describe, expect, it } from 'vitest';
import { server } from '../mocks/server';
import SystemSettingsView from './SystemSettingsView.vue';

async function mountView(hash = '') {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/settings', component: SystemSettingsView }, { path: '/login', component: { template: '<div>login</div>' } }] });
  await router.push(`/settings${hash}`); await router.isReady();
  const wrapper = mount(SystemSettingsView, { global: { plugins: [router] } }); await flushPromises();
  return { wrapper, router };
}

describe('SystemSettingsView', () => {
  beforeEach(() => localStorage.clear());

  it('loads account, model and clearly marked evaluation history', async () => {
    const { wrapper } = await mountView();
    expect(wrapper.text()).toContain('系统管理员');
    expect(wrapper.text()).toContain('模型版本与配置');
    expect(wrapper.text()).toContain('模拟联调数据，不代表真实模型性能');
    expect(wrapper.text()).toContain('88.4%');
    expect(wrapper.find('.matrix-wrap').exists()).toBe(true);
    expect(wrapper.get('#evaluations button[disabled]').text()).toBe('发起评估');
  });

  it('creates a reviewer account as an administrator', async () => {
    const { wrapper } = await mountView();
    const form = wrapper.get('.user-create-form');
    const inputs = form.findAll('input');
    await inputs[0].setValue('new-reviewer'); await inputs[1].setValue('新审核员'); await inputs[2].setValue('initial-password');
    await form.trigger('submit'); await flushPromises();
    expect(wrapper.text()).toContain('账号 new-reviewer 已创建');
  });

  it('persists theme and density preferences', async () => {
    const { wrapper } = await mountView();
    const selects = wrapper.findAll('#appearance select');
    await selects[0].setValue('dark'); await selects[1].setValue('compact');
    await wrapper.get('#appearance button').trigger('click');
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(document.documentElement.dataset.density).toBe('compact');
    expect(localStorage.getItem('review-monitoring.theme')).toBe('dark');
  });

  it('shows nullable metrics without replacing them with zero', async () => {
    const { wrapper } = await mountView();
    await wrapper.findAll('.evaluation-list button')[1].trigger('click'); await flushPromises();
    expect(wrapper.findAll('.metric-grid strong').every((item) => item.text() === '指标不可用')).toBe(true);
    expect(wrapper.text()).toContain('当前混淆矩阵结构无法展示');
  });

  it('hides user creation from non-admin users', async () => {
    server.use(http.get('/api/v1/auth/me', () => HttpResponse.json({ user_id: 2, username: 'reviewer', display_name: null, role: 'reviewer', status: 'active', last_login_at: null })));
    const { wrapper } = await mountView();
    expect(wrapper.find('#users').exists()).toBe(false);
  });

  it('keeps model settings usable when evaluation loading fails', async () => {
    server.use(http.get('/api/v1/evaluations', () => HttpResponse.json({ detail: '评估服务暂不可用' }, { status: 503 })));
    const { wrapper } = await mountView();
    expect(wrapper.text()).toContain('评估服务暂不可用');
    expect(wrapper.text()).toContain('mock-v1.0.0');
  });

  it('routes between settings sections even when account loading fails', async () => {
    server.use(http.get('/api/v1/auth/me', () => HttpResponse.json({ detail: '账户服务暂不可用' }, { status: 500 })));
    const { wrapper, router } = await mountView('#appearance');
    expect(wrapper.get('.settings-anchor-nav a.active').text()).toBe('界面');
    expect(wrapper.get('.settings-main').classes()).toContain('section-appearance');
    expect(wrapper.find('.settings-message.alert.error').exists()).toBe(false);

    await router.push('/settings#models'); await flushPromises();
    expect(wrapper.get('.settings-anchor-nav a.active').text()).toBe('模型');
    expect(wrapper.get('.settings-main').classes()).toContain('section-models');
  });
});
