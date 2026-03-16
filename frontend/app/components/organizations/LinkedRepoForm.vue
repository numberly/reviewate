<script setup lang="ts">
/**
 * LinkedRepoForm Component
 *
 * Two-input form for adding linked repositories.
 * URL input for the repo, branch input for the target branch.
 */
import type { LinkedRepositoryCreate } from '@reviewate/api-types'

const emit = defineEmits<{
  submit: [data: LinkedRepositoryCreate]
  cancel: []
}>()

defineProps<{
  isSubmitting?: boolean
}>()

// Form state
const url = ref('')
const branch = ref('')

function isValidUrl(urlStr: string): boolean {
  try {
    const parsed = new URL(urlStr.trim())
    return parsed.protocol === 'http:' || parsed.protocol === 'https:'
  } catch {
    return false
  }
}

const isValid = computed(() => isValidUrl(url.value) && branch.value.trim().length > 0)

function handleSubmit() {
  if (!isValid.value) return

  emit('submit', {
    url: url.value.trim(),
    branch: branch.value.trim(),
  })
}

function reset() {
  url.value = ''
  branch.value = ''
}

defineExpose({ reset })
</script>

<template>
  <form
    class="space-y-4"
    @submit.prevent="handleSubmit"
  >
    <!-- URL + Branch Inputs -->
    <div class="flex gap-3">
      <UFormField
        :label="$t('organizations.linkedRepos.urlLabel')"
        name="url"
        required
        class="grow"
      >
        <UInput
          v-model="url"
          :placeholder="$t('organizations.linkedRepos.urlPlaceholder')"
          class="w-full"
          type="url"
        />
      </UFormField>

      <UFormField
        :label="$t('organizations.linkedRepos.branchLabel')"
        name="branch"
        required
        class="w-48"
      >
        <UInput
          v-model="branch"
          :placeholder="$t('organizations.linkedRepos.branchPlaceholder')"
          class="w-full"
        />
      </UFormField>
    </div>

    <!-- Actions -->
    <div class="flex justify-end gap-2 pt-2">
      <UButton
        variant="ghost"
        size="sm"
        @click="emit('cancel')"
      >
        {{ $t('common.cancel') }}
      </UButton>
      <AppButton
        type="submit"
        color="primary"
        size="sm"
        :processing="isSubmitting"
        :disabled="!isValid"
        icon="i-lucide-plus"
      >
        {{ $t('organizations.linkedRepos.addLinkedRepo') }}
      </AppButton>
    </div>
  </form>
</template>
