<script setup lang="ts">
/**
 * Organization List Component
 *
 * Displays the list of organizations with selection state.
 * Shows empty state when no organizations are available.
 */
import type { OrganizationListItem } from '@reviewate/api-types'

import { getInitial, getProviderIcon, getProviderName } from '~/utils/organization'

defineProps<{
  organizations: OrganizationListItem[]
  selectedOrgId: string | null
  hasOrganizations: boolean
}>()

const emit = defineEmits<{
  select: [org: OrganizationListItem]
  addGithub: []
  addGitlab: []
}>()

const configStore = useConfigStore()
</script>

<template>
  <CornerFrame class="flex flex-col flex-1 border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 shadow-sm overflow-hidden">
    <!-- Header -->
    <div class="flex items-center px-4 py-3 border-b border-neutral-200 dark:border-neutral-700 shrink-0">
      <h2 class="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
        {{ $t('organizations.title') }}
      </h2>
    </div>

    <!-- Empty State -->
    <div
      v-if="!hasOrganizations"
      class="flex flex-col items-center justify-center flex-1 gap-4 p-4"
    >
      <div class="size-12 flex items-center justify-center rounded-full bg-neutral-100 dark:bg-neutral-700">
        <UIcon
          name="i-lucide-building-2"
          class="size-6 text-neutral-400"
        />
      </div>
      <div class="text-center">
        <p class="text-sm font-medium text-neutral-900 dark:text-neutral-100 mb-1">
          {{ $t('organizations.noOrganizations') }}
        </p>
        <p class="text-xs text-neutral-500 dark:text-neutral-400 mb-4">
          {{ $t('organizations.noOrganizationsDescription') }}
        </p>
      </div>
      <div class="flex flex-col gap-2 w-full">
        <UButton
          color="primary"
          size="xs"
          class="w-full"
          icon="i-simple-icons-github"
          :disabled="!configStore.isGitHubEnabled"
          @click="emit('addGithub')"
        >
          {{ $t('organizations.addFromGithub') }}
        </UButton>
        <UButton
          color="neutral"
          variant="outline"
          size="xs"
          class="w-full"
          icon="i-simple-icons-gitlab"
          :disabled="!configStore.isGitLabEnabled"
          @click="emit('addGitlab')"
        >
          {{ $t('organizations.addFromGitlab') }}
        </UButton>
      </div>
    </div>

    <!-- Org list -->
    <div
      v-else
      class="divide-y divide-neutral-100 dark:divide-neutral-700 overflow-y-auto flex-1"
    >
      <button
        v-for="org in organizations"
        :key="org.id"
        type="button"
        class="cursor-pointer group flex items-center gap-3 px-4 py-3 w-full text-left hover:bg-neutral-50 dark:hover:bg-neutral-700/50 transition-colors focus:outline-none"
        :class="{ 'bg-brand-50 dark:bg-brand-900/30': selectedOrgId === org.id }"
        @click="emit('select', org)"
      >
        <UAvatar
          :src="org.avatar_url ?? undefined"
          :alt="org.name"
          size="sm"
          class="shrink-0"
          :class="selectedOrgId === org.id
            ? 'ring-2 ring-brand-500'
            : ''"
          :ui="{
            fallback: selectedOrgId === org.id
              ? 'bg-brand-500 text-white'
              : 'bg-neutral-100 dark:bg-neutral-700 text-neutral-600 dark:text-neutral-200 group-hover:bg-neutral-200 dark:group-hover:bg-neutral-600',
          }"
        >
          <span class="text-sm font-semibold">{{ getInitial(org.name) }}</span>
        </UAvatar>
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2">
            <span
              class="text-sm font-medium truncate"
              :class="selectedOrgId === org.id
                ? 'text-brand-700 dark:text-brand-300'
                : 'text-neutral-900 dark:text-neutral-100'"
            >
              {{ org.name }}
            </span>
          </div>
          <span class="text-xs text-neutral-500 dark:text-neutral-400">
            {{ getProviderName(org.provider) }}
          </span>
        </div>
        <UIcon
          :name="getProviderIcon(org.provider)"
          class="size-4 text-neutral-400 dark:text-neutral-500"
        />
      </button>
    </div>

    <!-- Add buttons at bottom -->
    <div
      v-if="hasOrganizations"
      id="tour-add-org"
      class="p-3 border-t border-neutral-200 dark:border-neutral-700 shrink-0"
    >
      <div class="flex gap-2">
        <UButton
          color="primary"
          size="xs"
          class="flex-1"
          icon="i-simple-icons-github"
          :disabled="!configStore.isGitHubEnabled"
          @click="emit('addGithub')"
        >
          GitHub
        </UButton>
        <UButton
          color="neutral"
          variant="outline"
          size="xs"
          class="flex-1"
          icon="i-simple-icons-gitlab"
          :disabled="!configStore.isGitLabEnabled"
          @click="emit('addGitlab')"
        >
          GitLab
        </UButton>
      </div>
    </div>
  </CornerFrame>
</template>
