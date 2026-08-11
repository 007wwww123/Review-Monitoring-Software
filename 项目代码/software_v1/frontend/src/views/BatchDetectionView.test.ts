import { flushPromises, mount, type VueWrapper } from '@vue/test-utils';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../mocks/server';
import BatchDetectionView from './BatchDetectionView.vue';

const csv = 'review_id,user_id,prod_id,rating,date,text\nREV-1,USER-1,PROD-1,5,2026-08-11T10:00:00+08:00,商品与描述一致';

async function upload(wrapper: VueWrapper, content = csv, name = 'reviews.csv') {
  const input = wrapper.get('[data-testid="file-input"]');
  const file = new File([content], name, { type: 'text/csv' });
  Object.defineProperty(file, 'text', { value: () => Promise.resolve(content) });
  Object.defineProperty(input.element, 'files', { configurable: true, value: [file] });
  await input.trigger('change');
  await flushPromises();
}

async function settleTask() {
  await new Promise((resolve) => setTimeout(resolve, 50));
  await flushPromises();
}

describe('BatchDetectionView', () => {
  it('imports a file, exposes a template, and renders editable rows', async () => {
    const wrapper = mount(BatchDetectionView);
    expect(wrapper.get('a[download="batch-review-template.csv"]').attributes('href')).toBe('/batch-review-template.csv');
    await upload(wrapper);
    expect(wrapper.text()).toContain('reviews.csv');
    expect(wrapper.text()).toContain('1 条评论');
    expect(wrapper.findAll('.batch-table tbody input')).toHaveLength(6);
    expect(wrapper.get('[data-testid="batch-submit"]').attributes('disabled')).toBeUndefined();
  });

  it('blocks invalid rows and allows removing them', async () => {
    const wrapper = mount(BatchDetectionView);
    await upload(wrapper, 'review_id,user_id,prod_id,rating,date,text\nR-1,,P-1,8,bad,');
    expect(wrapper.text()).toContain('存在 1 条错误数据');
    expect(wrapper.get('[data-testid="batch-submit"]').attributes('disabled')).toBeDefined();
    await wrapper.get('button[aria-label="删除第 2 行"]').trigger('click');
    expect(wrapper.text()).toContain('选择 CSV / TSV 文件');
  });

  it('submits once, polls, and renders a successful task summary', async () => {
    const wrapper = mount(BatchDetectionView);
    await upload(wrapper);
    const submit = wrapper.get('[data-testid="batch-submit"]');
    await submit.trigger('click');
    expect(submit.attributes('disabled')).toBeDefined();
    await submit.trigger('click');
    await settleTask();
    expect(wrapper.text()).toContain('已完成');
    expect(wrapper.text()).toContain('全部评论处理完成');
    expect(wrapper.text()).toContain('1 / 1');
  });

  it('renders partial failure counts from the task API', async () => {
    const wrapper = mount(BatchDetectionView);
    const partial = `${csv}\nREV-2,USER-2,PROD-2,4,2026-08-11T11:00:00+08:00,[partial]`;
    await upload(wrapper, partial);
    await wrapper.get('[data-testid="batch-submit"]').trigger('click');
    await settleTask();
    expect(wrapper.text()).toContain('处理成功1');
    expect(wrapper.text()).toContain('处理失败1');
    expect(wrapper.text()).toContain('模拟单条处理失败');
  });

  it('shows a 503 detail returned by FastAPI', async () => {
    const wrapper = mount(BatchDetectionView);
    await upload(wrapper, csv.replace('商品与描述一致', '[503]'));
    await wrapper.get('[data-testid="batch-submit"]').trigger('click');
    await settleTask();
    expect(wrapper.text()).toContain('批量模型服务暂不可用（模拟）');
  });

  it('shows a connection message for network failures', async () => {
    server.use(http.post('/api/v1/detections/batch', () => HttpResponse.error()));
    const wrapper = mount(BatchDetectionView);
    await upload(wrapper);
    await wrapper.get('[data-testid="batch-submit"]').trigger('click');
    await settleTask();
    expect(wrapper.text()).toContain('无法连接检测服务');
  });
});
