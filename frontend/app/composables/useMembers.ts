/**
 * Composable for managing organization member state
 * Extracts member fetching, selection, and computed properties
 */

import type { MemberListItem } from '@reviewate/api-types'
import { listOrganizationMembers } from '@reviewate/api-types'

export function useMembers(orgId: Ref<string | null>) {
  const client = useApi()
  const authStore = useAuthStore()
  const orgsStore = useOrganizationsStore()

  const members = ref<MemberListItem[]>([])
  const selectedMemberId = ref<string | null>(null)
  const isMembersLoading = ref(false)

  const selectedMember = computed(() =>
    members.value.find((m) => m.id === selectedMemberId.value) ?? null,
  )

  const isOrgAdmin = computed(() => {
    return orgsStore.selectedOrg?.role === 'admin'
  })

  const currentUserMemberId = computed(() => {
    const org = orgsStore.selectedOrg
    if (!authStore.user || !org) return null

    const username = org.provider === 'github'
      ? authStore.user.github_username
      : authStore.user.gitlab_username

    if (!username) return null

    const currentMember = members.value.find(
      (m) => m.is_linked && m.username === username,
    )
    return currentMember?.id ?? null
  })

  function selectMember(member: MemberListItem | null) {
    selectedMemberId.value = member?.id ?? null
  }

  function handleMemberUpdated(updatedMember: MemberListItem) {
    const index = members.value.findIndex((m) => m.id === updatedMember.id)
    if (index !== -1) {
      members.value[index] = updatedMember
    }
  }

  // Fetch members when org changes
  watch(orgId, async (id) => {
    if (!id) {
      members.value = []
      selectedMemberId.value = null
      return
    }

    isMembersLoading.value = true
    const { data } = await listOrganizationMembers({
      client,
      path: { org_id: id },
    })
    if (data) {
      members.value = data.objects
    }
    isMembersLoading.value = false
  }, { immediate: true })

  return {
    members,
    selectedMember,
    isMembersLoading,
    isOrgAdmin,
    currentUserMemberId,
    selectMember,
    handleMemberUpdated,
  }
}
