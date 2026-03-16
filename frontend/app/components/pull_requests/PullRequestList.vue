<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'

import type { UIPullRequest } from '~/types/pullRequest'

interface Props {
  pullRequests: UIPullRequest[]
  currentPage: number
  itemsPerPage: number
  totalItems: number // Total from server for pagination
  pageSizeOptions?: readonly number[]
}

const props = withDefaults(defineProps<Props>(), {
  pageSizeOptions: () => [10, 25, 50],
})

const emit = defineEmits<{
  'update:currentPage': [page: number]
  'update:itemsPerPage': [size: number]
  'review': [pr: UIPullRequest]
}>()

const { t } = useI18n()
const authStore = useAuthStore()

function handleReview(pr: UIPullRequest): void {
  emit('review', pr)
}

function isProcessing(pr: UIPullRequest): boolean {
  return pr.latest_execution_status === 'processing' || pr.latest_execution_status === 'queued'
}

function isReviewDisabled(pr: UIPullRequest): boolean {
  return pr.author_reviewate_disabled || false
}

function isNotAuthor(pr: UIPullRequest): boolean {
  const user = authStore.user
  if (!user) return true
  return pr.author !== user.github_username && pr.author !== user.gitlab_username
}

function handleRowSelect(_e: Event, row: { original: UIPullRequest }) {
  const url = row.original.pr_url
  // Validate URL to prevent javascript: and data: URL attacks
  if (!url || !url.startsWith('https://')) {
    return
  }
  window.open(url, '_blank', 'noopener,noreferrer')
}

// Server-side pagination - items come pre-paginated from backend
const totalItems = computed(() => props.totalItems)

// Compute display values for the "showing X-Y of Z" text
const paginationStart = computed(() => {
  if (props.totalItems === 0) return 0
  return (props.currentPage - 1) * props.itemsPerPage + 1
})

const paginationEnd = computed(() => {
  return Math.min(props.currentPage * props.itemsPerPage, props.totalItems)
})

// Table columns
const columns = computed<TableColumn<UIPullRequest>[]>(() => [
  { accessorKey: 'title', header: t('pullRequests.columns.title') },
  { accessorKey: 'repository', header: t('pullRequests.columns.repo') },
  { accessorKey: 'status', header: t('pullRequests.columns.status') },
  { accessorKey: 'date', header: t('pullRequests.columns.date') },
  { id: 'actions', header: '' },
])
</script>

