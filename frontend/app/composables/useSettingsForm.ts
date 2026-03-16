/**
 * Composable for settings load/save/dirty-tracking pattern.
 * Used by OrgGeneralTab and RepoSettingsPanel.
 */

type TriggerValue = 'creation' | 'commit' | 'label' | 'none'
type NullableTriggerValue = TriggerValue | null

interface SettingsData {
  automatic_review_trigger: string | null
  automatic_summary_trigger: string | null
}

interface UseSettingsFormOptions {
  entityId: ComputedRef<string>
  defaultValue: NullableTriggerValue
  load: (client: ReturnType<typeof useApi>, id: string) => Promise<{ data?: SettingsData | undefined }>
  save: (client: ReturnType<typeof useApi>, id: string, body: {
    automatic_review_trigger: NullableTriggerValue
    automatic_summary_trigger: NullableTriggerValue
  }) => Promise<{ data?: SettingsData | undefined, error?: unknown, response: Response }>
}

export function useSettingsForm(options: UseSettingsFormOptions) {
  const { t } = useI18n()
  const client = useApi()
  const toast = useToast()

  const settings = ref<SettingsData | null>(null)
  const isLoading = ref(false)
  const isSaving = ref(false)

  const form = reactive({
    automatic_review_trigger: options.defaultValue,
    automatic_summary_trigger: options.defaultValue,
  })

  const hasChanges = computed(() => {
    if (!settings.value) return false
    return form.automatic_review_trigger !== settings.value.automatic_review_trigger
      || form.automatic_summary_trigger !== settings.value.automatic_summary_trigger
  })

  watch(options.entityId, loadSettings, { immediate: true })

  async function loadSettings() {
    isLoading.value = true
    const { data } = await options.load(client, options.entityId.value)
    if (data) {
      settings.value = data
      form.automatic_review_trigger = data.automatic_review_trigger as NullableTriggerValue
      form.automatic_summary_trigger = data.automatic_summary_trigger as NullableTriggerValue
    }
    isLoading.value = false
  }

  async function saveSettings() {
    isSaving.value = true

    const { data, error: apiError, response } = await options.save(client, options.entityId.value, {
      automatic_review_trigger: form.automatic_review_trigger,
      automatic_summary_trigger: form.automatic_summary_trigger,
    })

    if (apiError) {
      if (response.status === 403) {
        toast.add({ title: t('organizations.settings.adminRequired'), color: 'error' })
      } else {
        toast.add({ title: t('organizations.settings.saveFailed'), color: 'error' })
      }
    } else if (data) {
      settings.value = data
      toast.add({ title: t('organizations.settings.settingsSaved'), color: 'success' })
    }

    isSaving.value = false
  }

  return { form, isLoading, isSaving, hasChanges, saveSettings }
}

export function useTriggerOptions({ includeInherit = false } = {}) {
  const { t } = useI18n()

  const triggerOptions = computed(() => [
    ...(includeInherit ? [{ label: t('organizations.repositories.inheritFromOrg'), value: null }] : []),
    { label: t('organizations.settings.triggerNone'), value: 'none' },
    { label: t('organizations.settings.triggerCreation'), value: 'creation' },
    { label: t('organizations.settings.triggerCommit'), value: 'commit' },
    { label: t('organizations.settings.triggerLabel'), value: 'label' },
  ])

  const summaryTriggerOptions = computed(() => [
    ...(includeInherit ? [{ label: t('organizations.repositories.inheritFromOrg'), value: null }] : []),
    { label: t('organizations.settings.triggerNone'), value: 'none' },
    { label: t('organizations.settings.triggerCreation'), value: 'creation' },
    { label: t('organizations.settings.triggerCommit'), value: 'commit' },
    { label: t('organizations.settings.triggerLabelSummarate'), value: 'label' },
  ])

  return { triggerOptions, summaryTriggerOptions }
}
