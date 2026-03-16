<script setup lang="ts">
/**
 * Member List Component
 *
 * Displays the list of members within an organization.
 */
import type { MemberListItem } from '@reviewate/api-types'

const props = defineProps<{
  members: MemberListItem[]
  selectedMemberId: string | null
  hasSelectedMember: boolean
  isLoading: boolean
}>()

const emit = defineEmits<{
  select: [member: MemberListItem]
}>()

const searchQuery = ref('')

const filteredMembers = computed(() => {
  if (!searchQuery.value.trim()) {
    return props.members
  }
  const query = searchQuery.value.toLowerCase()
  return props.members.filter((member) => {
    return member.username?.toLowerCase().includes(query)
  })
})
</script>

<template>
  <div class="h-full flex flex-col overflow-hidden">
    <!-- Member List Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-neutral-200 dark:border-neutral-700 shrink-0 bg-white dark:bg-neutral-800">
      <div class="flex items-center gap-2">
        <span class="text-sm font-medium text-neutral-900 dark:text-neutral-100">
          {{ $t('organizations.team.title') }}
        </span>
        <span class="text-xs text-neutral-400 dark:text-neutral-500">({{ members.length }})</span>
      </div>
      <UInput
        v-if="!hasSelectedMember"
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
        v-if="isLoading && members.length === 0"
        class="divide-y divide-neutral-100 dark:divide-neutral-700"
      >
        <div
          v-for="i in 5"
          :key="i"
          class="flex items-center gap-3 px-4 py-3"
        >
          <USkeleton class="size-8 rounded-full" />
          <div class="flex-1 min-w-0 space-y-2">
            <USkeleton class="h-4 w-24" />
            <USkeleton class="h-3 w-16" />
          </div>
          <USkeleton class="size-4 rounded" />
        </div>
      </div>

      <!-- Member List -->
      <div
        v-else-if="filteredMembers.length > 0"
        class="divide-y divide-neutral-100 dark:divide-neutral-700"
      >
        <button
          v-for="member in filteredMembers"
          :key="member.id"
          type="button"
          class="cursor-pointer group flex items-center gap-3 px-4 py-3 w-full text-left hover:bg-neutral-50 dark:hover:bg-neutral-700/50 transition-all duration-200 ease-out focus:outline-none"
          :class="{ 'bg-brand-50 dark:bg-brand-900/30': selectedMemberId === member.id }"
          @click="emit('select', member)"
        >
          <!-- Avatar -->
          <div class="relative shrink-0">
            <UAvatar
              :src="member.avatar_url || undefined"
              :alt="member.username || 'Member'"
              size="sm"
            >
              <span class="text-xs font-medium text-neutral-600 dark:text-neutral-300">
                {{ (member.username ?? '?').charAt(0).toUpperCase() }}
              </span>
            </UAvatar>
            <!-- Linked indicator -->
            <span
              v-if="member.is_linked"
              class="absolute -bottom-0.5 -right-0.5 size-3 bg-success-500 rounded-full border-2 border-white dark:border-neutral-800"
              :title="$t('organizations.team.linkedAccount')"
            />
          </div>

          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <span
                class="text-sm font-medium truncate"
                :class="selectedMemberId === member.id
                  ? 'text-brand-700 dark:text-brand-300'
                  : 'text-neutral-900 dark:text-neutral-100'"
              >
                {{ member.username || 'Unknown' }}
              </span>
              <UBadge
                v-if="member.role === 'admin'"
                color="warning"
                variant="subtle"
                size="xs"
              >
                {{ $t('organizations.team.admin') }}
              </UBadge>
            </div>
            <div
              v-if="!hasSelectedMember"
              class="flex items-center gap-2 mt-0.5"
            >
              <span
                class="text-xs truncate"
                :class="member.reviewate_enabled
                  ? 'text-success-600 dark:text-success-400'
                  : 'text-neutral-400 dark:text-neutral-500'"
              >
                {{ member.reviewate_enabled ? $t('organizations.team.enabled') : $t('organizations.team.disabled') }}
              </span>
            </div>
          </div>
          <UIcon
            name="i-lucide-settings"
            class="size-4 text-neutral-300 dark:text-neutral-500 group-hover:text-neutral-500 dark:group-hover:text-neutral-300 group-hover:rotate-45 transition-all duration-300 ease-out shrink-0"
          />
        </button>
      </div>

      <!-- No Search Results -->
      <div
        v-else-if="searchQuery && members.length > 0"
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

      <!-- Empty State (No Members) -->
      <div
        v-else
        class="flex flex-col items-center justify-center py-12 px-4"
      >
        <div class="size-12 flex items-center justify-center rounded-full bg-neutral-100 dark:bg-neutral-700 mb-3">
          <UIcon
            name="i-lucide-users"
            class="size-6 text-neutral-400"
          />
        </div>
        <p class="text-sm font-medium text-neutral-900 dark:text-neutral-100 mb-1">
          {{ $t('organizations.team.noMembers') }}
        </p>
        <p class="text-xs text-neutral-500 dark:text-neutral-400 text-center">
          {{ $t('organizations.team.noMembersDescription') }}
        </p>
      </div>
    </div>
  </div>
</template>
