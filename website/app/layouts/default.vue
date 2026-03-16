<script setup lang="ts">
const colorMode = useColorMode()

function toggleColorMode() {
  colorMode.preference = colorMode.value === 'dark' ? 'light' : 'dark'
}

const navItems = [
  { label: 'Docs', to: '/docs' },
  { label: 'Pricing', to: '/pricing' },
  { label: 'Blog', to: '/blog' },
  { label: 'GitHub', to: 'https://github.com/numberly/reviewate', target: '_blank' },
]

const footerLinks = [
  { label: 'Docs', to: '/docs' },
  { label: 'GitHub', to: 'https://github.com/numberly/reviewate', target: '_blank' },
]
</script>

<template>
  <div class="min-h-screen">
    <UHeader title="Reviewate" to="/">
      <template #title>
        <img src="/logo.svg" alt="Reviewate" class="size-7">
        <span class="font-semibold text-lg tracking-tight text-neutral-900 dark:text-neutral-100">Reviewate</span>
      </template>

      <UNavigationMenu :items="navItems" variant="link" />

      <template #right>
        <UButton
          :icon="colorMode.value === 'dark' ? 'lucide:sun' : 'lucide:moon'"
          variant="ghost"
          color="neutral"
          @click="toggleColorMode"
        />
        <UTooltip text="Coming soon" :delay-duration="0">
          <UButton
            label="Login"
            variant="ghost"
            color="neutral"
            class="hidden sm:inline-flex"
            disabled
          />
        </UTooltip>
        <UTooltip text="Coming soon" :delay-duration="0">
          <UButton
            label="Get Started"
            color="neutral"
            variant="solid"
            disabled
          />
        </UTooltip>
      </template>

      <template #body>
        <UNavigationMenu :items="navItems" orientation="vertical" class="w-full" />
      </template>
    </UHeader>

    <main>
      <slot />
    </main>

    <footer class="border-t border-neutral-200 dark:border-neutral-800 py-8">
      <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div class="flex items-center gap-2.5">
          <img src="/logo.svg" alt="Reviewate" class="size-5">
          <span class="text-sm font-medium text-neutral-500 dark:text-neutral-400">Reviewate</span>
        </div>
        <div class="flex items-center gap-6">
          <NuxtLink
            v-for="link in footerLinks"
            :key="link.label"
            :to="link.to"
            :target="link.target"
            class="text-sm text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-300 transition-colors"
          >
            {{ link.label }}
          </NuxtLink>
        </div>
        <p class="text-xs text-neutral-400">
          &copy; {{ new Date().getFullYear() }} Reviewate. Open source under AGPL v3.
        </p>
      </div>
    </footer>
  </div>
</template>
