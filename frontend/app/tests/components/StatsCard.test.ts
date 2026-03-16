/**
 * Tests for StatsCard component
 */
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it } from 'vitest'

import StatsCard from '~/components/StatsCard.vue'

describe('StatsCard', () => {
  const defaultProps = {
    label: 'Total Users',
    value: '1,234',
    change: '+12%',
    trend: 'up' as const,
  }

  it('renders the label', async () => {
    const wrapper = await mountSuspended(StatsCard, {
      props: defaultProps,
    })
    expect(wrapper.text()).toContain('Total Users')
  })

  it('renders the value', async () => {
    const wrapper = await mountSuspended(StatsCard, {
      props: defaultProps,
    })
    expect(wrapper.text()).toContain('1,234')
  })

  it('renders the change', async () => {
    const wrapper = await mountSuspended(StatsCard, {
      props: defaultProps,
    })
    expect(wrapper.text()).toContain('+12%')
  })

  it('has rounded-xl class', async () => {
    const wrapper = await mountSuspended(StatsCard, {
      props: defaultProps,
    })
    expect(wrapper.classes()).toContain('rounded-xl')
  })

  describe('trend styling', () => {
    it('applies success color classes for up trend', async () => {
      const wrapper = await mountSuspended(StatsCard, {
        props: { ...defaultProps, trend: 'up' },
      })
      const trendEl = wrapper.find('.text-success-600')
      expect(trendEl.exists()).toBe(true)
    })

    it('applies neutral color classes for down trend', async () => {
      const wrapper = await mountSuspended(StatsCard, {
        props: { ...defaultProps, trend: 'down' },
      })
      const trendEl = wrapper.find('.text-neutral-500')
      expect(trendEl.exists()).toBe(true)
    })
  })

  it('has group class for hover effects', async () => {
    const wrapper = await mountSuspended(StatsCard, {
      props: defaultProps,
    })
    expect(wrapper.classes()).toContain('group')
  })

  it('has cursor-pointer for interactivity', async () => {
    const wrapper = await mountSuspended(StatsCard, {
      props: defaultProps,
    })
    expect(wrapper.classes()).toContain('cursor-pointer')
  })
})
