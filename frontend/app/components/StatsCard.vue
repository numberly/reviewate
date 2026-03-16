<script setup lang="ts">
interface Props {
  label: string
  value: string
  change?: string
  trend?: 'up' | 'down' | 'neutral'
  icon?: string
  iconColor?: 'brand' | 'success' | 'warning'
}

defineProps<Props>()

const iconBgClasses: Record<string, string> = {
  brand: 'bg-brand-50 dark:bg-brand-900/30',
  success: 'bg-success-50 dark:bg-success-900/30',
  warning: 'bg-warning-50 dark:bg-warning-900/30',
}

const iconFgClasses: Record<string, string> = {
  brand: 'text-brand-500 dark:text-brand-400',
  success: 'text-success-500 dark:text-success-400',
  warning: 'text-warning-500 dark:text-warning-400',
}
</script>

<template>
  <div class="group flex flex-col gap-3 rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 p-4 sm:p-5 shadow-sm hover:shadow-md hover:border-neutral-300 dark:hover:border-neutral-600 hover:-translate-y-0.5 transition-all duration-200 cursor-pointer">
    <div class="flex items-center justify-between">
      <div
        v-if="icon"
        class="size-9 flex items-center justify-center rounded-lg"
        :class="iconBgClasses[iconColor || 'brand']"
      >
        <UIcon
          :name="icon"
          class="size-5"
          :class="iconFgClasses[iconColor || 'brand']"
        />
      </div>
      <div
        v-if="change"
        class="flex items-center gap-1 text-xs sm:text-sm font-medium"
        :class="trend === 'up' ? 'text-success-600 dark:text-success-400' : trend === 'down' ? 'text-error-600 dark:text-error-400' : 'text-neutral-400 dark:text-neutral-500'"
      >
        <UIcon
          v-if="trend === 'up' || trend === 'down'"
          :name="trend === 'up' ? 'i-lucide-trending-up' : 'i-lucide-trending-down'"
          class="size-4"
        />
        {{ change }}
      </div>
    </div>
    <div>
      <p class="text-2xl sm:text-3xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100 group-hover:text-brand-600 dark:group-hover:text-brand-400 transition-colors">
        {{ value }}
      </p>
      <p class="text-xs sm:text-sm font-medium text-neutral-500 dark:text-neutral-400 mt-1">
        {{ label }}
      </p>
    </div>
  </div>
</template>
