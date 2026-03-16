<script setup lang="ts">
/**
 * Repository List Component
 *
 * Displays the list of repositories within an organization.
 * GitLab subgroups render as drill-down folders; GitHub repos stay flat.
 */
import type { RepositoryListItem } from '@reviewate/api-types'

import { getProviderIcon } from '~/utils/organization'

const props = defineProps<{
  repositories: RepositoryListItem[]
  selectedRepoId: string | null
  hasSelectedRepo: boolean
  isLoading: boolean
}>()

const emit = defineEmits<{
  select: [repo: RepositoryListItem]
}>()

const searchQuery = ref('')
const currentPath = ref('')
const navigationDirection = ref<'forward' | 'back'>('forward')

/**
 * Extract subgroup path from web_url (e.g., "qa/team" from "https://gitlab.com/org/qa/team/project")
 * Returns empty string if no subgroups exist.
 */
function getRepoSubgroup(webUrl: string): string {
  try {
    const url = new URL(webUrl)
    // Path: /org/subgroup1/subgroup2/repo -> ["org", "subgroup1", "subgroup2", "repo"]
    const pathParts = url.pathname.slice(1).split('/')
    // Remove first (org) and last (repo name) to get subgroups only
    const subgroups = pathParts.slice(1, -1)
    return subgroups.join('/')
  } catch {
    return ''
  }
}

const isSearching = computed(() => searchQuery.value.trim().length > 0)

const filteredRepositories = computed(() => {
  if (!isSearching.value) {
    return props.repositories
  }
  const query = searchQuery.value.toLowerCase()
  return props.repositories.filter((repo) => {
    const subgroup = getRepoSubgroup(repo.web_url)
    return repo.name.toLowerCase().includes(query) || subgroup.toLowerCase().includes(query)
  })
})

interface SubgroupItem {
  name: string
  repoCount: number
}

const subgroupItems = computed<SubgroupItem[]>(() => {
  if (isSearching.value) return []

  const seen = new Map<string, number>()
  for (const repo of props.repositories) {
    const subgroup = getRepoSubgroup(repo.web_url)
    // Compute relative path from currentPath
    let relative = subgroup
    if (currentPath.value) {
      if (!subgroup.startsWith(currentPath.value)) continue
      relative = subgroup.slice(currentPath.value.length)
      if (relative.startsWith('/')) relative = relative.slice(1)
    }
    if (!relative) continue // direct repo at this level
    const firstSegment = relative.split('/')[0]!
    seen.set(firstSegment, (seen.get(firstSegment) ?? 0) + 1)
  }

  return Array.from(seen.entries())
    .map(([name, repoCount]) => ({ name, repoCount }))
    .sort((a, b) => a.name.localeCompare(b.name))
})

const directRepos = computed(() => {
  if (isSearching.value) return filteredRepositories.value

  return props.repositories.filter((repo) => {
    const subgroup = getRepoSubgroup(repo.web_url)
    return subgroup === currentPath.value
  })
})

function navigateToSubgroup(name: string) {
  navigationDirection.value = 'forward'
  currentPath.value = currentPath.value ? `${currentPath.value}/${name}` : name
}

function navigateBack() {
  navigationDirection.value = 'back'
  const parts = currentPath.value.split('/')
  parts.pop()
  currentPath.value = parts.join('/')
}

// Reset navigation when repositories change (org switch)
watch(() => props.repositories, () => {
  currentPath.value = ''
})

// Reset currentPath when search clears
watch(isSearching, (searching) => {
  if (!searching) {
    currentPath.value = ''
  }
})
</script>

