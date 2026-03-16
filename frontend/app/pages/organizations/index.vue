<script setup lang="ts">
/**
 * Organizations Page
 *
 * Split panel layout: left panel with org list (w-80), right panel with settings (flex-1).
 * Settings panel uses tabs: General, Repositories, and Team.
 */
import type { OrganizationListItem, RepositoryListItem } from '@reviewate/api-types'

const { t } = useI18n()
const toast = useToast()
const orgsStore = useOrganizationsStore()
const reposStore = useRepositoriesStore()

useHead({
  title: () => `${t('organizations.title')} - Reviewate`,
})

// ============================================================================
// Data Fetching
// ============================================================================

const { resumeTour, hasPendingStep, isTourActive, demoActiveTab, demoOrganizations, demoRepositories, demoMembers } = useTour()
const demoSelectedOrg = computed(() => demoOrganizations[0] ?? null)

onMounted(() => {
  orgsStore.fetchOrganizations()

  // Resume onboarding tour if navigated here from dashboard
  if (hasPendingStep()) {
    if (orgsStore.isInitialized) {
      setTimeout(() => resumeTour(), 400)
    } else {
      const stopWatch = watch(() => orgsStore.isInitialized, (ready) => {
        if (ready) {
          stopWatch()
          setTimeout(() => resumeTour(), 400)
        }
      })
    }
  }
})

// ============================================================================
// Organization & Repository Selection
// ============================================================================

const {
  selectedOrgId,
  selectedOrg,
  selectOrg,
  selectedRepoId,
  selectedRepo,
  repositories,
  selectRepo,
} = useOrganizationSelection()

// Auto-select first org when organizations load (only on settings page)
watch(() => orgsStore.organizations, (orgs) => {
  if (orgs.length > 0 && !selectedOrgId.value) {
    const firstOrg = orgs[0]
    if (firstOrg) {
      orgsStore.setSelectedOrgId(firstOrg.id)
    }
  }
}, { immediate: true })

// ============================================================================
// Mobile Navigation (inlined — only used here)
// ============================================================================

const isMobileListView = ref(true)

function selectOrgAndShowDetail(org: OrganizationListItem) {
  selectOrg(org)
  isMobileListView.value = false
}

// ============================================================================
// Tabs State
// ============================================================================

const activeTab = ref('general')

// ============================================================================
// Members State
// ============================================================================

const {
  members,
  selectedMember,
  isMembersLoading,
  isOrgAdmin,
  currentUserMemberId,
  selectMember,
  handleMemberUpdated,
} = useMembers(selectedOrgId)

// ============================================================================
// GitLab Modal
// ============================================================================

const isGitlabModalOpen = ref(false)

async function handleAddGitlab(token: string, url: string) {
  const result = await orgsStore.addGitlabSource(token, url)

  if (result.success) {
    isGitlabModalOpen.value = false
    toast.add({ title: t('organizations.gitlabAdded'), color: 'success' })
    if (selectedOrgId.value) {
      reposStore.fetchRepositories(selectedOrgId.value)
    }
  } else {
    toast.add({ title: orgsStore.gitlabError || t('organizations.gitlabFailed'), color: 'error' })
  }
}

// ============================================================================
// Delete Repository
// ============================================================================

const {
  isOpen: isDeleteRepoDialogOpen,
  itemToDelete: repositoryToDelete,
  isDeleting: isDeletingRepo,
  error: deleteRepoError,
  confirm: confirmDeleteRepository,
  execute: executeDeleteRepository,
  clearError: clearDeleteRepoError,
} = useDeleteConfirmation<RepositoryListItem>({
  onDelete: async (repo) => {
    if (!selectedOrgId.value) return false
    return await reposStore.deleteRepository(repo.id, selectedOrgId.value)
  },
  onSuccess: (repo) => {
    if (selectedRepoId.value === repo.id) {
      selectRepo(null)
    }
    toast.add({ title: t('organizations.repositories.deleted'), color: 'success' })
  },
  getError: () => reposStore.error,
})

// ============================================================================
// Delete Organization
// ============================================================================

