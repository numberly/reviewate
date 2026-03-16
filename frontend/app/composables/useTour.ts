import type { MemberListItem, OrganizationListItem, RepositoryListItem } from '@reviewate/api-types'
import { updateProfile } from '@reviewate/api-types'
import type { DriveStep, Driver } from 'driver.js'

import type { UIPullRequest } from '~/types/pullRequest'

const TOTAL_STEPS = 9

// Cross-page navigation needs a transient client-side flag
let pendingNavStep: number | null = null
let activeDriver: Driver | null = null

// Shared reactive state — components read this to show demo data
const isTourActive = ref(false)
const demoActiveTab = ref('general')

// Demo data shown during the tour
const DEMO_PRS: UIPullRequest[] = [
  {
    id: 'demo-1',
    organization_id: 'demo-org',
    repository_id: 'demo-repo',
    pr_number: 142,
    external_pr_id: '142',
    title: 'feat: add user authentication with OAuth2',
    author: 'alice',
    state: 'open',
    head_branch: 'feat/oauth2-auth',
    base_branch: 'main',
    head_sha: 'abc123',
    pr_url: '#',
    created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    updated_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
    latest_execution_status: 'completed',
    latest_execution_id: 'demo-exec-1',
    repository: 'acme/backend',
    date: '2h ago',
    executionDisplay: { label: 'Completed', color: 'success' },
  },
  {
    id: 'demo-2',
    organization_id: 'demo-org',
    repository_id: 'demo-repo-2',
    pr_number: 87,
    external_pr_id: '87',
    title: 'fix: resolve race condition in WebSocket handler',
    author: 'bob',
    state: 'open',
    head_branch: 'fix/ws-race',
    base_branch: 'main',
    head_sha: 'def456',
    pr_url: '#',
    created_at: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString(),
    updated_at: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString(),
    latest_execution_status: null,
    latest_execution_id: null,
    repository: 'acme/frontend',
    date: '5h ago',
    executionDisplay: { label: 'No review yet', color: 'neutral' },
  },
  {
    id: 'demo-3',
    organization_id: 'demo-org',
    repository_id: 'demo-repo',
    pr_number: 143,
    external_pr_id: '143',
    title: 'refactor: extract payment service into separate module',
    author: 'charlie',
    state: 'open',
    head_branch: 'refactor/payment-service',
    base_branch: 'main',
    head_sha: 'ghi789',
    pr_url: '#',
    created_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
    updated_at: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
    latest_execution_status: 'processing',
    latest_execution_id: 'demo-exec-3',
    repository: 'acme/backend',
    date: '1d ago',
    executionDisplay: { label: 'Reviewing', color: 'primary' },
  },
]

const DEMO_ORGS: OrganizationListItem[] = [
  {
    id: 'demo-org',
    name: 'Acme Corp',
    external_org_id: '12345',
    provider: 'github',
    created_at: new Date().toISOString(),
    role: 'admin',
  },
]

const DEMO_REPOS: RepositoryListItem[] = [
  {
    id: 'demo-repo-1',
    organization_id: 'demo-org',
    external_repo_id: '100',
    provider: 'github',
    name: 'acme/backend',
    web_url: '#',
    created_at: new Date().toISOString(),
  },
  {
    id: 'demo-repo-2',
    organization_id: 'demo-org',
    external_repo_id: '101',
    provider: 'github',
    name: 'acme/frontend',
    web_url: '#',
    created_at: new Date().toISOString(),
  },
]

const DEMO_MEMBERS: MemberListItem[] = [
  {
    id: 'demo-member-1',
    provider_identity_id: 'pid-1',
    username: 'alice',
    avatar_url: null,
    role: 'admin',
    reviewate_enabled: true,
    is_linked: true,
  },
  {
    id: 'demo-member-2',
    provider_identity_id: 'pid-2',
    username: 'bob',
    avatar_url: null,
    role: 'member',
    reviewate_enabled: true,
    is_linked: false,
  },
]

