import { flushPromises, mount } from '@vue/test-utils';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../mocks/server';
import DetectionRecordsView from './DetectionRecordsView.vue';

async function settle() {
  await new Promise((resolve) => setTimeout(resolve, 25));
  await flushPromises();
}

describe('DetectionRecordsView', () => {
  it('loads the first page and enables pagination', async () => {
    const wrapper = mount(DetectionRecordsView);
    await settle();
    expect(wrapper.findAll('.records-table tbody tr')).toHaveLength(10);
    expect(wrapper.text()).toContain('共 26 条');
    expect(wrapper.text()).toContain('1 / 3');
    await wrapper.get('button[aria-label="下一页"]').trigger('click');
    await settle();
    expect(wrapper.text()).toContain('2 / 3');
    expect(wrapper.text()).toContain('显示 11–20');
  });

  it('links each record to its result detail', async () => {
    const wrapper = mount(DetectionRecordsView, {
      global: { stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } } },
    });
    await settle();
    expect(wrapper.get('a[href="/results/3001"]').attributes('href')).toBe('/results/3001');
  });

  it('shows the evidence heading when opened from the evidence navigation', async () => {
    window.history.pushState({}, '', '/results?mode=evidence');
    const wrapper = mount(DetectionRecordsView, { global: { stubs: { RouterLink: true } } });
    await settle();
    expect(wrapper.get('h1').text()).toBe('结果与证据');
    expect(wrapper.text()).toContain('选择一条检测记录');
    window.history.pushState({}, '', '/results');
  });

  it('filters by authenticity and action', async () => {
    const wrapper = mount(DetectionRecordsView);
    await settle();
    const selects = wrapper.findAll('.filter-field select');
    await selects[0].setValue('fake');
    await selects[1].setValue('block');
    await wrapper.get('button[type="submit"]').trigger('submit');
    await settle();
    const labels = wrapper.findAll('.authenticity-label');
    expect(labels.length).toBeGreaterThan(0);
    expect(labels.every((item) => item.text() === '疑似虚假')).toBe(true);
    expect(wrapper.findAll('.action-badge').every((item) => item.text() === '拦截')).toBe(true);
  });

  it('searches review content and shows an empty state', async () => {
    const wrapper = mount(DetectionRecordsView);
    await settle();
    await wrapper.get('.keyword-filter input').setValue('不存在的记录');
    await wrapper.get('button[type="submit"]').trigger('submit');
    await settle();
    expect(wrapper.text()).toContain('未找到检测记录');
    expect(wrapper.text()).toContain('共 0 条');
  });

  it('resets all filters', async () => {
    const wrapper = mount(DetectionRecordsView);
    await settle();
    await wrapper.get('.keyword-filter input').setValue('REV-202608-001');
    await wrapper.get('button[type="submit"]').trigger('submit');
    await settle();
    expect(wrapper.text()).toContain('共 1 条');
    await wrapper.get('button[type="button"]').trigger('click');
    await settle();
    expect(wrapper.text()).toContain('共 26 条');
  });

  it('shows and retries a network error', async () => {
    server.use(http.get('/api/v1/results', () => HttpResponse.error()));
    const wrapper = mount(DetectionRecordsView);
    await settle();
    expect(wrapper.text()).toContain('无法连接检测服务');
    expect(wrapper.text()).toContain('重新加载');
  });
});
