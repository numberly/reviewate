<script setup lang="ts">
import type { OrganizationListItem } from '@reviewate/api-types'

import { getInitial, getProviderIcon, getProviderName } from '~/utils/organization'

interface Props {
  organizations: OrganizationListItem[]
}

defineProps<Props>()

const orgsStore = useOrganizationsStore()

const emit = defineEmits<{
  selectOrg: [orgId: string | null]
}>()

/**
 * Select an organization for filtering
 */
function selectOrg(org: OrganizationListItem): void {
  orgsStore.setSelectedOrgId(org.id)
  emit('selectOrg', org.id)
}

/**
 * Clear organization filter (show all)
 */
function clearSelection(): void {
  orgsStore.setSelectedOrgId(null)
  emit('selectOrg', null)
}
</script>

<template>
  <CornerFrame
    id="tour-org-sidebar"
    class="flex flex-col rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 shadow-sm shrink-0"
  >
    <div class="flex items-center justify-between px-4 py-3 border-b border-neutral-200 dark:border-neutral-700 shrink-0">
      <div class="flex items-center gap-2">
        <UIcon
          name="i-heroicons-building-office-2"
          class="size-4 text-neutral-500 dark:text-neutral-400"
        />
        <h3 class="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
          {{ $t('organizations.title') }}
        </h3>
        <span class="text-xs text-neutral-400 dark:text-neutral-500">({{ organizations.length }})</span>
      </div>
      <NuxtLink to="/organizations">
        <UButton
          icon="i-lucide-settings"
          variant="ghost"
          color="neutral"
          size="xs"
          square
          :ui="{ base: 'size-7' }"
        />
      </NuxtLink>
    </div>

    <!-- Empty state -->
    <NuxtLink
      v-if="organizations.length === 0"
      to="/organizations"
      class="flex flex-col items-center justify-center gap-2 px-4 py-8 hover:bg-neutral-50 dark:hover:bg-neutral-700 transition-colors cursor-pointer"
    >
      <div class="size-10 flex items-center justify-center rounded-full bg-neutral-100 dark:bg-neutral-700">
        <UIcon
          name="i-heroicons-plus"
          class="size-5 text-neutral-400 dark:text-neutral-400"
        />
      </div>
      <p class="text-sm text-neutral-500 dark:text-neutral-300">
        {{ $t('organizations.noOrganizations') }}
      </p>
      <span class="text-xs font-medium text-brand-500 hover:text-brand-600 dark:text-brand-400 dark:hover:text-brand-300">
        {{ $t('organizations.addFirst') }}
      </span>
    </NuxtLink>

    <!-- Org list - fixed max height -->
    <div
      v-else
      class="divide-y divide-neutral-100 dark:divide-neutral-700 overflow-y-auto min-h-0 flex-1"
    >
      <!-- All Organizations option -->
      <button
        type="button"
        class="cursor-pointer group flex items-center gap-3 px-4 py-2.5 w-full text-left hover:bg-neutral-50 dark:hover:bg-neutral-700 transition-colors focus:outline-none"
        :class="{
          'bg-brand-50 dark:bg-brand-900/20 hover:bg-brand-100 dark:hover:bg-brand-900/30': orgsStore.selectedOrgId === null,
        }"
        @click="clearSelection"
      >
        <div
          class="size-7 flex items-center justify-center text-xs font-semibold bg-neutral-100 dark:bg-neutral-700 text-neutral-600 dark:text-neutral-200 group-hover:bg-neutral-200 dark:group-hover:bg-neutral-600 transition-colors rounded-lg"
        >
          <UIcon
            name="i-lucide-layers"
            class="size-4"
          />
        </div>
        <div class="flex-1 min-w-0">
          <span class="text-sm font-medium text-neutral-900 dark:text-neutral-100">{{ $t('organizations.allOrganizations') }}</span>
        </div>
      </button>

      <!-- Individual organizations -->
      <button
        v-for="org in organizations"
        :key="org.id"
        type="button"
        class="cursor-pointer group flex items-center gap-3 px-4 py-2.5 w-full text-left hover:bg-neutral-50 dark:hover:bg-neutral-700 transition-colors focus:outline-none"
        :class="{
          'bg-brand-50 dark:bg-brand-900/20 hover:bg-brand-100 dark:hover:bg-brand-900/30': orgsStore.selectedOrgId === org.id,
        }"
        @click="selectOrg(org)"
      >
        <div
          class="size-7 flex items-center justify-center text-xs font-semibold bg-neutral-100 dark:bg-neutral-700 text-neutral-600 dark:text-neutral-200 group-hover:bg-neutral-200 dark:group-hover:bg-neutral-600 transition-colors rounded-lg"
        >
          {{ getInitial(org.name) }}
        </div>
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2">
            <span class="text-sm font-medium text-neutral-900 dark:text-neutral-100 truncate">{{ org.name }}</span>
          </div>
          <div class="flex items-center gap-1 text-xs text-neutral-500 dark:text-neutral-400">
            <UIcon
              :name="getProviderIcon(org.provider)"
              class="size-3"
            />
            <span>{{ getProviderName(org.provider) }}</span>
          </div>
        </div>
      </button>
    </div>
  </CornerFrame>
</template>
