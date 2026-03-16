<script setup lang="ts">
/**
 * Repository Settings Panel Component
 *
 * Displays repository details and settings form with inheritance support.
 */
import type { RepositoryListItem } from '@reviewate/api-types'
import { getRepositorySettings, updateRepositorySettings } from '@reviewate/api-types'

import { getProviderIcon } from '~/utils/organization'

const props = defineProps<{
  repository: RepositoryListItem
  isDeleting: boolean
  isAdmin?: boolean
}>()

const emit = defineEmits<{
  close: []
  delete: [repo: RepositoryListItem]
}>()

const { form, isLoading, isSaving, hasChanges, saveSettings } = useSettingsForm({
  entityId: computed(() => props.repository.id),
  defaultValue: null,
  load: async (client, id) => getRepositorySettings({ client, path: { repo_id: id } }),
  save: async (client, id, body) => updateRepositorySettings({ client, path: { repo_id: id }, body }),
})

const { triggerOptions, summaryTriggerOptions } = useTriggerOptions({ includeInherit: true })
</script>

<template>
  <div class="h-full flex flex-col overflow-hidden">
    <!-- Repo Settings Header -->
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
        <div>
          <h3 class="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
            {{ repository.name }}
          </h3>
          <div class="flex items-center gap-2 mt-0.5">
            <UIcon
              :name="getProviderIcon(repository.provider)"
              class="size-3 text-neutral-400"
            />
            <span class="text-xs text-neutral-500 dark:text-neutral-400">
              {{ repository.provider }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Repo Settings Content -->
    <div class="flex-1 overflow-y-auto p-6 space-y-6">
      <!-- Repository Settings -->
      <div class="space-y-4">
        <h4 class="text-sm font-semibold text-neutral-900 dark:text-neutral-100 flex items-center gap-2">
          <UIcon
            name="i-lucide-settings"
            class="size-4"
          />
          {{ $t('organizations.repositories.settingsTitle') }}
        </h4>
        <UCard>
          <template v-if="isLoading">
            <div class="flex items-center justify-center py-8">
              <UIcon
                name="i-lucide-loader-2"
                class="size-6 animate-spin text-neutral-400"
              />
            </div>
          </template>
          <template v-else>
            <div class="space-y-4">
              <p class="text-xs text-neutral-500 dark:text-neutral-400">
                {{ $t('organizations.repositories.settingsDescription') }}
              </p>

              <!-- Automatic Review Trigger -->
              <UFormField
                :label="$t('organizations.settings.automaticReviewTrigger')"
                name="trigger"
              >
                <USelect
                  v-model="form.automatic_review_trigger"
                  :items="triggerOptions"
                  value-key="value"
                  class="w-full"
                  :disabled="!isAdmin"
                />
              </UFormField>

              <!-- Automatic Summary Trigger -->
              <UFormField
                :label="$t('organizations.settings.automaticSummaryTrigger')"
                name="summary"
              >
                <USelect
                  v-model="form.automatic_summary_trigger"
                  :items="summaryTriggerOptions"
                  value-key="value"
                  class="w-full"
                  :disabled="!isAdmin"
                />
              </UFormField>

              <!-- Save Button (admin only) -->
              <div
                v-if="isAdmin"
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
            </div>
          </template>
        </UCard>
      </div>

      <!-- Linked Repositories -->
      <LinkedReposList
        :repository-id="repository.id"
        :description="$t('organizations.linkedRepos.repoDescription')"
        :is-admin="isAdmin"
      />

      <!-- Danger Zone (admin only) -->
      <div
        v-if="isAdmin"
        class="space-y-4"
      >
        <h4 class="text-sm font-semibold text-error-600 dark:text-error-400 flex items-center gap-2">
          <UIcon
            name="i-lucide-alert-triangle"
            class="size-4"
          />
          {{ $t('organizations.settings.dangerZone') }}
        </h4>
        <UCard class="border-error-200 dark:border-error-800">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm font-medium text-neutral-900 dark:text-neutral-100">
                {{ $t('organizations.repositories.removeRepository') }}
              </p>
              <p class="text-xs text-neutral-500 dark:text-neutral-400">
                {{ $t('organizations.repositories.removeRepositoryDescription') }}
              </p>
            </div>
            <UButton
              color="error"
              variant="soft"
              size="sm"
              :loading="isDeleting"
              @click="emit('delete', repository)"
            >
              {{ $t('common.remove') }}
            </UButton>
          </div>
        </UCard>
      </div>
    </div>
  </div>
</template>
