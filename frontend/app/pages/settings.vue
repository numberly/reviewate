<script setup lang="ts">
/**
 * User Settings Page
 *
 * Single scrollable page with all settings sections.
 */
import { disconnectProvider, updateProfile } from '@reviewate/api-types'

import { email as emailValidator } from '~/utils/validators'

const { t } = useI18n()
const route = useRoute()
const client = useApi()
const toast = useToast()
const authStore = useAuthStore()
const configStore = useConfigStore()
const config = useRuntimeConfig()

useHead({
  title: () => `${t('settings.title')} - Reviewate`,
})

// Show skeletons until hydration completes and auth is ready
// Server and client both start with true, then client sets false after mount
const isHydrated = ref(false)
onMounted(() => {
  isHydrated.value = true
})
const showSkeleton = computed(() => !isHydrated.value || !authStore.isInitialized)

// Loading states
const disconnectingProvider = ref<string | null>(null)
const isSavingProfile = ref(false)

// Profile form state
const profileForm = ref({
  email: authStore.user?.email || '',
})
const originalEmail = ref(authStore.user?.email || '')

// Email validation
const { getError: getProfileError, touch: touchProfile, validateAll: validateProfile, reset: resetProfileValidation } = useFormValidation(profileForm, {
  email: [emailValidator(t('validation.invalidEmail'))],
})

const hasProfileChanges = computed(() =>
  profileForm.value.email !== originalEmail.value,
)

// Update form when user changes
watch(() => authStore.user, (user) => {
  if (user) {
    profileForm.value.email = user.email || ''
    originalEmail.value = user.email || ''
    resetProfileValidation()
  }
}, { immediate: true })

// Allowed OAuth providers for validation
const ALLOWED_PROVIDERS = ['github', 'gitlab', 'google'] as const

// Check for link success/error from query params
onMounted(() => {
  const linked = route.query.linked as string
  const errorParam = route.query.error as string

  // Validate linked parameter against allowed providers
  if (linked && ALLOWED_PROVIDERS.includes(linked as typeof ALLOWED_PROVIDERS[number])) {
    toast.add({ title: t('settings.accounts.linked', { provider: linked }), color: 'success' })
    navigateTo('/settings', { replace: true })
  } else if (errorParam === 'already_linked') {
    toast.add({ title: t('settings.accounts.alreadyLinked'), color: 'error' })
    navigateTo('/settings', { replace: true })
  } else if (errorParam === 'account_in_use') {
    toast.add({ title: t('settings.accounts.accountInUse'), color: 'error' })
    navigateTo('/settings', { replace: true })
  }
})

// Provider list with connection status and enabled state
const providers = computed(() => [
  {
    id: 'github',
    name: 'GitHub',
    icon: 'i-simple-icons-github',
    connected: authStore.hasLinkedProvider('github'),
    username: authStore.user?.github_username,
    enabled: configStore.isGitHubEnabled,
  },
  {
    id: 'gitlab',
    name: 'GitLab',
    icon: 'i-simple-icons-gitlab',
    connected: authStore.hasLinkedProvider('gitlab'),
    username: authStore.user?.gitlab_username,
    enabled: configStore.isGitLabEnabled,
  },
  {
    id: 'google',
    name: 'Google',
    icon: 'i-simple-icons-google',
    connected: authStore.hasLinkedProvider('google'),
    username: null,
    enabled: configStore.isGoogleEnabled,
  },
])

const connectedCount = computed(() =>
  providers.value.filter((p) => p.connected).length,
)

const canDisconnect = computed(() => connectedCount.value > 1)

function connectProvider(providerId: string) {
  // Validate provider ID to prevent open redirect
  if (!ALLOWED_PROVIDERS.includes(providerId as typeof ALLOWED_PROVIDERS[number])) {
    toast.add({ title: t('settings.accounts.invalidProvider'), color: 'error' })
    return
  }
  const baseUrl = config.public.apiBase
  window.location.href = `${baseUrl}/auth/link/${providerId}`
}

async function handleDisconnect(providerId: string) {
  if (!canDisconnect.value) {
    toast.add({ title: t('settings.accounts.cannotDisconnectLast'), color: 'error' })
    return
  }

  disconnectingProvider.value = providerId

  const { data, error: apiError } = await disconnectProvider({
    client,
    path: { provider: providerId as 'github' | 'gitlab' | 'google' },
  })

  if (apiError) {
    toast.add({ title: t('settings.accounts.disconnectFailed'), color: 'error' })
  } else if (data) {
    toast.add({ title: t('settings.accounts.disconnected', { provider: providerId }), color: 'success' })
    await authStore.fetchUser()
  }

  disconnectingProvider.value = null
}

