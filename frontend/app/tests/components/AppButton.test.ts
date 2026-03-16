/**
 * Tests for AppButton component
 */
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it } from 'vitest'
import { h } from 'vue'

import AppButton from '~/components/AppButton.vue'

describe('AppButton', () => {
  it('renders slot content', async () => {
    const wrapper = await mountSuspended(AppButton, {
      slots: {
        default: () => h('span', 'Click me'),
      },
    })
    expect(wrapper.text()).toContain('Click me')
  })

  it('emits click event when clicked', async () => {
    const wrapper = await mountSuspended(AppButton)
    await wrapper.find('button').trigger('click')
    expect(wrapper.emitted('click')).toBeTruthy()
  })

  it('disables button when processing is true', async () => {
    const wrapper = await mountSuspended(AppButton, {
      props: { processing: true },
    })
    expect(wrapper.find('button').attributes('disabled')).toBeDefined()
  })

  it('shows icon when provided', async () => {
    const wrapper = await mountSuspended(AppButton, {
      props: {
        icon: 'i-lucide-check',
        processing: false,
      },
    })
    // The icon should be present
    expect(wrapper.find('.iconify').exists()).toBe(true)
  })

  it('shows loading dots when processing', async () => {
    const wrapper = await mountSuspended(AppButton, {
      props: {
        processing: true,
      },
    })
    // Should show loading dots instead of content
    expect(wrapper.findAll('.animate-bounce-dot').length).toBe(3)
  })
})