const {
  isOpen: isDeleteOrgDialogOpen,
  itemToDelete: organizationToDelete,
  isDeleting: isDeletingOrg,
  error: deleteOrgError,
  confirm: confirmDeleteOrganization,
  execute: executeDeleteOrganization,
  clearError: clearDeleteOrgError,
} = useDeleteConfirmation<OrganizationListItem>({
  onDelete: async (org) => {
    return await orgsStore.deleteOrganization(org.id)
  },
  onSuccess: (org) => {
    if (selectedOrgId.value === org.id) {
      orgsStore.setSelectedOrgId(null)
    }
    toast.add({ title: t('organizations.deleted'), color: 'success' })
  },
  getError: () => orgsStore.error,
})

// ============================================================================
// Shared Settings Bindings
// ============================================================================

const settingsProps = computed(() => ({
  organization: selectedOrg.value!,
  activeTab: activeTab.value,
  repositories: repositories.value,
  selectedRepo: selectedRepo.value,
  isRepoLoading: reposStore.isLoading,
  isRepoDeleting: reposStore.isDeleting,
  isAdmin: isOrgAdmin.value,
  members: members.value,
  selectedMember: selectedMember.value,
  organizationId: selectedOrgId.value!,
  isMembersLoading: isMembersLoading.value,
  currentUserMemberId: currentUserMemberId.value,
}))

const settingsHandlers = {
  'update:activeTab': (v: string) => {
    activeTab.value = v
  },
  'delete': confirmDeleteOrganization,
  selectRepo,
  'deleteRepo': confirmDeleteRepository,
  selectMember,
  'memberUpdated': handleMemberUpdated,
}
</script>

