<script setup lang="ts">
import type { MemberListItem, OrganizationListItem, RepositoryListItem } from '@reviewate/api-types'

/**
 * Organization settings content: header + tabs + tab content.
 * Used in tour, desktop, and mobile layouts to avoid triplication.
 */
defineProps<{
  organization: OrganizationListItem
  repositories: RepositoryListItem[]
  selectedRepo: RepositoryListItem | null
  isRepoLoading: boolean
  isRepoDeleting: boolean
  isAdmin: boolean
  members: MemberListItem[]
  selectedMember: MemberListItem | null
  organizationId: string
  isMembersLoading: boolean
  currentUserMemberId: string | null
  readonly?: boolean
  hideHeader?: boolean
}>()

const activeTab = defineModel<string>('activeTab', { required: true })

const emit = defineEmits<{
  delete: [org: OrganizationListItem]
  selectRepo: [repo: RepositoryListItem | null]
  deleteRepo: [repo: RepositoryListItem]
  selectMember: [member: MemberListItem | null]
  memberUpdated: [member: MemberListItem]
}>()
</script>

<template>
  <OrgHeader
    v-if="!hideHeader"
    :organization="organization"
  />

  <div
    :id="readonly && activeTab !== 'general' ? `tour-${activeTab}-content` : undefined"
    class="flex flex-col flex-1 min-h-0"
  >
    <OrgSettingsTabs v-model="activeTab" />

    <div
      class="flex-1"
      :class="readonly ? 'overflow-y-auto pointer-events-none' : 'overflow-hidden'"
    >
      <OrgGeneralTab
        v-if="activeTab === 'general'"
        :organization="organization"
        :is-admin="isAdmin"
        @delete="emit('delete', $event)"
      />

      <OrgReposTab
        v-else-if="activeTab === 'repositories'"
        :repositories="repositories"
        :selected-repo="selectedRepo"
        :is-loading="isRepoLoading"
        :is-deleting="isRepoDeleting"
        :is-admin="isAdmin"
        @select-repo="emit('selectRepo', $event)"
        @delete-repo="emit('deleteRepo', $event)"
      />

      <OrgTeamTab
        v-else-if="activeTab === 'team'"
        :members="members"
        :selected-member="selectedMember"
        :organization-id="organizationId"
        :is-loading="isMembersLoading"
        :is-admin="isAdmin"
        :current-user-member-id="currentUserMemberId"
        @select-member="emit('selectMember', $event)"
        @member-updated="emit('memberUpdated', $event)"
      />
    </div>
  </div>
</template>