export function useTour() {
  const { t } = useI18n()
  const route = useRoute()
  const toast = useToast()
  const authStore = useAuthStore()
  const client = useApi()

  interface TourStep extends DriveStep {
    page: string
    tab?: string
  }

  function getAllSteps(): TourStep[] {
    return [
      // ── Dashboard ──
      {
        page: '/',
        popover: {
          title: t('tour.welcome.title'),
          description: t('tour.welcome.description'),
        },
      },
      {
        page: '/',
        element: '#tour-review-button',
        popover: {
          title: t('tour.reviewButton.title'),
          description: t('tour.reviewButton.description'),
          side: 'bottom',
          align: 'end',
        },
      },
      {
        page: '/',
        element: '#tour-pr-switch',
        popover: {
          title: t('tour.prSwitch.title'),
          description: t('tour.prSwitch.description'),
          side: 'bottom',
          align: 'start',
        },
      },
      {
        page: '/',
        element: '#tour-org-sidebar',
        popover: {
          title: t('tour.orgSidebar.title'),
          description: t('tour.orgSidebar.description'),
          side: 'right',
          align: 'start',
        },
      },
      // ── Organizations ──
      {
        page: '/organizations',
        element: '#tour-add-org',
        popover: {
          title: t('tour.addOrg.title'),
          description: t('tour.addOrg.description'),
          side: 'right',
          align: 'center',
        },
      },
      {
        page: '/organizations',
        tab: 'general',
        element: '#tour-general-settings',
        popover: {
          title: t('tour.generalSettings.title'),
          description: t('tour.generalSettings.description'),
          side: 'bottom',
          align: 'center',
        },
      },
      {
        page: '/organizations',
        tab: 'general',
        element: '#tour-linked-repos',
        popover: {
          title: t('tour.linkedRepos.title'),
          description: t('tour.linkedRepos.description'),
          side: 'top',
          align: 'center',
        },
      },
      {
        page: '/organizations',
        tab: 'repositories',
        element: '#tour-repositories-content',
        popover: {
          title: t('tour.repositoriesTab.title'),
          description: t('tour.repositoriesTab.description'),
          side: 'left',
          align: 'center',
        },
      },
      {
        page: '/organizations',
        tab: 'team',
        element: '#tour-team-content',
        popover: {
          title: t('tour.teamTab.title'),
          description: t('tour.teamTab.description'),
          side: 'left',
          align: 'center',
        },
      },
    ]
  }

  /** Save onboarding step to backend (fire-and-forget) */
  function saveStep(step: number) {
    if (authStore.user) {
      authStore.user = { ...authStore.user, onboarding_step: step }
    }
    updateProfile({ client, body: { onboarding_step: step } })
  }

  function completeTour() {
    isTourActive.value = false
    pendingNavStep = null
    saveStep(TOTAL_STEPS)
    navigateTo('/')
  }

  function getStepsForPage(page: string): { steps: DriveStep[], tabs: (string | undefined)[], globalOffset: number } {
    const allSteps = getAllSteps()
    const globalOffset = allSteps.findIndex((s) => s.page === page)
    const pageSteps = allSteps.filter((s) => s.page === page)
    const tabs = pageSteps.map((s) => s.tab)
    const steps = pageSteps.map(({ page: _page, tab: _tab, ...rest }) => rest)
    return { steps, tabs, globalOffset: globalOffset === -1 ? 0 : globalOffset }
  }

  function activateTab(tab: string | undefined) {
    if (tab) {
      demoActiveTab.value = tab
    }
  }

  async function createDriver(steps: DriveStep[], tabs: (string | undefined)[], globalOffset: number, startIndex: number = 0) {
    const driverModule = await import('driver.js')
    await import('driver.js/dist/driver.css')

    const totalSteps = getAllSteps().length

    if (activeDriver) {
      activeDriver.destroy()
      activeDriver = null
    }

    isTourActive.value = true

    // Activate the tab for the starting step
    activateTab(tabs[startIndex])

    const driver = driverModule.driver({
      showProgress: false,
      popoverClass: 'reviewate-tour',
      stagePadding: 12,
      stageRadius: 14,
      allowClose: true,
      smoothScroll: true,
      overlayOpacity: 0.75,
      popoverOffset: 20,
      steps: steps.map((step, i) => ({
        ...step,
        popover: {
          ...step.popover,
          progressText: t('tour.progress', { current: globalOffset + i + 1, total: totalSteps }),
          nextBtnText: (globalOffset + i + 1 === totalSteps) ? t('tour.done') : t('tour.next'),
          prevBtnText: t('tour.prev'),
          onNextClick: () => {
            const globalIndex = globalOffset + (driver.getActiveIndex() ?? 0) + 1
            const allSteps = getAllSteps()

            if (globalIndex >= allSteps.length) {
              completeTour()
              driver.destroy()
              activeDriver = null
              return
            }

            // Save progress on every step
            saveStep(globalIndex)

            const nextStep = allSteps[globalIndex]
            if (nextStep && nextStep.page !== route.path) {
              pendingNavStep = globalIndex
              driver.destroy()
              activeDriver = null
              navigateTo(nextStep.page)
              return
            }

            // Switch tab before moving to next step
            const nextLocalIndex = (driver.getActiveIndex() ?? 0) + 1
            activateTab(tabs[nextLocalIndex])
            // Wait a tick for the tab content to render, scroll element into view, then move
            nextTick(() => {
              const selector = steps[nextLocalIndex]?.element as string | undefined
              if (selector) {
                document.querySelector(selector)?.scrollIntoView({ behavior: 'instant', block: 'center' })
              }
              driver.moveNext()
            })
          },
          onPrevClick: () => {
            const globalIndex = globalOffset + (driver.getActiveIndex() ?? 0) - 1
            if (globalIndex < 0) return

            saveStep(globalIndex)

            const allSteps = getAllSteps()
            const prevStep = allSteps[globalIndex]
            if (prevStep && prevStep.page !== route.path) {
              pendingNavStep = globalIndex
              driver.destroy()
              activeDriver = null
              navigateTo(prevStep.page)
              return
            }

            // Switch tab before moving to prev step
            const prevLocalIndex = (driver.getActiveIndex() ?? 0) - 1
            activateTab(tabs[prevLocalIndex])
            nextTick(() => {
              const selector = steps[prevLocalIndex]?.element as string | undefined
              if (selector) {
                document.querySelector(selector)?.scrollIntoView({ behavior: 'instant', block: 'center' })
              }
              driver.movePrevious()
            })
          },
        },
      })),
      onDestroyStarted: () => {
        if (activeDriver) {
          completeTour()
          activeDriver.destroy()
          activeDriver = null
        }
      },
    })

    activeDriver = driver
    driver.drive(startIndex)
  }

  async function startTour() {
    if (route.path !== '/') {
      pendingNavStep = 0
      isTourActive.value = true
      saveStep(0)
      await navigateTo('/')
      return
    }

    isTourActive.value = true
    saveStep(0)
    pendingNavStep = null

    // Wait a tick for demo data to render before highlighting elements
    await nextTick()
    setTimeout(async () => {
      const { steps, tabs, globalOffset } = getStepsForPage('/')
      if (steps.length > 0) {
        await createDriver(steps, tabs, globalOffset)
      }
    }, 100)
  }

  async function resumeTour() {
    const step = pendingNavStep ?? authStore.user?.onboarding_step
    if (step === null || step === undefined || step >= TOTAL_STEPS) return

    isTourActive.value = true
    pendingNavStep = null

    const allSteps = getAllSteps()
    const targetStep = allSteps[step]
    if (!targetStep) return

    // Wait for demo data to render
    await nextTick()
    setTimeout(async () => {
      const { steps, tabs, globalOffset } = getStepsForPage(targetStep.page)
      const localIndex = step - globalOffset
      if (steps.length > 0 && localIndex >= 0 && localIndex < steps.length) {
        await createDriver(steps, tabs, globalOffset, localIndex)
      }
    }, 100)
  }

  function shouldAutoStart(): boolean {
    if (import.meta.server) return false
    const step = authStore.user?.onboarding_step
    return (!step || step === 0) && window.innerWidth >= 1024
  }

  function hasPendingStep(): boolean {
    if (pendingNavStep !== null) return true
    const step = authStore.user?.onboarding_step
    return step !== null && step !== undefined && step > 0 && step < TOTAL_STEPS
  }

  function replayTour() {
    if (import.meta.server) return
    if (window.innerWidth < 1024) {
      toast.add({ title: t('tour.mobileNotSupported'), color: 'warning' })
      return
    }
    startTour()
  }

  // Patch demo PR authors so the first PR matches the logged-in user
  // (otherwise isNotAuthor() disables all review buttons during the tour)
  const demoPullRequests = computed(() => {
    const username = authStore.user?.github_username || authStore.user?.gitlab_username
    if (!username) return DEMO_PRS
    return DEMO_PRS.map((pr, i) => i === 0 ? { ...pr, author: username } : pr)
  })

  return {
    isTourActive: readonly(isTourActive),
    demoActiveTab: readonly(demoActiveTab),
    demoPullRequests,
    demoOrganizations: DEMO_ORGS,
    demoRepositories: DEMO_REPOS,
    demoMembers: DEMO_MEMBERS,
    startTour,
    resumeTour,
    shouldAutoStart,
    hasPendingStep,
    replayTour,
  }
}
