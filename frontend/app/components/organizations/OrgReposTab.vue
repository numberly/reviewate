<script setup lang="ts">
import type { RepositoryListItem } from '@reviewate/api-types'

const props = defineProps<{
  repositories: RepositoryListItem[]
  selectedRepo: RepositoryListItem | null
  isLoading: boolean
  isDeleting: boolean
  isAdmin?: boolean
}>()

const emit = defineEmits<{
  selectRepo: [repo: RepositoryListItem | null]
  deleteRepo: [repo: RepositoryListItem]
}>()

const hasSelectedRepo = computed(() => !!props.selectedRepo)
</script>

<template>
  <SplitDetailLayout :has-selection="hasSelectedRepo">
    <template #list>
      <RepoList
        :repositories="repositories"
        :selected-repo-id="selectedRepo?.id ?? null"
        :has-selected-repo="hasSelectedRepo"
        :is-loading="isLoading"
        @select="emit('selectRepo', $event)"
      />
    </template>

    <template #detail>
      <RepoSettingsPanel
        v-if="selectedRepo"
        :repository="selectedRepo"
        :is-deleting="isDeleting"
        :is-admin="isAdmin"
        @close="emit('selectRepo', null)"
        @delete="emit('deleteRepo', $event)"
      />
    </template>
  </SplitDetailLayout>
</template>
