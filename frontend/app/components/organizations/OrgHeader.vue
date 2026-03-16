<script setup lang="ts">
/**
 * Organization Settings Header Component
 *
 * Displays the organization header with avatar, name, and provider info.
 */
import type { OrganizationListItem } from '@reviewate/api-types'

import { getInitial, getProviderIcon, getProviderName } from '~/utils/organization'

defineProps<{
  organization: OrganizationListItem
}>()

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}
</script>

<template>
  <div class="flex items-center justify-between px-6 py-4 border-b border-neutral-200 dark:border-neutral-700 shrink-0">
    <div class="flex items-center gap-4">
      <div class="size-12 flex items-center justify-center text-lg font-semibold rounded-lg bg-brand-500 text-white">
        {{ getInitial(organization.name) }}
      </div>
      <div>
        <h2 class="text-lg font-semibold text-neutral-900 dark:text-neutral-100">
          {{ organization.name }}
        </h2>
        <div class="flex items-center gap-2 text-sm text-neutral-500 dark:text-neutral-400">
          <UIcon
            :name="getProviderIcon(organization.provider)"
            class="size-4"
          />
          <span>{{ getProviderName(organization.provider) }}</span>
          <span>·</span>
          <span>{{ $t('organizations.createdAt') }} {{ formatDate(organization.created_at) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
