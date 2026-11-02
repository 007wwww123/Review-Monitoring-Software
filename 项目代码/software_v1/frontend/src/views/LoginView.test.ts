import { flushPromises, mount, type VueWrapper } from '@vue/test-utils';
import { HttpResponse, delay, http } from 'msw';
import { createMemoryHistory, createRouter } from 'vue-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { server } from '../mocks/server';
import LoginView from './LoginView.vue';

async function mountLogin(redirect?: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', component: LoginView },
      { path: '/overview', component: { template: '<div>overview</div>' } },
      { path: '/results', component: { template: '<div>results</div>' } },
    ],
  });
  await router.push({ path: '/login', query: redirect ? { redirect } : {} });
  await router.isReady();
  const wrapper = mount(LoginView, { global: { plugins: [router] } });
  return { wrapper, router };
}

async function fillCredentials(wrapper: VueWrapper) {
  await wrapper.get('input[autocomplete="username"]').setValue('admin');
  await wrapper.get('input[autocomplete="current-password"]').setValue('demo');
}

describe('LoginView', () => {
  beforeEach(() => localStorage.clear());

  it('requires both credentials and defaults successful login to overview', async () => {
    const { wrapper, router } = await mountLogin();
    expect(wrapper.get('input[autocomplete="username"]').attributes('required')).toBeDefined();
    expect(wrapper.get('input[autocomplete="current-password"]').attributes('required')).toBeDefined();
    await fillCredentials(wrapper);
    await wrapper.get('form').trigger('submit');
    await flushPromises();
    expect(router.currentRoute.value.fullPath).toBe('/overview');
  });

  it('returns to the originally requested internal page', async () => {
    const { wrapper, router } = await mountLogin('/results');
    await fillCredentials(wrapper);
    await wrapper.get('form').trigger('submit');
    await flushPromises();
    expect(router.currentRoute.value.fullPath).toBe('/results');
  });

  it('shows the server error and allows another submission', async () => {
    const { wrapper } = await mountLogin();
    await wrapper.get('input[autocomplete="username"]').setValue('admin');
    await wrapper.get('input[autocomplete="current-password"]').setValue('wrong');
    await wrapper.get('form').trigger('submit');
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toContain('用户名或密码错误');
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeUndefined();
  });

  it('shows a loading state and blocks duplicate submissions', async () => {
    const requests = vi.fn();
    server.use(http.post('/api/v1/auth/login', async () => {
      requests();
      await delay(60);
      return HttpResponse.json({ user_id: 1, username: 'admin', role: 'admin', access_token: 'token', token_type: 'bearer', expires_at: new Date(Date.now() + 1800000).toISOString() });
    }));
    const { wrapper } = await mountLogin();
    await fillCredentials(wrapper);
    await wrapper.get('form').trigger('submit');
    await wrapper.get('form').trigger('submit');
    expect(wrapper.get('button[type="submit"]').text()).toBe('登录中');
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined();
    await delay(80);
    await flushPromises();
    expect(requests).toHaveBeenCalledTimes(1);
  });
});