<template>
  <div class="h-full flex flex-col overflow-hidden">
    <!-- Repo List Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-neutral-200 dark:border-neutral-700 shrink-0 bg-white dark:bg-neutral-800">
      <div class="flex items-center gap-2">
        <span class="text-sm font-medium text-neutral-900 dark:text-neutral-100">
          {{ $t('organizations.repositories.title') }}
        </span>
        <span class="text-xs text-neutral-400 dark:text-neutral-500">({{ repositories.length }})</span>
      </div>
      <UInput
        v-if="!hasSelectedRepo"
        v-model="searchQuery"
        icon="i-lucide-search"
        :placeholder="$t('common.search')"
        size="xs"
        class="w-48"
      />
    </div>

    <!-- Scrollable Content -->
    <div class="flex-1 overflow-y-auto">
      <!-- Loading Skeleton -->
      <div
        v-if="isLoading && repositories.length === 0"
        class="divide-y divide-neutral-100 dark:divide-neutral-700"
      >
        <div
          v-for="i in 5"
          :key="i"
          class="flex items-center gap-3 px-4 py-3"
        >
          <div class="flex-1 min-w-0 space-y-2">
            <div class="flex items-center gap-2">
              <USkeleton class="size-4 rounded" />
              <USkeleton class="h-4 w-36" />
            </div>
            <USkeleton class="h-3 w-16" />
          </div>
          <USkeleton class="size-4 rounded" />
        </div>
      </div>

      <!-- Repo & Subgroup List -->
      <Transition
        v-if="!isLoading && (subgroupItems.length > 0 || directRepos.length > 0)"
        :name="navigationDirection === 'forward' ? 'slide-left' : 'slide-right'"
        mode="out-in"
      >
        <div
          :key="currentPath"
          class="divide-y divide-neutral-100 dark:divide-neutral-700"
        >
          <!-- Back to parent -->
          <button
            v-if="currentPath && !isSearching"
            type="button"
            class="cursor-pointer group flex items-center gap-3 px-4 py-3 w-full text-left hover:bg-neutral-50 dark:hover:bg-neutral-700/50 transition-all duration-200 ease-out focus:outline-none"
            @click="navigateBack"
          >
            <div class="size-6 flex items-center justify-center rounded bg-neutral-100 dark:bg-neutral-700 shrink-0">
              <UIcon
                name="i-lucide-corner-left-up"
                class="size-3.5 text-neutral-400 dark:text-neutral-500"
              />
            </div>
            <span class="text-sm text-neutral-500 dark:text-neutral-400">..</span>
          </button>

          <!-- Subgroup Folders -->
          <button
            v-for="sg in subgroupItems"
            :key="`sg-${currentPath}-${sg.name}`"
            type="button"
            class="cursor-pointer group flex items-center gap-3 px-4 py-3 w-full text-left hover:bg-neutral-50 dark:hover:bg-neutral-700/50 transition-all duration-200 ease-out focus:outline-none"
            @click="navigateToSubgroup(sg.name)"
          >
            <div class="size-6 flex items-center justify-center rounded bg-neutral-100 dark:bg-neutral-700 shrink-0">
              <UIcon
                name="i-lucide-folder"
                class="size-3.5 text-neutral-500 dark:text-neutral-400"
              />
            </div>
            <div class="flex-1 min-w-0">
              <span class="text-sm font-medium text-neutral-900 dark:text-neutral-100 truncate">
                {{ sg.name }}
              </span>
            </div>
            <span class="text-xs text-neutral-400 dark:text-neutral-500 shrink-0">
              {{ sg.repoCount }}
            </span>
            <UIcon
              name="i-lucide-chevron-right"
              class="size-4 text-neutral-300 dark:text-neutral-500 shrink-0"
            />
          </button>

          <!-- Direct Repos -->
          <button
            v-for="repo in directRepos"
            :key="repo.id"
            type="button"
            class="cursor-pointer group flex items-center gap-3 px-4 py-3 w-full text-left hover:bg-neutral-50 dark:hover:bg-neutral-700/50 transition-all duration-200 ease-out focus:outline-none"
            :class="{ 'bg-brand-50 dark:bg-brand-900/30': selectedRepoId === repo.id }"
            @click="emit('select', repo)"
          >
            <UAvatar
              :src="repo.avatar_url ?? undefined"
              :alt="repo.name"
              size="xs"
              class="shrink-0"
              :ui="{
                fallback: 'bg-neutral-100 dark:bg-neutral-700',
              }"
            >
              <UIcon
                :name="getProviderIcon(repo.provider)"
                class="size-3 text-neutral-400"
              />
            </UAvatar>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <span
                  class="text-sm font-medium truncate"
                  :class="selectedRepoId === repo.id
                    ? 'text-brand-700 dark:text-brand-300'
                    : 'text-neutral-900 dark:text-neutral-100'"
                >
                  {{ repo.name }}
                </span>
              </div>
              <div
                v-if="isSearching && getRepoSubgroup(repo.web_url)"
                class="flex items-center gap-2 mt-0.5"
              >
                <span class="text-xs text-neutral-500 dark:text-neutral-400 truncate">
                  {{ getRepoSubgroup(repo.web_url) }}
                </span>
              </div>
            </div>
            <UIcon
              name="i-lucide-settings"
              class="size-4 text-neutral-300 dark:text-neutral-500 group-hover:text-neutral-500 dark:group-hover:text-neutral-300 group-hover:rotate-45 transition-all duration-300 ease-out shrink-0"
            />
          </button>
        </div>
      </Transition>

      <!-- No Search Results -->
      <div
        v-if="!isLoading && subgroupItems.length === 0 && directRepos.length === 0 && searchQuery && repositories.length > 0"
        class="flex flex-col items-center justify-center py-12 px-4"
      >
        <div class="size-12 flex items-center justify-center rounded-full bg-neutral-100 dark:bg-neutral-700 mb-3">
          <UIcon
            name="i-lucide-search-x"
            class="size-6 text-neutral-400"
          />
        </div>
        <p class="text-sm font-medium text-neutral-900 dark:text-neutral-100 mb-1">
          {{ $t('common.noResults') }}
        </p>
        <p class="text-xs text-neutral-500 dark:text-neutral-400 text-center">
          {{ $t('common.noResultsDescription') }}
        </p>
      </div>

      <!-- Empty State (No Repositories) -->
      <div
        v-if="!isLoading && subgroupItems.length === 0 && directRepos.length === 0 && !searchQuery && repositories.length === 0"
        class="flex flex-col items-center justify-center py-12 px-4"
      >
        <div class="size-12 flex items-center justify-center rounded-full bg-neutral-100 dark:bg-neutral-700 mb-3">
          <UIcon
            name="i-lucide-git-branch"
            class="size-6 text-neutral-400"
          />
        </div>
        <p class="text-sm font-medium text-neutral-900 dark:text-neutral-100 mb-1">
          {{ $t('organizations.repositories.noRepositories') }}
        </p>
        <p class="text-xs text-neutral-500 dark:text-neutral-400 text-center">
          {{ $t('organizations.repositories.noRepositoriesDescription') }}
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.slide-left-enter-active,
.slide-left-leave-active,
.slide-right-enter-active,
.slide-right-leave-active {
  transition: all 0.2s ease-out;
}

.slide-left-enter-from {
  opacity: 0;
  transform: translateX(20px);
}

.slide-left-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

.slide-right-enter-from {
  opacity: 0;
  transform: translateX(-20px);
}

.slide-right-leave-to {
  opacity: 0;
  transform: translateX(20px);
}
</style>