async function saveProfile() {
  if (!validateProfile()) return

  isSavingProfile.value = true

  const { data, error: apiError } = await updateProfile({
    client,
    body: {
      email: profileForm.value.email || null,
    },
  })

  if (apiError) {
    toast.add({ title: t('settings.profile.saveFailed'), color: 'error' })
  } else if (data) {
    await authStore.fetchUser()
    toast.add({ title: t('settings.profile.saved'), color: 'success' })
  }

  isSavingProfile.value = false
}
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Page Header -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 pb-6 border-b border-neutral-200 dark:border-neutral-700 shrink-0">
      <div class="flex flex-col gap-0.5">
        <p class="text-xl sm:text-2xl font-semibold text-neutral-900 dark:text-neutral-100 tracking-tight">
          {{ $t('settings.title') }}
        </p>
        <p class="text-sm text-neutral-500 dark:text-neutral-400">
          {{ $t('settings.subtitle') }}
        </p>
      </div>
    </div>

    <!-- Settings Content - Scrollable -->
    <div class="flex-1 overflow-y-auto space-y-6">
      <!-- Skeletons while loading -->
      <template v-if="showSkeleton">
        <!-- Connected Accounts Skeleton -->
        <div class="rounded-lg border border-neutral-200 dark:border-neutral-700 p-6 space-y-4">
          <div class="flex items-center gap-2">
            <div class="size-5 bg-neutral-200 dark:bg-neutral-700 rounded animate-pulse" />
            <div class="h-5 w-40 bg-neutral-200 dark:bg-neutral-700 rounded animate-pulse" />
          </div>
          <div class="space-y-3">
            <div
              v-for="i in 3"
              :key="i"
              class="flex items-center justify-between p-4 rounded-lg border border-neutral-200 dark:border-neutral-700"
            >
              <div class="flex items-center gap-3">
                <div class="size-10 bg-neutral-100 dark:bg-neutral-800 rounded-lg animate-pulse" />
                <div class="space-y-2">
                  <div class="h-4 w-20 bg-neutral-200 dark:bg-neutral-700 rounded animate-pulse" />
                  <div class="h-3 w-28 bg-neutral-100 dark:bg-neutral-800 rounded animate-pulse" />
                </div>
              </div>
              <div class="h-8 w-24 bg-neutral-100 dark:bg-neutral-800 rounded animate-pulse" />
            </div>
          </div>
        </div>

        <!-- Profile Skeleton -->
        <div class="rounded-lg border border-neutral-200 dark:border-neutral-700 p-6 space-y-4">
          <div class="flex items-center gap-2">
            <div class="size-5 bg-neutral-200 dark:bg-neutral-700 rounded animate-pulse" />
            <div class="h-5 w-24 bg-neutral-200 dark:bg-neutral-700 rounded animate-pulse" />
          </div>
          <div class="space-y-4">
            <div class="space-y-2">
              <div class="h-4 w-32 bg-neutral-200 dark:bg-neutral-700 rounded animate-pulse" />
              <div class="h-10 w-full max-w-md bg-neutral-100 dark:bg-neutral-800 rounded animate-pulse" />
            </div>
            <div class="h-px bg-neutral-200 dark:bg-neutral-700" />
            <div class="space-y-2">
              <div class="h-4 w-16 bg-neutral-200 dark:bg-neutral-700 rounded animate-pulse" />
              <div class="h-10 w-full max-w-md bg-neutral-100 dark:bg-neutral-800 rounded animate-pulse" />
            </div>
          </div>
        </div>
      </template>

      <!-- Actual Content -->
      <template v-else>
        <!-- Connected Accounts Section -->
        <SettingSection
          :title="$t('settings.accounts.title')"
          icon="i-lucide-link"
        >
          <div class="space-y-3">
            <div
              v-for="provider in providers"
              :key="provider.id"
              class="flex items-center justify-between p-4 rounded-lg border border-neutral-200 dark:border-neutral-700"
            >
              <div class="flex items-center gap-3">
                <div class="size-10 flex items-center justify-center rounded-lg bg-neutral-100 dark:bg-neutral-700">
                  <UIcon
                    :name="provider.icon"
                    class="size-5"
                  />
                </div>
                <div>
                  <p class="text-sm font-medium text-neutral-900 dark:text-neutral-100">
                    {{ provider.name }}
                  </p>
                  <p class="text-xs text-neutral-500 dark:text-neutral-400">
                    {{ provider.connected
                      ? (provider.username || $t('settings.accounts.connected'))
                      : $t('settings.accounts.notConnected')
                    }}
                  </p>
                </div>
              </div>

              <AppButton
                v-if="provider.connected"
                color="neutral"
                size="sm"
                icon="i-lucide-unlink"
                :processing="disconnectingProvider === provider.id"
                :disabled="!canDisconnect || !provider.enabled"
                @click="handleDisconnect(provider.id)"
              >
                {{ $t('settings.accounts.disconnect') }}
              </AppButton>
              <AppButton
                v-else
                color="primary"
                size="sm"
                icon="i-lucide-plug"
                :disabled="!provider.enabled"
                @click="connectProvider(provider.id)"
              >
                {{ $t('settings.accounts.connect') }}
              </AppButton>
            </div>
          </div>

          <p
            v-if="connectedCount === 1"
            class="text-xs text-neutral-500 dark:text-neutral-400"
          >
            {{ $t('settings.accounts.lastAccountWarning') }}
          </p>
        </SettingSection>

        <!-- Profile Section -->
        <SettingSection
          :title="$t('settings.profile.title')"
          icon="i-lucide-user"
        >
          <!-- Display Name (read-only) -->
          <UFormField
            :label="$t('settings.profile.displayName')"
            :description="$t('settings.profile.displayNameDescription')"
            name="displayName"
          >
            <UInput
              :model-value="authStore.user?.display_username || ''"
              disabled
              class="w-full max-w-md"
            />
          </UFormField>

          <USeparator />

          <!-- Email -->
          <UFormField
            :label="$t('settings.profile.email')"
            :description="$t('settings.profile.emailDescription')"
            name="email"
            :error="getProfileError('email')"
          >
            <UInput
              v-model="profileForm.email"
              type="email"
              class="w-full max-w-md"
              @blur="touchProfile('email')"
            />
          </UFormField>

          <USeparator />

          <!-- Save Button -->
          <div class="flex justify-end">
            <AppButton
              color="primary"
              size="sm"
              :processing="isSavingProfile"
              :disabled="!hasProfileChanges"
              icon="i-lucide-check"
              @click="saveProfile"
            >
              {{ $t('common.save') }}
            </AppButton>
          </div>
        </SettingSection>
      </template>
    </div>
  </div>
</template>
