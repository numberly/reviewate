<script setup lang="ts">
import { ExecutionStatus } from '~/types/execution'
import type { UIPullRequest } from '~/types/pullRequest'

const props = defineProps<{
  pullRequest: UIPullRequest
}>()

const emit = defineEmits<{
  review: [pullRequest: UIPullRequest]
}>()

const isProcessing = computed(() => {
  return props.pullRequest.latest_execution_status === ExecutionStatus.PROCESSING
    || props.pullRequest.latest_execution_status === ExecutionStatus.QUEUED
})

const isReviewDisabled = computed(() => {
  return props.pullRequest.author_reviewate_disabled || false
})

const authStore = useAuthStore()

const isNotAuthor = computed(() => {
  const user = authStore.user
  if (!user) return true
  return props.pullRequest.author !== user.github_username && props.pullRequest.author !== user.gitlab_username
})

const { t } = useI18n()

function handleReview() {
  emit('review', props.pullRequest)
}
</script>

<template>
  <NuxtLink
    :to="pullRequest.pr_url"
    external
    target="_blank"
    class="block"
  >
    <UCard
      variant="interactive"
      padding="md"
      :ui="{
        body: 'space-y-2',
      }"
    >
      <!-- Title + execution status -->
      <div class="flex items-start justify-between gap-2">
        <span class="flex-1 min-w-0 font-medium text-neutral-900 dark:text-neutral-100 line-clamp-1 group-hover:text-brand-600 dark:group-hover:text-brand-400 transition-colors">
          {{ pullRequest.title }}
        </span>
        <div @click.stop.prevent>
          <ExecutionErrorPopover
            v-if="pullRequest.executionDisplay.color === 'error'"
            :execution-display="pullRequest.executionDisplay"
            @retry="handleReview"
          />
          <UBadge
            v-else
            :color="pullRequest.executionDisplay.color"
            variant="subtle"
            size="xs"
            class="shrink-0"
          >
            {{ pullRequest.executionDisplay.label }}
          </UBadge>
        </div>
      </div>
      <!-- Repo + date + state -->
      <div class="flex items-center gap-2 text-neutral-500 dark:text-neutral-400 text-sm min-w-0">
        <span class="truncate shrink min-w-0">{{ pullRequest.repository }}</span>
        <span class="shrink-0">·</span>
        <span class="shrink-0">{{ pullRequest.date }}</span>
        <UBadge
          :color="getPRStateColor(pullRequest.state)"
          variant="soft"
          size="xs"
          class="capitalize shrink-0"
        >
          {{ getPRStateLabel(pullRequest.state) }}
        </UBadge>
      </div>
      <!-- Review button -->
      <div
        class="flex justify-end"
        @click.stop.prevent
      >
        <UTooltip
          v-if="isReviewDisabled"
          :text="t('pullRequests.reviewDisabledForAuthor', { author: pullRequest.author })"
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
          v-else-if="isNotAuthor"
          :text="t('pullRequests.onlyAuthorCanReview')"
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
          :processing="isProcessing"
          color="primary"
          size="xs"
          icon="icon-park-outline:preview-open"
          class="uppercase tracking-wide min-w-22"
          @click="handleReview"
        >
          {{ $t('common.review') }}
        </AppButton>
      </div>
    </UCard>
  </NuxtLink>
</template>
