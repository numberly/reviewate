/**
 * Tests for PullRequestCard component
 */
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it } from 'vitest'

import PullRequestCard from '~/components/pull_requests/PullRequestCard.vue'
import type { UIPullRequest } from '~/types/pullRequest'

describe('PullRequestCard', () => {
  const mockPullRequest: UIPullRequest = {
    // API fields (from PullRequestListItem)
    id: 'pr-uuid-123',
    organization_id: 'org-uuid-456',
    repository_id: 'repo-uuid-789',
    pr_number: 1,
    external_pr_id: '12345',
    title: 'Add new feature',
    author: 'testuser',
    state: 'open',
    head_branch: 'feature-branch',
    base_branch: 'main',
    head_sha: 'da1560886d4f094c3e6c9ef40349f7d38b5d27d7',
    pr_url: 'https://github.com/org/repo/pull/1',
    created_at: '2024-01-15T10:00:00Z',
    updated_at: '2024-01-15T10:00:00Z',
    latest_execution_id: null,
    latest_execution_status: null,
    latest_execution_created_at: null,
    // UI-specific fields
    repository: 'org/repo',
    date: '2024-01-15',
    executionDisplay: {
      label: 'No review yet',
      color: 'neutral' as const,
    },
  }

  it('renders pull request title', async () => {
    const wrapper = await mountSuspended(PullRequestCard, {
      props: { pullRequest: mockPullRequest },
    })
    expect(wrapper.text()).toContain('Add new feature')
  })

  it('renders repository name', async () => {
    const wrapper = await mountSuspended(PullRequestCard, {
      props: { pullRequest: mockPullRequest },
    })
    expect(wrapper.text()).toContain('org/repo')
  })

  it('renders date', async () => {
    const wrapper = await mountSuspended(PullRequestCard, {
      props: { pullRequest: mockPullRequest },
    })
    expect(wrapper.text()).toContain('2024-01-15')
  })

  it('renders status badge', async () => {
    const wrapper = await mountSuspended(PullRequestCard, {
      props: { pullRequest: mockPullRequest },
    })
    expect(wrapper.text()).toContain('No review yet')
  })

  it('renders review button', async () => {
    const wrapper = await mountSuspended(PullRequestCard, {
      props: { pullRequest: mockPullRequest },
    })
    // Check for translated key or button existence
    const button = wrapper.findComponent({ name: 'AppButton' })
    expect(button.exists()).toBe(true)
  })

  it('wraps card in external link to PR URL', async () => {
    const wrapper = await mountSuspended(PullRequestCard, {
      props: { pullRequest: mockPullRequest },
    })

    const link = wrapper.find('a')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe('https://github.com/org/repo/pull/1')
    expect(link.attributes('target')).toBe('_blank')
  })
})
