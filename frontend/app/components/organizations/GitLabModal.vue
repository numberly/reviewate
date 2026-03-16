<script setup lang="ts">
/**
 * GitLab Token Modal Component
 *
 * Modal for adding GitLab organizations via personal access token.
 */
import { required, url as urlValidator } from '~/utils/validators'

const props = defineProps<{
  open: boolean
  isLoading: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'submit': [token: string, url: string]
}>()

const { t } = useI18n()
const configStore = useConfigStore()

const form = ref({
  token: '',
  url: configStore.gitLabUrl,
})

const { getError, touch, validateAll, reset } = useFormValidation(form, {
  token: [required(t('validation.required'))],
  url: [required(t('validation.required')), urlValidator(t('validation.invalidUrl'))],
})

function handleSubmit() {
  if (!validateAll()) return
  emit('submit', form.value.token.trim(), form.value.url.trim())
}

function handleClose() {
  emit('update:open', false)
}

// Reset form when modal closes
watch(() => props.open, (isOpen) => {
  if (!isOpen) {
    form.value.token = ''
    form.value.url = configStore.gitLabUrl
    reset()
  }
})
</script>

<template>
  <UModal
    :open="open"
    @update:open="emit('update:open', $event)"
  >
    <template #header>
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <div class="flex size-7 items-center justify-center rounded-full bg-primary-100 dark:bg-primary-900/30">
            <UIcon
              name="i-simple-icons-gitlab"
              class="size-4 text-primary-600 dark:text-primary-400"
            />
          </div>
          <h3 class="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
            {{ $t('organizations.gitlabTokenTitle') }}
          </h3>
        </div>
        <UButton
          color="neutral"
          variant="ghost"
          size="xs"
          icon="i-lucide-x"
          @click="handleClose"
        />
      </div>
    </template>

    <template #body>
      <div class="space-y-4">
        <p class="text-sm text-neutral-500 dark:text-neutral-400">
          {{ $t('organizations.gitlabTokenDescription') }}
        </p>

        <!-- Token Input -->
        <UFormField
          :label="$t('organizations.gitlabTokenLabel')"
          name="token"
          :error="getError('token')"
        >
          <UInput
            v-model="form.token"
            type="password"
            :placeholder="$t('organizations.gitlabTokenPlaceholder')"
            icon="i-lucide-key"
            @blur="touch('token')"
          />
        </UFormField>

        <!-- URL Input -->
        <UFormField
          :label="$t('organizations.gitlabUrlLabel')"
          name="url"
          :error="getError('url')"
        >
          <UInput
            v-model="form.url"
            type="url"
            :placeholder="$t('organizations.gitlabUrlPlaceholder')"
            icon="i-lucide-globe"
            @blur="touch('url')"
          />
        </UFormField>
      </div>
    </template>

    <template #footer>
      <UButton
        color="neutral"
        variant="ghost"
        size="sm"
        @click="handleClose"
      >
        {{ $t('common.cancel') }}
      </UButton>
      <UButton
        color="primary"
        size="sm"
        :loading="isLoading"
        :disabled="!form.token.trim()"
        @click="handleSubmit"
      >
        {{ $t('common.add') }}
      </UButton>
    </template>
  </UModal>
</template>
