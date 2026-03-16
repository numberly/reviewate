/**
 * Tests for OrgList component
 */
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it } from 'vitest'

import OrgList from '~/components/organizations/OrgList.vue'
import { createMockOrganization } from '~/tests/setup'

describe('OrgList', () => {
  const mockOrganizations = [
    createMockOrganization({ id: 'org-1', name: 'GitHub Org', installation_id: '12345', provider: 'github' }),
    createMockOrganization({ id: 'org-2', name: 'GitLab Org', installation_id: 'gitlab-token', provider: 'gitlab' }),
  ]

  describe('empty state', () => {
    it('shows empty state when hasOrganizations is false', async () => {
      const wrapper = await mountSuspended(OrgList, {
        props: {
          organizations: [],
          selectedOrgId: null,
          hasOrganizations: false,
        },
      })
      expect(wrapper.text()).toContain('organizations.noOrganizations')
    })

    it('shows description in empty state', async () => {
      const wrapper = await mountSuspended(OrgList, {
        props: {
          organizations: [],
          selectedOrgId: null,
          hasOrganizations: false,
        },
      })
      expect(wrapper.text()).toContain('organizations.noOrganizationsDescription')
    })

    it('shows add buttons in empty state', async () => {
      const wrapper = await mountSuspended(OrgList, {
        props: {
          organizations: [],
          selectedOrgId: null,
          hasOrganizations: false,
        },
      })
      expect(wrapper.text()).toContain('organizations.addFromGithub')
      expect(wrapper.text()).toContain('organizations.addFromGitlab')
    })
  })

  describe('with organizations', () => {
    it('renders the title', async () => {
      const wrapper = await mountSuspended(OrgList, {
        props: {
          organizations: mockOrganizations,
          selectedOrgId: null,
          hasOrganizations: true,
        },
      })
      expect(wrapper.text()).toContain('organizations.title')
    })

    it('renders organization names', async () => {
      const wrapper = await mountSuspended(OrgList, {
        props: {
          organizations: mockOrganizations,
          selectedOrgId: null,
          hasOrganizations: true,
        },
      })
      expect(wrapper.text()).toContain('GitHub Org')
      expect(wrapper.text()).toContain('GitLab Org')
    })

    it('shows organization initials', async () => {
      const wrapper = await mountSuspended(OrgList, {
        props: {
          organizations: mockOrganizations,
          selectedOrgId: null,
          hasOrganizations: true,
        },
      })
      expect(wrapper.text()).toContain('G') // First letter of GitHub Org and GitLab Org
    })

    it('renders buttons for each organization', async () => {
      const wrapper = await mountSuspended(OrgList, {
        props: {
          organizations: mockOrganizations,
          selectedOrgId: null,
          hasOrganizations: true,
        },
      })

      const orgButtons = wrapper.findAll('button').filter((btn) => {
        return btn.text().includes('GitHub Org') || btn.text().includes('GitLab Org')
      })
      expect(orgButtons.length).toBe(2)
    })
  })

  describe('selection', () => {
    it('applies selected styling to the selected organization', async () => {
      const wrapper = await mountSuspended(OrgList, {
        props: {
          organizations: mockOrganizations,
          selectedOrgId: 'org-1',
          hasOrganizations: true,
        },
      })

      const selectedButton = wrapper.findAll('button').find((btn) => {
        return btn.text().includes('GitHub Org')
      })

      expect(selectedButton?.classes()).toContain('bg-brand-50')
    })

    it('emits select event when clicking an organization', async () => {
      const wrapper = await mountSuspended(OrgList, {
        props: {
          organizations: mockOrganizations,
          selectedOrgId: null,
          hasOrganizations: true,
        },
      })

      const orgButton = wrapper.findAll('button').find((btn) => {
        return btn.text().includes('GitHub Org')
      })

      await orgButton?.trigger('click')
      expect(wrapper.emitted('select')).toBeTruthy()
      expect(wrapper.emitted('select')?.[0]).toEqual([mockOrganizations[0]])
    })
  })

  describe('add organization buttons', () => {
    it('shows add buttons at bottom when has organizations', async () => {
      const wrapper = await mountSuspended(OrgList, {
        props: {
          organizations: mockOrganizations,
          selectedOrgId: null,
          hasOrganizations: true,
        },
      })

      expect(wrapper.text()).toContain('GitHub')
      expect(wrapper.text()).toContain('GitLab')
    })

    it('emits addGithub when GitHub button is clicked', async () => {
      const wrapper = await mountSuspended(OrgList, {
        props: {
          organizations: mockOrganizations,
          selectedOrgId: null,
          hasOrganizations: true,
        },
      })

      const buttons = wrapper.findAll('button')
      const githubButton = buttons.find((btn) => {
        const text = btn.text()
        return text === 'GitHub' || text.includes('addFromGithub')
      })

      await githubButton?.trigger('click')
      expect(wrapper.emitted('addGithub')).toBeTruthy()
    })

    it('emits addGitlab when GitLab button is clicked', async () => {
      const wrapper = await mountSuspended(OrgList, {
        props: {
          organizations: mockOrganizations,
          selectedOrgId: null,
          hasOrganizations: true,
        },
      })

      const buttons = wrapper.findAll('button')
      const gitlabButton = buttons.find((btn) => {
        const text = btn.text()
        return text === 'GitLab' || text.includes('addFromGitlab')
      })

      await gitlabButton?.trigger('click')
      expect(wrapper.emitted('addGitlab')).toBeTruthy()
    })
  })

  describe('provider detection', () => {
    it('shows GitHub provider name for github provider', async () => {
      const wrapper = await mountSuspended(OrgList, {
        props: {
          organizations: [createMockOrganization({ provider: 'github' })],
          selectedOrgId: null,
          hasOrganizations: true,
        },
      })

      expect(wrapper.text()).toContain('GitHub')
    })

    it('shows GitLab provider name for gitlab provider', async () => {
      const wrapper = await mountSuspended(OrgList, {
        props: {
          organizations: [createMockOrganization({ provider: 'gitlab' })],
          selectedOrgId: null,
          hasOrganizations: true,
        },
      })

      expect(wrapper.text()).toContain('GitLab')
    })
  })
})
