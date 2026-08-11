import { flushPromises, mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
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

  it('selects another version but keeps online switching disabled', async () => {
    const wrapper = await mountView();
    await wrapper.findAll('.model-version-row')[1].trigger('click');
    expect(wrapper.text()).toContain('mock-v0.9.0');
    expect(wrapper.get('.model-detail-head button').attributes('disabled')).toBeDefined();
    expect(wrapper.get('.model-detail-head button').text()).toBe('需重启切换');
    expect(wrapper.text()).toContain('不支持在线热切换');
  });
});
