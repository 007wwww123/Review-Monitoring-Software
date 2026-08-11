import { flushPromises, mount, type VueWrapper } from '@vue/test-utils';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../mocks/server';
import SingleDetectionView from './SingleDetectionView.vue';

function fields(wrapper: VueWrapper) {
  const inputs = wrapper.findAll('.form-grid input');
  return {
    reviewId: inputs[0],
    userId: inputs[1],
    productId: inputs[2],
    rating: inputs[3],
    date: inputs[4],
    text: wrapper.find('.form-grid textarea'),
  };
}

async function fillValidForm(wrapper: VueWrapper, text = '配送及时，商品与描述一致。') {
  const form = fields(wrapper);
  await form.userId.setValue('anonymous-user-01');
  await form.productId.setValue('product-01');
  await form.date.setValue('2026-08-11T10:00');
  await form.text.setValue(text);
}

async function settleRequest() {
  await new Promise((resolve) => setTimeout(resolve, 30));
  await flushPromises();
}

describe('SingleDetectionView', () => {
  it('validates required fields before submission', async () => {
    const wrapper = mount(SingleDetectionView);
    await wrapper.get('[data-testid="submit"]').trigger('submit');
    expect(wrapper.text()).toContain('请检查表单中的');
    expect(wrapper.text()).toContain('请输入用户 ID');
    expect(wrapper.text()).toContain('请输入评论文本');
  });

  it('collects raw history and rejects non-past history', async () => {
    const wrapper = mount(SingleDetectionView);
    await fillValidForm(wrapper);
    await wrapper.get('[data-testid="add-history"]').trigger('click');
    const historyInputs = wrapper.findAll('.history-base input');
    await historyInputs[1].setValue('historical-product');
    await historyInputs[3].setValue('2026-08-11T10:00');
    await wrapper.get('[data-testid="submit"]').trigger('submit');
    expect(wrapper.text()).toContain('历史时间必须早于目标评论');
  });

  it('submits once and renders insufficient evidence without history', async () => {
    const wrapper = mount(SingleDetectionView);
    await fillValidForm(wrapper);
    const submit = wrapper.get('[data-testid="submit"]');
    await submit.trigger('submit');
    expect(submit.attributes('disabled')).toBeDefined();
    await submit.trigger('submit');
    await settleRequest();
    expect(wrapper.text()).toContain('真实');
    expect(wrapper.text()).toContain('行为证据不足');
    expect(wrapper.text()).toContain('未提供可用历史，该状态不表示用户行为正常');
    expect(submit.attributes('disabled')).toBeUndefined();
  });

  it('submits raw behavior history and renders the history response', async () => {
    let receivedProductId = '';
    server.use(http.post('/api/v1/detections/single', async ({ request }) => {
      const body = await request.json() as { behavior_history: Array<{ prod_id: string }> };
      receivedProductId = body.behavior_history[0].prod_id;
      return HttpResponse.json({
        task: { task_id: 'e26a484e-7347-4c74-b343-111111111111', status: 'succeeded', created_at: '2026-08-11T10:00:00Z' },
        result: { result_id: 3, authenticity: 'fake', confidence: 0.86, semantic_type: 'misleading', behavior_type: 'review_manipulation', risk_source: 'language_behavior_composite', action: 'review', model_version: 'mock-v1.0.0' },
      }, { status: 202 });
    }));
    const wrapper = mount(SingleDetectionView);
    await fillValidForm(wrapper);
    await wrapper.get('[data-testid="add-history"]').trigger('click');
    const historyInputs = wrapper.findAll('.history-base input');
    await historyInputs[1].setValue('historical-product');
    await historyInputs[3].setValue('2026-08-10T10:00');
    await wrapper.get('[data-testid="submit"]').trigger('submit');
    await settleRequest();
    expect(receivedProductId).toBe('historical-product');
    expect(wrapper.text()).toContain('疑似虚假');
    expect(wrapper.text()).toContain('评论操纵');
  });

  it('shows FastAPI 422 and 503 details', async () => {
    const wrapper = mount(SingleDetectionView);
    await fillValidForm(wrapper, '[422]');
    await wrapper.get('[data-testid="submit"]').trigger('submit');
    await settleRequest();
    expect(wrapper.text()).toContain('评论文本触发模拟校验错误');
    await fields(wrapper).text.setValue('[503]');
    await wrapper.get('[data-testid="submit"]').trigger('submit');
    await settleRequest();
    expect(wrapper.text()).toContain('模型服务暂不可用（模拟）');
  });

  it('shows a connection message for network failures', async () => {
    server.use(http.post('/api/v1/detections/single', () => HttpResponse.error()));
    const wrapper = mount(SingleDetectionView);
    await fillValidForm(wrapper);
    await wrapper.get('[data-testid="submit"]').trigger('submit');
    await settleRequest();
    expect(wrapper.text()).toContain('无法连接检测服务');
  });
});
