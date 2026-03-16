/**
 * Tests for RepoList component
 */
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it } from 'vitest'

import RepoList from '~/components/organizations/RepoList.vue'

describe('RepoList', () => {
  const mockRepositories = [
    {
      id: 'repo-1',
      name: 'frontend',
      external_repo_id: '123',
      web_url: 'https://github.com/org/frontend',
      provider: 'github',
      organization_id: 'org-1',
      created_at: '2024-01-01T00:00:00Z',
    },
    {
      id: 'repo-2',
      name: 'backend',
      external_repo_id: '456',
      web_url: 'https://gitlab.com/org/backend',
      provider: 'gitlab',
      organization_id: 'org-1',
      created_at: '2024-01-01T00:00:00Z',
    },
  ]

  it('renders repository list with count', async () => {
    const wrapper = await mountSuspended(RepoList, {
      props: {
        repositories: mockRepositories,
        selectedRepoId: null,
        hasSelectedRepo: false,
        isLoading: false,
      },
    })
    expect(wrapper.text()).toContain('organizations.repositories.title')
    expect(wrapper.text()).toContain('(2)')
  })

  it('renders repository names', async () => {
    const wrapper = await mountSuspended(RepoList, {
      props: {
        repositories: mockRepositories,
        selectedRepoId: null,
        hasSelectedRepo: false,
        isLoading: false,
      },
    })
    expect(wrapper.text()).toContain('frontend')
    expect(wrapper.text()).toContain('backend')
  })

  it('shows loading skeleton', async () => {
    const wrapper = await mountSuspended(RepoList, {
      props: {
        repositories: [],
        selectedRepoId: null,
        hasSelectedRepo: false,
        isLoading: true,
      },
    })
    // Should show skeleton items instead of spinner
    expect(wrapper.findAllComponents({ name: 'USkeleton' }).length).toBeGreaterThan(0)
  })

  it('shows empty state when no repositories', async () => {
    const wrapper = await mountSuspended(RepoList, {
      props: {
        repositories: [],
        selectedRepoId: null,
        hasSelectedRepo: false,
        isLoading: false,
      },
    })
    expect(wrapper.text()).toContain('organizations.repositories.noRepositories')
  })

  it('highlights selected repository', async () => {
    const wrapper = await mountSuspended(RepoList, {
      props: {
        repositories: mockRepositories,
        selectedRepoId: 'repo-1',
        hasSelectedRepo: true,
        isLoading: false,
      },
    })

    const selectedButton = wrapper.findAll('button').find((btn) =>
      btn.text().includes('frontend'),
    )
    expect(selectedButton?.classes()).toContain('bg-brand-50')
  })

  it('emits select when repository is clicked', async () => {
    const wrapper = await mountSuspended(RepoList, {
      props: {
        repositories: mockRepositories,
        selectedRepoId: null,
        hasSelectedRepo: false,
        isLoading: false,
      },
    })

    const repoButton = wrapper.findAll('button').find((btn) =>
      btn.text().includes('frontend'),
    )
    await repoButton?.trigger('click')

    expect(wrapper.emitted('select')).toBeTruthy()
    expect(wrapper.emitted('select')?.[0]).toEqual([mockRepositories[0]])
  })
})
