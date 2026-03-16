<script setup lang="ts">
import type { MemberListItem } from '@reviewate/api-types'

const props = defineProps<{
  members: MemberListItem[]
  selectedMember: MemberListItem | null
  organizationId: string
  isLoading: boolean
  isAdmin: boolean
  currentUserMemberId: string | null
}>()

const emit = defineEmits<{
  selectMember: [member: MemberListItem | null]
  memberUpdated: [member: MemberListItem]
}>()

const hasSelectedMember = computed(() => !!props.selectedMember)
</script>

<template>
  <SplitDetailLayout :has-selection="hasSelectedMember">
    <template #list>
      <MemberList
        :members="members"
        :selected-member-id="selectedMember?.id ?? null"
        :has-selected-member="hasSelectedMember"
        :is-loading="isLoading"
        @select="emit('selectMember', $event)"
      />
    </template>

    <template #detail>
      <MemberSettingsPanel
        v-if="selectedMember"
        :member="selectedMember"
        :organization-id="organizationId"
        :is-admin="isAdmin"
        :current-user-member-id="currentUserMemberId"
        @close="emit('selectMember', null)"
        @updated="emit('memberUpdated', $event)"
      />
    </template>
  </SplitDetailLayout>
</template>
