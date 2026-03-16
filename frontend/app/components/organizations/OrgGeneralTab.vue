<script setup lang="ts">
/**
 * Organization General Settings Tab Component
 *
 * Displays general organization settings and review settings form.
 * Uses base SettingSection and SettingRow components for consistent layout.
 */
import type { OrganizationListItem } from '@reviewate/api-types'
import { getOrganizationSettings, updateOrganizationSettings } from '@reviewate/api-types'

const props = defineProps<{
  organization: OrganizationListItem
  isDeleting?: boolean
  isAdmin?: boolean
}>()

const emit = defineEmits<{
  delete: [org: OrganizationListItem]
}>()

const { form, isLoading, isSaving, hasChanges, saveSettings } = useSettingsForm({
  entityId: computed(() => props.organization.id),
  defaultValue: 'none' as const,
  load: async (client, id) => getOrganizationSettings({ client, path: { org_id: id } }),
  save: async (client, id, body) => updateOrganizationSettings({ client, path: { org_id: id }, body }),
})

const { triggerOptions, summaryTriggerOptions } = useTriggerOptions()
</script>

<template>
  <div class="p-6 overflow-y-auto h-full">
    <div class="space-y-6">
      <!-- Review Settings -->
      <SettingSection
        id="tour-general-settings"
        :title="$t('organizations.settings.reviewSettings')"
        icon="i-lucide-git-pull-request"
      >
        <template v-if="isLoading">
          <div class="flex items-center justify-center py-8">
            <UIcon
              name="i-lucide-loader-2"
              class="size-6 animate-spin text-neutral-400"
            />
          </div>
        </template>
        <template v-else>
          <!-- Automatic Review Trigger -->
          <SettingRow
            :label="$t('organizations.settings.automaticReviewTrigger')"
            :description="$t('organizations.settings.automaticReviewTriggerDescription')"
          >
            <USelect
              v-model="form.automatic_review_trigger"
              :items="triggerOptions"
              value-key="value"
              class="w-48"
              :disabled="!isAdmin"
            />
          </SettingRow>

          <USeparator />

          <!-- Automatic Summary Trigger -->
          <SettingRow
            :label="$t('organizations.settings.automaticSummaryTrigger')"
            :description="$t('organizations.settings.automaticSummaryTriggerDescription')"
          >
            <USelect
              v-model="form.automatic_summary_trigger"
              :items="summaryTriggerOptions"
              value-key="value"
              class="w-48"
              :disabled="!isAdmin"
            />
          </SettingRow>

          <USeparator />

          <!-- Save Button -->
          <div
            v-if="isAdmin"
            class="flex justify-end"
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
        </template>
      </SettingSection>

      <!-- Linked Repositories -->
      <LinkedReposList
        :organization-id="organization.id"
        :description="$t('organizations.linkedRepos.orgDescription')"
        :is-admin="isAdmin"
      />

      <!-- Danger Zone (admin only) -->
      <SettingSection
        v-if="isAdmin"
        :title="$t('organizations.settings.dangerZone')"
        icon="i-lucide-alert-triangle"
        danger
      >
        <SettingRow
          :label="$t('organizations.settings.removeOrganization')"
          :description="$t('organizations.settings.removeOrganizationDescription')"
        >
          <UButton
            color="error"
            variant="soft"
            size="sm"
            :loading="isDeleting"
            @click="emit('delete', organization)"
          >
            {{ $t('common.remove') }}
          </UButton>
        </SettingRow>
      </SettingSection>
    </div>
  </div>
</template>
