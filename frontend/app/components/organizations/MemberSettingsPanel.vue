<script setup lang="ts">
/**
 * Member Settings Panel Component
 *
 * Displays member details and settings form.
 */
import type { MemberListItem } from '@reviewate/api-types'
import { updateOrganizationMember } from '@reviewate/api-types'

const props = defineProps<{
  member: MemberListItem
  organizationId: string
  isAdmin: boolean
  currentUserMemberId: string | null
}>()

// Can edit if admin OR if editing own settings
const canEdit = computed(() => {
  return props.isAdmin || props.member.id === props.currentUserMemberId
})

const emit = defineEmits<{
  close: []
  updated: [member: MemberListItem]
}>()

const { t } = useI18n()
const client = useApi()
const toast = useToast()

// Form state
const isSaving = ref(false)
const error = ref<string | null>(null)
const reviewateEnabled = ref(props.member.reviewate_enabled)

// Watch for member changes
watch(() => props.member, (newMember) => {
  reviewateEnabled.value = newMember.reviewate_enabled
})

// Track changes
const hasChanges = computed(() => {
  return reviewateEnabled.value !== props.member.reviewate_enabled
})

async function saveSettings() {
  isSaving.value = true
  error.value = null

  const { data, error: apiError, response } = await updateOrganizationMember({
    client,
    path: { org_id: props.organizationId, member_id: props.member.id },
    body: {
      reviewate_enabled: reviewateEnabled.value,
    },
  })

  if (apiError) {
    if (response.status === 403) {
      error.value = t('organizations.settings.adminRequired')
    } else {
      toast.add({ title: t('organizations.settings.saveFailed'), color: 'error' })
    }
  } else if (data) {
    emit('updated', data)
    toast.add({ title: t('organizations.settings.settingsSaved'), color: 'success' })
  }

  isSaving.value = false
}
</script>

<template>
  <div class="h-full flex flex-col overflow-hidden">
    <!-- Member Settings Header -->
    <div class="flex items-center justify-between px-6 py-4 border-b border-neutral-200 dark:border-neutral-700 shrink-0 bg-white dark:bg-neutral-800">
      <div class="flex items-center gap-3">
        <button
          type="button"
          class="cursor-pointer p-1.5 rounded-md hover:bg-neutral-100 dark:hover:bg-neutral-700 transition-all duration-200 ease-out hover:scale-110 active:scale-95"
          @click="emit('close')"
        >
          <UIcon
            name="i-lucide-x"
            class="size-4 text-neutral-500"
          />
        </button>
        <div class="flex items-center gap-3">
          <!-- Avatar -->
          <UAvatar
            :src="member.avatar_url || undefined"
            :alt="member.username || 'Member'"
            size="md"
          >
            <span class="text-sm font-medium text-neutral-600 dark:text-neutral-300">
              {{ (member.username ?? '?').charAt(0).toUpperCase() }}
            </span>
          </UAvatar>
          <div>
            <h3 class="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
              {{ member.username || 'Unknown' }}
            </h3>
            <div class="flex items-center gap-2 mt-0.5">
              <UBadge
                :color="member.role === 'admin' ? 'warning' : 'neutral'"
                variant="subtle"
                size="xs"
              >
                {{ member.role === 'admin' ? $t('organizations.team.admin') : $t('organizations.team.member') }}
              </UBadge>
              <UBadge
                v-if="member.is_linked"
                color="success"
                variant="subtle"
                size="xs"
              >
                {{ $t('organizations.team.linkedAccount') }}
              </UBadge>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Member Settings Content -->
    <div class="flex-1 overflow-y-auto p-6 space-y-6">
      <!-- Reviewate Settings -->
      <div class="space-y-4">
        <h4 class="text-sm font-semibold text-neutral-900 dark:text-neutral-100 flex items-center gap-2">
          <UIcon
            name="i-lucide-settings"
            class="size-4"
          />
          {{ $t('organizations.team.settingsTitle') }}
        </h4>
        <UCard>
          <div class="space-y-4">
            <p class="text-xs text-neutral-500 dark:text-neutral-400">
              {{ $t('organizations.team.settingsDescription') }}
            </p>

            <!-- Reviewate Enabled Toggle -->
            <div class="flex items-center justify-between">
              <div>
                <p class="text-sm font-medium text-neutral-900 dark:text-neutral-100">
                  {{ $t('organizations.team.reviewateEnabled') }}
                </p>
                <p class="text-xs text-neutral-500 dark:text-neutral-400">
                  {{ $t('organizations.team.reviewateEnabledDescription') }}
                </p>
              </div>
              <USwitch
                v-model="reviewateEnabled"
                :disabled="!canEdit"
              />
            </div>

            <!-- Error Alert -->
            <ErrorAlert
              :error="error"
              @dismiss="error = null"
            />

            <!-- Save Button -->
            <div
              v-if="canEdit"
              class="flex justify-end pt-2"
            >
              <AppButton
                color="primary"
                size="sm"
                :processing="isSaving"
                :disabled="!hasChanges"
                icon="i-lucide-check"
                @click="saveSettings"
              >
                {{ $t('common.save') }}
              </AppButton>
            </div>

            <!-- Read-only message for non-admins viewing others -->
            <p
              v-else
              class="text-xs text-neutral-400 dark:text-neutral-500 text-center"
            >
              {{ $t('organizations.team.adminOnlyMessage') }}
            </p>
          </div>
        </UCard>
      </div>

      <!-- Member Info -->
      <div class="space-y-4">
        <h4 class="text-sm font-semibold text-neutral-900 dark:text-neutral-100 flex items-center gap-2">
          <UIcon
            name="i-lucide-info"
            class="size-4"
          />
          {{ $t('organizations.team.memberInfo') }}
        </h4>
        <UCard>
          <div class="space-y-3">
            <div class="flex items-center justify-between">
              <span class="text-sm text-neutral-500 dark:text-neutral-400">
                {{ $t('organizations.team.accountStatus') }}
              </span>
              <span class="text-sm text-neutral-900 dark:text-neutral-100">
                {{ member.is_linked ? $t('organizations.team.linked') : $t('organizations.team.notLinked') }}
              </span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-sm text-neutral-500 dark:text-neutral-400">
                {{ $t('organizations.team.role') }}
              </span>
              <span class="text-sm text-neutral-900 dark:text-neutral-100 capitalize">
                {{ member.role }}
              </span>
            </div>
          </div>
        </UCard>
      </div>
    </div>
  </div>
</template>
