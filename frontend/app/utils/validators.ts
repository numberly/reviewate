/**
 * Common Validators
 *
 * Simple validator functions that return an error message or empty string.
 * Use with useFormValidation composable.
 *
 * @example
 * import { required, email, url } from '~/utils/validators'
 *
 * const validators = {
 *   email: [required('Email is required'), email()],
 *   website: [url('Enter a valid URL')],
 * }
 */

/**
 * Validates that a field is not empty
 */
export function required(msg = 'This field is required') {
  return (value: string): string => value?.trim() ? '' : msg
}

/**
 * Validates a URL format
 * Empty values pass (combine with required() if needed)
 */
export function url(msg = 'Enter a valid URL') {
  return (value: string): string => {
    if (!value?.trim()) return ''
    try {
      new URL(value)
      return ''
    } catch {
      return msg
    }
  }
}

/**
 * Validates an email format
 * Empty values pass (combine with required() if needed)
 */
export function email(msg = 'Enter a valid email address') {
  return (value: string): string => {
    if (!value?.trim()) return ''
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) ? '' : msg
  }
}

/**
 * Validates minimum length
 * Empty values pass (combine with required() if needed)
 */
export function minLength(min: number, msg?: string) {
  return (value: string): string => {
    if (!value) return ''
    return value.length >= min ? '' : (msg || `Must be at least ${min} characters`)
  }
}
