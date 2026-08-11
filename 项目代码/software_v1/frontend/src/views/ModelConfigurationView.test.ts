import { flushPromises, mount } from '@vue/test-utils';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../mocks/server';
import ModelConfigurationView from './ModelConfigurationView.vue';

async function mountView() { const wrapper = mount(ModelConfigurationView); await flushPromises(); return wrapper; }

describe('ModelConfigurationView', () => {
  it('shows registered versions, fixed configuration and missing metrics boundary', async () => {
    const wrapper = await mountView();
    expect(wrapper.findAll('.model-version-row')).toHaveLength(2);
    expect(wrapper.text()).toContain('mock-v1.0.0');
    expect(wrapper.text()).toContain('behavior_input_size');
    expect(wrapper.text()).toContain('real → misleading → exaggerated → advertising');
    expect(wrapper.text()).toContain('不会生成或补造准确率、F1、AUC');
  });

  it('selects and activates another registered version', async () => {
    const wrapper = await mountView();
    await wrapper.findAll('.model-version-row')[1].trigger('click');
    expect(wrapper.text()).toContain('mock-v0.9.0');
    await wrapper.get('.model-detail-head button').trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain('已激活模型版本 mock-v0.9.0');
    expect(wrapper.get('.model-detail-head button').text()).toBe('当前使用');
  });

  it('shows backend activation rejection without changing the selected version', async () => {
    server.use(http.post('/api/v1/models/:version/activate', () => HttpResponse.json({ detail: 'checkpoint is unavailable' }, { status: 409 })));
    const wrapper = await mountView();
    await wrapper.findAll('.model-version-row')[1].trigger('click');
    await wrapper.get('.model-detail-head button').trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain('checkpoint is unavailable');
    expect(wrapper.get('.model-detail-head button').text()).toBe('激活此版本');
  });
});
