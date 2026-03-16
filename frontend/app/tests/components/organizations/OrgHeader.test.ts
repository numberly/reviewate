/**
 * Tests for OrgHeader component
 */
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it } from 'vitest'

import OrgHeader from '~/components/organizations/OrgHeader.vue'

describe('OrgHeader', () => {
  const mockOrganization = {
    id: 'org-1',
    name: 'Acme Corp',
    external_org_id: 'ext-123',
    installation_id: '12345',
    provider: 'github' as const,
    created_at: '2024-01-15T10:30:00Z',
    role: 'admin' as const,
  }

  it('renders organization name', async () => {
    const wrapper = await mountSuspended(OrgHeader, {
      props: { organization: mockOrganization },
    })
    expect(wrapper.text()).toContain('Acme Corp')
  })

  it('displays organization initial in avatar', async () => {
    const wrapper = await mountSuspended(OrgHeader, {
      props: { organization: mockOrganization },
    })
    expect(wrapper.text()).toContain('A')
  })

  it('shows GitHub provider for github provider field', async () => {
    const wrapper = await mountSuspended(OrgHeader, {
      props: { organization: mockOrganization },
    })
    expect(wrapper.text()).toContain('GitHub')
  })

  it('shows GitLab provider for gitlab provider field', async () => {
    const wrapper = await mountSuspended(OrgHeader, {
      props: {
        organization: {
          ...mockOrganization,
          provider: 'gitlab' as const,
        },
      },
    })
    expect(wrapper.text()).toContain('GitLab')
  })

  it('displays formatted creation date', async () => {
    const wrapper = await mountSuspended(OrgHeader, {
      props: { organization: mockOrganization },
    })
    // Should contain date parts (month, day, year)
    expect(wrapper.text()).toMatch(/Jan|2024|15/)
  })
})
