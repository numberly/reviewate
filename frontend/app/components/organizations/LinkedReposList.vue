<script setup lang="ts">
/**
 * LinkedReposList Component
 *
 * Displays and manages linked repositories for an organization or repository.
 * Reusable for both org-level and repo-level linked repos.
 */
import type { LinkedRepositoryCreate, LinkedRepositoryResponse, ListGenericResponseLinkedRepositoryResponse } from '@reviewate/api-types'
import {
  addOrganizationLinkedRepo,
  addRepositoryLinkedRepo,
  deleteLinkedRepo,
  listOrganizationLinkedRepos,
  listRepositoryLinkedRepos,
} from '@reviewate/api-types'

const props = defineProps<{
  /** Organization ID (for org-level linked repos) */
  organizationId?: string
  /** Repository ID (for repo-level linked repos) */
  repositoryId?: string
  /** Description text to show under the section title */
  description?: string
  /** Whether the current user is an admin (can add/delete) */
  isAdmin?: boolean
}>()

const { t } = useI18n()
const client = useApi()
const toast = useToast()

// State
const linkedRepos = ref<LinkedRepositoryResponse[]>([])
const isLoading = ref(false)
const isAdding = ref(false)
const isDeleting = ref<string | null>(null)
const showAddForm = ref(false)

// Only show form if user wants it AND is admin
const shouldShowAddForm = computed(() => showAddForm.value && props.isAdmin)

// Determine if this is org-level or repo-level
const isOrgLevel = computed(() => !!props.organizationId && !props.repositoryId)

// Load linked repos
async function loadLinkedRepos() {
  isLoading.value = true

  try {
    let response: { data?: ListGenericResponseLinkedRepositoryResponse }

    if (isOrgLevel.value && props.organizationId) {
      response = await listOrganizationLinkedRepos({
        client,
        path: { org_id: props.organizationId },
      })
    } else if (props.repositoryId) {
      response = await listRepositoryLinkedRepos({
        client,
        path: { repo_id: props.repositoryId },
      })
    } else {
      return
    }

    if (response.data) {
      linkedRepos.value = response.data.objects
    }
  } finally {
    isLoading.value = false
  }
}

// Add linked repo
async function handleAdd(data: LinkedRepositoryCreate) {
  isAdding.value = true

  try {
    let response: { data?: LinkedRepositoryResponse, error?: unknown }

    if (isOrgLevel.value && props.organizationId) {
      response = await addOrganizationLinkedRepo({
        client,
        path: { org_id: props.organizationId },
        body: data,
      })
    } else if (props.repositoryId) {
      response = await addRepositoryLinkedRepo({
        client,
        path: { repo_id: props.repositoryId },
        body: data,
      })
    } else {
      return
    }

    if (response.error) {
      toast.add({
        title: t('organizations.linkedRepos.addFailed'),
        color: 'error',
      })
    } else if (response.data) {
      linkedRepos.value.push(response.data)
      showAddForm.value = false
      toast.add({
        title: t('organizations.linkedRepos.added'),
        color: 'success',
      })
    }
  } finally {
    isAdding.value = false
  }
}

// Remove linked repo
async function handleRemove(linkedRepoId: string) {
  isDeleting.value = linkedRepoId

  try {
    const { error } = await deleteLinkedRepo({
      client,
      path: { linked_repo_id: linkedRepoId },
    })

    if (error) {
      toast.add({
        title: t('organizations.linkedRepos.removeFailed'),
        color: 'error',
      })
    } else {
      linkedRepos.value = linkedRepos.value.filter((r) => r.id !== linkedRepoId)
      toast.add({
        title: t('organizations.linkedRepos.removed'),
        color: 'success',
      })
    }
  } finally {
    isDeleting.value = null
  }
}

// Load on mount and when IDs change
watch(
  () => [props.organizationId, props.repositoryId],
  () => loadLinkedRepos(),
  { immediate: true },
)
</script>

<template>
  <SettingSection
    id="tour-linked-repos"
    :title="$t('organizations.linkedRepos.title')"
    icon="i-lucide-link"
  >
    <p
      v-if="description"
      class="text-sm text-neutral-500 mb-4"
    >
      {{ description }}
    </p>

    <!-- Loading -->
    <template v-if="isLoading">
      <div class="flex items-center justify-center py-8">
        <UIcon
          name="i-lucide-loader-2"
          class="size-6 animate-spin text-neutral-400"
        />
      </div>
    </template>

    <!-- Empty state -->
    <template v-else-if="linkedRepos.length === 0 && !shouldShowAddForm">
      <div class="text-center py-8">
        <UIcon
          name="i-lucide-link-2"
          class="size-12 mx-auto text-neutral-300 mb-3"
        />
        <p class="text-sm text-neutral-500 mb-4">
          {{ $t('organizations.linkedRepos.noLinkedReposDescription') }}
        </p>
        <UButton
          v-if="isAdmin"
          variant="soft"
          size="sm"
          icon="i-lucide-plus"
          @click="showAddForm = true"
        >
          {{ $t('organizations.linkedRepos.addLinkedRepo') }}
        </UButton>
      </div>
    </template>

    <!-- Linked repos list -->
    <template v-else>
      <div
        v-if="linkedRepos.length > 0"
        class="space-y-3 mb-4"
      >
        <div
          v-for="repo in linkedRepos"
          :key="repo.id"
          class="flex items-center justify-between p-3 rounded-lg bg-neutral-50 dark:bg-neutral-800"
        >
          <div class="flex items-center gap-3">
            <UIcon
              :name="repo.linked_provider === 'github' ? 'i-simple-icons-github' : 'i-simple-icons-gitlab'"
              class="size-5 text-neutral-500"
            />
            <div>
              <div class="font-medium text-sm">
                {{ repo.display_name || repo.linked_repo_path }}
              </div>
              <div class="text-xs text-neutral-500">
                {{ repo.linked_repo_path }}
                <span v-if="repo.linked_branch">@ {{ repo.linked_branch }}</span>
              </div>
            </div>
          </div>
          <UButton
            v-if="isAdmin"
            variant="ghost"
            color="error"
            size="xs"
            icon="i-lucide-trash-2"
            :loading="isDeleting === repo.id"
            @click="handleRemove(repo.id)"
          />
        </div>
      </div>

      <!-- Add form -->
      <template v-if="shouldShowAddForm">
        <USeparator class="my-4" />
        <LinkedRepoForm
          :is-submitting="isAdding"
          @submit="handleAdd"
          @cancel="showAddForm = false"
        />
      </template>

      <!-- Add button (admin only) -->
      <template v-else-if="isAdmin">
        <UButton
          variant="soft"
          size="sm"
          icon="i-lucide-plus"
          @click="showAddForm = true"
        >
          {{ $t('organizations.linkedRepos.addLinkedRepo') }}
        </UButton>
      </template>
    </template>
  </SettingSection>
</template>
