import { flushPromises, mount } from '@vue/test-utils';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../mocks/server';
import SystemOverviewView from './SystemOverviewView.vue';

const RouterLink = { props: ['to'], template: '<a :href="to"><slot /></a>' };

async function mountOverview() {
  const wrapper = mount(SystemOverviewView, { global: { stubs: { RouterLink } } });
  await flushPromises();
  return wrapper;
}

describe('SystemOverviewView', () => {
  it('renders sourced summary metrics and recent detail links', async () => {
    const wrapper = await mountOverview();
    expect(wrapper.text()).toContain('检测服务正常');
    expect(wrapper.text()).toContain('检测记录总数26');
    expect(wrapper.text()).toContain('统计口径：当前加载的最近 100 条记录');
    expect(wrapper.findAll('.recent-item')).toHaveLength(5);
    expect(wrapper.get('a[href="/results/3001"]').attributes('href')).toBe('/results/3001');
  });

  it('provides both detection shortcuts', async () => {
    const wrapper = await mountOverview();
    expect(wrapper.get('a[href="/detections/single"]').text()).toContain('单条评论检测');
    expect(wrapper.get('a[href="/detections/batch"]').text()).toContain('批量检测任务');
  });

  it('shows a retryable error when the service is unavailable', async () => {
    server.use(http.get('/api/v1/health', () => HttpResponse.json({ detail: '服务暂不可用' }, { status: 503 })));
    const wrapper = await mountOverview();
    expect(wrapper.text()).toContain('服务暂不可用');
    expect(wrapper.text()).toContain('检测服务不可用');
    expect(wrapper.text()).toContain('重新加载');
  });
});
