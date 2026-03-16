<script setup lang="ts">
const { locale, locales, setLocale } = useI18n()

interface LocaleItem {
  code: 'en' | 'fr'
  name: string
}

// Locale flags mapping
const localeFlags: Record<string, string> = {
  en: '🇬🇧',
  fr: '🇫🇷',
}

const availableLocales = computed<LocaleItem[]>(() =>
  locales.value
    .filter((l): l is { code: 'en' | 'fr', name: string } =>
      typeof l === 'object' && 'code' in l && 'name' in l,
    )
    .map((l) => ({ code: l.code, name: l.name })),
)

// Language menu items for dropdown with flags
const languageMenuItems = computed(() => [
  availableLocales.value.map((loc) => ({
    label: `${localeFlags[loc.code] || '🌐'}  ${loc.name}`,
    icon: locale.value === loc.code ? 'i-lucide-check' : undefined,
    onSelect: () => setLocale(loc.code),
  })),
])
</script>

<template>
  <UDropdownMenu
    :items="languageMenuItems"
    :content="{ side: 'bottom', align: 'start' }"
  >
    <UButton
      color="neutral"
      variant="ghost"
      size="xs"
      icon="i-heroicons-language"
      :aria-label="$t('settings.language')"
    />
  </UDropdownMenu>
</template>
