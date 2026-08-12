import { flushPromises, mount } from '@vue/test-utils';
import { HttpResponse, http } from 'msw';
import { createMemoryHistory, createRouter } from 'vue-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { server } from '../mocks/server';
import DetectionResultDetailView from './DetectionResultDetailView.vue';

async function mountDetail(resultId = 3001, page: 'summary' | 'evidence' = 'summary') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/results', component: { template: '<div />' } },
      { path: '/results/:resultId', component: DetectionResultDetailView },
    ],
  });
  await router.push(`/results/${resultId}?page=${page}`);
  await router.isReady();
  const wrapper = mount(DetectionResultDetailView, { global: { plugins: [router] } });
  await flushPromises();
  return wrapper;
}

describe('DetectionResultDetailView', () => {
  beforeEach(() => {
    const NativeURL = URL;
    class TestURL extends NativeURL {
      static createObjectURL = vi.fn(() => 'blob:test');
      static revokeObjectURL = vi.fn();
    }
    vi.stubGlobal('URL', TestURL);
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('renders fixed semantic and behavior label order with insufficient evidence', async () => {
    const wrapper = await mountDetail(3001, 'evidence');
    expect(wrapper.findAll('.semantic-scores .score-row').map((row) => row.text())).toEqual([
      '真实语义82%', '误导性8%', '夸张性6%', '广告性4%',
    ]);
    expect(wrapper.findAll('.behavior-scores .score-row').map((row) => row.text())).toEqual([
      '行为正常0%', '评论操纵0%', '群体操纵0%', '机器行为0%', '行为证据不足100%',
    ]);
    expect(wrapper.text()).toContain('该状态不能解释为用户行为正常');
    expect(wrapper.findAll('.disclaimer-section li')).toHaveLength(4);
  });

  it('does not invent evidence when Explanation is absent', async () => {
    const wrapper = await mountDetail(3005, 'evidence');
    expect(wrapper.text()).toContain('解释数据不可用');
    expect(wrapper.find('.semantic-scores').exists()).toBe(false);
  });

  it('creates a task report and downloads JSON and CSV', async () => {
    const wrapper = await mountDetail();
    await wrapper.get('.report-create button').trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain('报告已生成');
    const buttons = wrapper.findAll('.report-downloads button');
    await buttons[0].trigger('click');
    await flushPromises();
    await buttons[1].trigger('click');
    await flushPromises();
    expect(URL.createObjectURL).toHaveBeenCalledTimes(2);
    expect(HTMLAnchorElement.prototype.click).toHaveBeenCalledTimes(2);
  });

  it.each([
    [401, '登录状态已过期'],
    [503, '结果服务暂不可用'],
  ])('shows API error status %s', async (status, message) => {
    server.use(http.get('/api/v1/results/:resultId', () => HttpResponse.json({ detail: message }, { status })));
    const wrapper = await mountDetail();
    expect(wrapper.text()).toContain(message);
    expect(wrapper.text()).toContain('重新加载');
  });

  it('shows the dedicated 404 state', async () => {
    const wrapper = await mountDetail(9999);
    expect(wrapper.text()).toContain('未找到该检测结果');
  });

  it('keeps result content visible when report generation fails', async () => {
    server.use(http.post('/api/v1/reports', () => HttpResponse.json({ detail: '报告服务暂不可用' }, { status: 503 })));
    const wrapper = await mountDetail();
    await wrapper.get('.report-create button').trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain('报告服务暂不可用');
    expect(wrapper.text()).toContain('结果摘要');
  });

  it('splits existing modules between summary and evidence pages', async () => {
    const wrapper = await mountDetail();
    expect(wrapper.get('.detail-page-nav a.active').text()).toBe('结果概览');
    expect(wrapper.get('.summary-section').isVisible()).toBe(true);
    expect(wrapper.get('.metadata-section').isVisible()).toBe(true);
    expect(wrapper.get('.report-section').isVisible()).toBe(true);
    expect(wrapper.get('.disclaimer-section').isVisible()).toBe(true);
    expect(wrapper.get('.evidence-section').isVisible()).toBe(false);

    await wrapper.get('.detail-page-nav a:nth-child(2)').trigger('click');
    await flushPromises();
    expect(wrapper.get('.detail-page-nav a.active').text()).toBe('融合证据');
    expect(wrapper.get('.detail-layout').classes()).toContain('detail-page-evidence');
    expect(wrapper.findAll('.evidence-section').every((section) => section.attributes('style') !== 'display: none;')).toBe(true);
    expect(wrapper.get('.fusion-section').attributes('style')).not.toBe('display: none;');
    expect(wrapper.get('.summary-section').attributes('style')).toBe('display: none;');
    expect(wrapper.get('.detail-side').attributes('style')).toBe('display: none;');
  });
});
