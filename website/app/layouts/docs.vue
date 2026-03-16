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

const { data: navigation } = useLazyAsyncData('docs-navigation', () =>
  queryCollectionNavigation('docs'),
)

// Flatten the root "Docs" wrapper from the navigation tree
const docsNavigation = computed(() => {
  if (!navigation.value) return []
  if (navigation.value.length === 1 && navigation.value[0]?.children) {
    return navigation.value[0]?.children
  }
  return navigation.value
})
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
        <USeparator class="my-4" />
        <UContentNavigation :navigation="docsNavigation" highlight />
      </template>
    </UHeader>

    <slot />
  </div>
</template>
