<script setup lang="ts">
/**
 * Login Page
 *
 * SSO-only authentication page supporting GitHub, GitLab, and Google.
 * Uses OAuth flow handled by backend - redirects to provider then back with session cookie.
 */
definePageMeta({
  layout: 'auth',
})

const { t } = useI18n()
const authStore = useAuthStore()
const configStore = useConfigStore()

useHead({
  title: () => `${t('auth.login.title')} - Reviewate`,
})

// Track loading state per provider for visual feedback
const loadingProvider = ref<'github' | 'gitlab' | 'google' | null>(null)

/**
 * Initiate SSO login flow
 */
function handleLogin(provider: 'github' | 'gitlab' | 'google') {
  loadingProvider.value = provider
  authStore.login(provider)
}

// SSO Provider configuration
const ssoProviders = [
  {
    id: 'github' as const,
    icon: 'i-simple-icons-github',
    labelKey: 'auth.continueWithGithub',
  },
  {
    id: 'gitlab' as const,
    icon: 'i-simple-icons-gitlab',
    labelKey: 'auth.continueWithGitlab',
  },
  {
    id: 'google' as const,
    icon: 'i-simple-icons-google',
    labelKey: 'auth.continueWithGoogle',
  },
]

// Check if provider is enabled
function isProviderEnabled(providerId: 'github' | 'gitlab' | 'google'): boolean {
  if (providerId === 'github') return configStore.isGitHubEnabled
  if (providerId === 'gitlab') return configStore.isGitLabEnabled
  if (providerId === 'google') return configStore.isGoogleEnabled
  return true
}
</script>

<template>
  <div class="w-full max-w-sm">
    <!-- Header -->
    <div class="text-center mb-8">
      <Logo class="size-[200px] mx-auto mb-8 lg:hidden" />
      <h1 class="text-2xl font-semibold text-neutral-900 dark:text-neutral-100 mb-2">
        {{ $t('auth.login.title') }}
      </h1>
      <p class="text-sm text-neutral-500 dark:text-neutral-400">
        {{ $t('auth.login.subtitle') }}
      </p>
    </div>

    <!-- SSO Login Card -->
    <UCard>
      <div class="space-y-3">
        <!-- SSO Buttons -->
        <AppButton
          v-for="provider in ssoProviders"
          :key="provider.id"
          color="neutral"
          variant="outline"
          size="lg"
          block
          :icon="provider.icon"
          :processing-duration="0"
          :disabled="loadingProvider !== null || !isProviderEnabled(provider.id)"
          @click="handleLogin(provider.id)"
        >
          <template v-if="loadingProvider === provider.id">
            <span class="flex items-center gap-2">
              <UIcon
                name="i-lucide-loader-2"
                class="size-4 animate-spin"
              />
              {{ $t('auth.redirecting') }}
            </span>
          </template>
          <template v-else>
            {{ $t(provider.labelKey) }}
          </template>
        </AppButton>
      </div>

      <!-- Error Display -->
      <UAlert
        v-if="authStore.error"
        color="error"
        variant="soft"
        :title="$t('auth.loginError')"
        :description="authStore.error"
        class="mt-4"
        icon="i-lucide-alert-circle"
      >
        <template #actions>
          <UButton
            color="error"
            variant="ghost"
            size="xs"
            @click="authStore.clearError()"
          >
            {{ $t('common.dismiss') }}
          </UButton>
        </template>
      </UAlert>
    </UCard>

    <!-- Terms Notice -->
    <p class="text-center text-xs text-neutral-400 dark:text-neutral-500 mt-6">
      {{ $t('auth.termsNotice') }}
    </p>
  </div>
</template>
