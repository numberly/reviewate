/**
 * Tests for CornerFrame component
 */
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it } from 'vitest'
import { h } from 'vue'

import CornerFrame from '~/components/CornerFrame.vue'

describe('CornerFrame', () => {
  it('renders slot content', async () => {
    const wrapper = await mountSuspended(CornerFrame, {
      slots: {
        default: () => h('span', 'Test Content'),
      },
    })
    expect(wrapper.text()).toContain('Test Content')
  })

  it('has rounded-xl class', async () => {
    const wrapper = await mountSuspended(CornerFrame)
    expect(wrapper.classes()).toContain('rounded-xl')
  })

  it('renders as a plain div wrapper', async () => {
    const wrapper = await mountSuspended(CornerFrame)
    expect(wrapper.element.tagName).toBe('DIV')
  })
})
