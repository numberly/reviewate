/**
 * Organization and repository utility functions
 */

/**
 * Get the initial letter from an organization or repository name
 * @param name - The name to extract initial from
 * @returns Uppercase first letter
 */
export function getInitial(name: string): string {
  return name.charAt(0).toUpperCase()
}

/**
 * Get the icon name for a provider
 * @param provider - Provider string ('github'|'gitlab')
 * @returns Icon name for the provider
 */
export function getProviderIcon(provider: string | null | undefined): string {
  if (provider === 'github') {
    return 'i-simple-icons-github'
  }
  return 'i-simple-icons-gitlab'
}

/**
 * Get the display name for a provider
 * @param provider - Provider string ('github'|'gitlab')
 * @returns 'GitHub' or 'GitLab'
 */
export function getProviderName(provider: string | null | undefined): string {
  return provider === 'github' ? 'GitHub' : 'GitLab'
}