<template>
  <!-- Page Header -->
  <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 pb-6 border-b border-neutral-200 dark:border-neutral-700 shrink-0">
    <div class="flex flex-col gap-0.5 relative z-10">
      <p class="text-xl sm:text-2xl font-semibold text-neutral-900 dark:text-neutral-100 tracking-tight">
        {{ $t('organizations.title') }}
      </p>
      <p class="text-sm text-neutral-500 dark:text-neutral-400">
        {{ $t('organizations.subtitle') }}
      </p>
    </div>
  </div>

  <!-- Desktop Layout (lg+): Side by side -->
  <div class="hidden lg:flex gap-6 h-[calc(100vh-220px)] min-h-[500px]">
    <!-- Left Panel: Organizations List (w-80) -->
    <div class="w-80 shrink-0 flex flex-col">
      <!-- Tour Demo Org List -->
      <template v-if="isTourActive">
        <OrgList
          :organizations="demoOrganizations"
          :selected-org-id="demoOrganizations[0]?.id ?? null"
          :has-organizations="true"
        />
      </template>

      <!-- Loading Skeleton -->
      <OrgListSkeleton v-else-if="!orgsStore.isInitialized" />

      <!-- Loaded Content -->
      <OrgList
        v-else
        :organizations="orgsStore.organizations"
        :selected-org-id="selectedOrgId"
        :has-organizations="orgsStore.hasOrganizations"
        @select="selectOrg"
        @add-github="orgsStore.installGitHubApp()"
        @add-gitlab="isGitlabModalOpen = true"
      />
    </div>

    <!-- Right Panel: Settings (flex-1) -->
    <div class="flex-1 min-w-0 flex flex-col">
      <CornerFrame
        class="flex-1 flex flex-col rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 shadow-sm overflow-hidden"
        :class="{ 'opacity-50 pointer-events-none': !isTourActive && !selectedOrg && orgsStore.isInitialized }"
      >
        <!-- Tour Demo Settings Panel -->
        <OrgSettingsContent
          v-if="isTourActive && demoSelectedOrg"
          :organization="demoSelectedOrg"
          :active-tab="demoActiveTab"
          :repositories="demoRepositories"
          :selected-repo="null"
          :is-repo-loading="false"
          :is-repo-deleting="false"
          :is-admin="true"
          :members="demoMembers"
          :selected-member="null"
          :organization-id="demoSelectedOrg.id"
          :is-members-loading="false"
          :current-user-member-id="null"
          readonly
        />

        <!-- Loading Skeleton -->
        <OrgSettingsSkeleton v-else-if="!orgsStore.isInitialized" />

        <!-- No Selection State -->
        <div
          v-else-if="!selectedOrg"
          class="flex flex-col items-center justify-center h-full gap-4 p-8"
        >
          <div class="size-16 flex items-center justify-center rounded-full bg-neutral-100 dark:bg-neutral-700">
            <UIcon
              name="i-lucide-settings"
              class="size-8 text-neutral-400"
            />
          </div>
          <div class="text-center">
            <h3 class="text-lg font-semibold text-neutral-900 dark:text-neutral-100 mb-1">
              {{ $t('organizations.selectOrganization') }}
            </h3>
            <p class="text-sm text-neutral-500 dark:text-neutral-400">
              {{ $t('organizations.selectOrganizationDescription') }}
            </p>
          </div>
        </div>

        <!-- Settings Content -->
        <OrgSettingsContent
          v-else
          v-bind="settingsProps"
          v-on="settingsHandlers"
        />
      </CornerFrame>
    </div>
  </div>

  <!-- Mobile/Tablet Layout (< lg): Single panel with navigation -->
  <div class="lg:hidden h-[calc(100vh-220px)] min-h-[400px]">
    <!-- Loading Skeleton -->
    <OrgListSkeleton v-if="!orgsStore.isInitialized" />

    <!-- Loaded Content -->
    <template v-else>
      <Transition
        enter-active-class="transition-all duration-200 ease-out"
        enter-from-class="opacity-0 -translate-x-4"
        enter-to-class="opacity-100 translate-x-0"
        leave-active-class="transition-all duration-150 ease-in"
        leave-from-class="opacity-100 translate-x-0"
        leave-to-class="opacity-0 -translate-x-4"
        mode="out-in"
      >
        <!-- Organization List View -->
        <div
          v-if="isMobileListView"
          class="h-full"
        >
          <OrgList
            :organizations="orgsStore.organizations"
            :selected-org-id="selectedOrgId"
            :has-organizations="orgsStore.hasOrganizations"
            @select="selectOrgAndShowDetail"
            @add-github="orgsStore.installGitHubApp()"
            @add-gitlab="isGitlabModalOpen = true"
          />
        </div>

        <!-- Settings View -->
        <div
          v-else
          class="h-full flex flex-col"
        >
          <CornerFrame
            class="flex-1 flex flex-col rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 shadow-sm overflow-hidden"
          >
            <!-- Mobile Back Button + Header -->
            <div class="flex items-center gap-3 px-4 py-3 border-b border-neutral-200 dark:border-neutral-700 shrink-0">
              <button
                type="button"
                class="cursor-pointer p-2 -ml-2 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-700 transition-colors"
                @click="isMobileListView = true"
              >
                <UIcon
                  name="i-lucide-arrow-left"
                  class="size-5 text-neutral-500"
                />
              </button>
              <div
                v-if="selectedOrg"
                class="flex-1 min-w-0"
              >
                <h2 class="text-base font-semibold text-neutral-900 dark:text-neutral-100 truncate">
                  {{ selectedOrg.name }}
                </h2>
              </div>
            </div>

            <!-- Settings Content -->
            <OrgSettingsContent
              v-if="selectedOrg"
              v-bind="settingsProps"
              hide-header
              v-on="settingsHandlers"
            />
          </CornerFrame>
        </div>
      </Transition>
    </template>
  </div>

  <!-- GitLab Token Modal -->
  <GitLabModal
    :open="isGitlabModalOpen"
    :is-loading="orgsStore.isAddingGitlab"
    @update:open="isGitlabModalOpen = $event"
    @submit="handleAddGitlab"
  />

  <!-- Delete Repository Confirmation Modal -->
  <DeleteConfirmModal
    :open="isDeleteRepoDialogOpen"
    :is-loading="isDeletingRepo"
    :title="$t('organizations.repositories.deleteConfirmTitle')"
    :description="$t('organizations.repositories.deleteConfirmMessage')"
    :item-name="repositoryToDelete?.name ?? ''"
    :error-message="deleteRepoError"
    @update:open="isDeleteRepoDialogOpen = $event"
    @confirm="executeDeleteRepository"
    @clear-error="clearDeleteRepoError"
  />

  <!-- Delete Organization Confirmation Modal -->
  <DeleteConfirmModal
    :open="isDeleteOrgDialogOpen"
    :is-loading="isDeletingOrg"
    :title="$t('organizations.deleteConfirmTitle')"
    :description="$t('organizations.deleteConfirmMessage')"
    :item-name="organizationToDelete?.name ?? ''"
    :error-message="deleteOrgError"
    @update:open="isDeleteOrgDialogOpen = $event"
    @confirm="executeDeleteOrganization"
    @clear-error="clearDeleteOrgError"
  />
</template>
