<script setup lang="ts">
/**
 * Organization Settings Tabs Component
 *
 * Custom tab navigation for organization settings.
 */
const { t } = useI18n()

const model = defineModel<string>({ required: true })

const tabs = computed(() => [
  {
    label: t('organizations.tabs.general'),
    value: 'general',
    icon: 'i-lucide-sliders-horizontal',
  },
  {
    label: t('organizations.tabs.repositories'),
    value: 'repositories',
    icon: 'i-lucide-git-branch',
  },
  {
    label: t('organizations.tabs.team'),
    value: 'team',
    icon: 'i-lucide-users',
  },
])
</script>

<template>
  <div class="border-b border-neutral-200 dark:border-neutral-700 px-6 shrink-0">
    <nav class="flex gap-6">
      <button
        v-for="tab in tabs"
        :id="'tour-' + tab.value + '-tab'"
        :key="tab.value"
        type="button"
        class="cursor-pointer relative flex items-center gap-2 py-3 text-sm font-medium transition-colors"
        :class="model === tab.value
          ? 'text-brand-600 dark:text-brand-400'
          : 'text-neutral-500 dark:text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-300'"
        @click="model = tab.value"
      >
        <UIcon
          :name="tab.icon"
          class="size-4"
        />
        {{ tab.label }}
        <!-- Active indicator -->
        <span
          v-if="model === tab.value"
          class="absolute bottom-0 left-0 right-0 h-0.5 bg-brand-500 rounded-full"
        />
      </button>
    </nav>
  </div>
</template>
