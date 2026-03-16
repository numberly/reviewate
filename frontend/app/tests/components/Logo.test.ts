/**
 * Tests for Logo component
 */
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it } from 'vitest'

import Logo from '~/components/Logo.vue'

describe('Logo', () => {
  it('renders an SVG element', async () => {
    const wrapper = await mountSuspended(Logo)
    expect(wrapper.find('svg').exists()).toBe(true)
  })

  it('has the correct viewBox attribute', async () => {
    const wrapper = await mountSuspended(Logo)
    expect(wrapper.find('svg').attributes('viewBox')).toBe('0 0 24 24')
  })

  it('contains path elements for the logo shape', async () => {
    const wrapper = await mountSuspended(Logo)
    const paths = wrapper.findAll('path')
    expect(paths.length).toBe(27)
  })
})
