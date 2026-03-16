/**
 * Date formatting utilities
 */

/**
 * Formats a date string as relative time from now
 * @param dateString - ISO date string
 * @returns Human-readable relative time (e.g., "2 hours ago")
 */
export function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMinutes = Math.floor(diffMs / (1000 * 60))
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffMinutes < 1) return 'Just now'
  if (diffMinutes < 60) return `${diffMinutes} ${diffMinutes === 1 ? 'minute' : 'minutes'} ago`
  if (diffHours < 24) return `${diffHours} ${diffHours === 1 ? 'hour' : 'hours'} ago`
  if (diffDays === 1) return '1 day ago'
  return `${diffDays} days ago`
}

/**
 * Formats a duration in seconds as a human-readable string
 * @param seconds - Duration in seconds (null/undefined = no data)
 * @returns e.g. "6h 15m", "45m", "<1m", "--"
 */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || seconds < 0) return '--'

  const totalMinutes = Math.round(seconds / 60)
  if (totalMinutes < 1) return '<1m'

  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60

  if (hours === 0) return `${minutes}m`
  if (minutes === 0) return `${hours}h`
  return `${hours}h ${minutes}m`
}

/**
 * Formats a percentage change for display
 * @param percentage - Change percentage (null = no meaningful comparison)
 * @param vsLabel - The "vs last week" label from i18n
 * @returns e.g. "+5% vs last week", or undefined when nothing to show
 */
export function formatChange(
  percentage: number | null | undefined,
  vsLabel: string,
): string | undefined {
  if (percentage == null || percentage === 0) return undefined
  const sign = percentage > 0 ? '+' : ''
  return `${sign}${percentage}% ${vsLabel}`
}