<template>
  <div class="flex flex-col lg:flex-1 lg:min-h-0 lg:overflow-hidden">
    <!-- Desktop Table -->
    <div class="hidden lg:flex lg:flex-col lg:flex-1 lg:min-h-0 rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 shadow-sm overflow-hidden">
      <UTable
        :data="pullRequests"
        :columns="columns"
        sticky
        class="flex-1 min-h-0"
        :ui="{
          root: 'flex-1 overflow-y-auto overflow-x-hidden',
          base: 'w-full table-auto',
          thead: 'bg-neutral-50 dark:bg-neutral-700 border-b border-neutral-200 dark:border-neutral-600',
          th: 'px-4 py-2 text-xs font-semibold text-neutral-500 dark:text-neutral-300 uppercase tracking-wider whitespace-nowrap first:w-full [&:nth-child(2)]:w-36 [&:nth-child(3)]:w-32 [&:nth-child(4)]:w-32 [&:nth-child(5)]:w-28',
          tbody: 'divide-y divide-neutral-100 dark:divide-neutral-700',
          tr: 'group',
          td: 'px-4 py-2.5 text-sm whitespace-nowrap first:max-w-0',
        }"
        @select="handleRowSelect"
      >
        <template #title-cell="{ row }">
          <div class="flex items-center gap-2 min-w-0">
            <UTooltip
              :text="row.original.title"
              :delay-duration="300"
              class="min-w-0 flex-1"
            >
              <span class="font-medium text-neutral-900 dark:text-neutral-100 group-hover:text-brand-600 dark:group-hover:text-brand-400 transition-colors block truncate cursor-pointer">
                {{ row.original.title }}
              </span>
            </UTooltip>
            <UBadge
              :color="getPRStateColor(row.original.state)"
              variant="soft"
              size="xs"
              class="flex-shrink-0 capitalize"
            >
              {{ getPRStateLabel(row.original.state) }}
            </UBadge>
          </div>
        </template>

        <template #repository-cell="{ row }">
          <span class="text-neutral-500 dark:text-neutral-400 whitespace-nowrap cursor-pointer">{{ row.original.repository }}</span>
        </template>

        <template #status-cell="{ row }">
          <div @click.stop>
            <ExecutionErrorPopover
              v-if="row.original.executionDisplay.color === 'error'"
              :execution-display="row.original.executionDisplay"
              @retry="handleReview(row.original)"
            />
            <UBadge
              v-else
              :color="row.original.executionDisplay.color"
              variant="subtle"
              size="xs"
              class="inline-block w-24 text-center"
            >
              {{ row.original.executionDisplay.label }}
            </UBadge>
          </div>
        </template>

        <template #date-cell="{ row }">
          <span class="text-neutral-500 dark:text-neutral-400 whitespace-nowrap cursor-pointer">{{ row.original.date }}</span>
        </template>

        <template #actions-cell="{ row }">
          <div
            class="text-right"
            @click.stop
          >
            <UTooltip
              v-if="isReviewDisabled(row.original)"
              :text="$t('pullRequests.reviewDisabledForAuthor', { author: row.original.author })"
            >
              <AppButton
                disabled
                color="neutral"
                size="xs"
                icon="icon-park-outline:preview-close"
                class="uppercase tracking-wide min-w-22"
              >
                {{ $t('common.review') }}
              </AppButton>
            </UTooltip>
            <UTooltip
              v-else-if="isNotAuthor(row.original)"
              :text="$t('pullRequests.onlyAuthorCanReview')"
            >
              <AppButton
                disabled
                color="neutral"
                size="xs"
                icon="icon-park-outline:preview-close"
                class="uppercase tracking-wide min-w-22"
              >
                {{ $t('common.review') }}
              </AppButton>
            </UTooltip>
            <AppButton
              v-else
              :id="row.index === 0 ? 'tour-review-button' : undefined"
              :processing="isProcessing(row.original)"
              color="primary"
              size="xs"
              icon="icon-park-outline:preview-open"
              class="uppercase tracking-wide min-w-22"
              @click="handleReview(row.original)"
            >
              {{ $t('common.review') }}
            </AppButton>
          </div>
        </template>
      </UTable>

      <!-- Pagination Footer -->
      <div class="flex items-center justify-between border-t border-neutral-200 dark:border-neutral-600 px-4 py-2 bg-neutral-50 dark:bg-neutral-700 shrink-0">
        <div class="flex items-center gap-3">
          <span class="text-xs text-neutral-500 dark:text-neutral-300">
            {{ $t('common.showing', { start: paginationStart, end: paginationEnd, total: totalItems }) }}
          </span>
          <div class="flex items-center gap-1.5">
            <span class="text-xs text-neutral-400 dark:text-neutral-500">{{ $t('common.perPage') }}</span>
            <USelect
              :model-value="itemsPerPage"
              :items="pageSizeOptions.map(n => ({ label: String(n), value: n }))"
              value-key="value"
              size="xs"
              class="w-16"
              :ui="{ base: 'text-xs' }"
              @update:model-value="emit('update:itemsPerPage', $event)"
            />
          </div>
        </div>
        <UPagination
          :page="currentPage"
          :total="totalItems"
          :items-per-page="itemsPerPage"
          :show-edges="false"
          size="xs"
          @update:page="emit('update:currentPage', $event)"
        />
      </div>
    </div>

    <!-- Mobile Cards -->
    <div class="lg:hidden space-y-2">
      <PullRequestCard
        v-for="pr in pullRequests"
        :key="pr.id"
        :pull-request="pr"
        @review="handleReview"
      />

      <!-- Mobile Pagination -->
      <div class="flex flex-col gap-2 pt-1">
        <div class="flex items-center justify-between">
          <span class="text-xs text-neutral-500 dark:text-neutral-400">
            {{ $t('common.showing', { start: paginationStart, end: paginationEnd, total: totalItems }) }}
          </span>
          <div class="flex items-center gap-1.5">
            <span class="text-xs text-neutral-400 dark:text-neutral-500">{{ $t('common.perPage') }}</span>
            <USelect
              :model-value="itemsPerPage"
              :items="pageSizeOptions.map(n => ({ label: String(n), value: n }))"
              value-key="value"
              size="xs"
              class="w-16"
              :ui="{ base: 'text-xs' }"
              @update:model-value="emit('update:itemsPerPage', $event)"
            />
          </div>
        </div>
        <div class="flex justify-center">
          <UPagination
            :page="currentPage"
            :total="totalItems"
            :items-per-page="itemsPerPage"
            :show-edges="false"
            size="xs"
            @update:page="emit('update:currentPage', $event)"
          />
        </div>
      </div>
    </div>
  </div>
</template>
