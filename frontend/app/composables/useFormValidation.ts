/**
 * Form Validation Composable
 *
 * Provides reactive field-level validation with touched state tracking.
 * Use with UFormField's :error prop for inline error display.
 *
 * @example
 * const form = ref({ email: '', url: '' })
 * const { getError, touch, validateAll } = useFormValidation(form, {
 *   email: [required(), email()],
 *   url: [url()],
 * })
 *
 * <UFormField :error="getError('email')">
 *   <UInput v-model="form.email" @blur="touch('email')" />
 * </UFormField>
 */

type Validator = (value: string) => string
type FieldValidators<T> = Partial<Record<keyof T, Validator[]>>

export function useFormValidation<T extends Record<string, string>>(
  form: Ref<T>,
  validators: FieldValidators<T>,
) {
  const errors = reactive<Record<string, string>>({})
  const touched = reactive<Record<string, boolean>>({})

  /**
   * Validate a single field and update errors
   * Returns true if valid, false if invalid
   */
  function validateField(field: keyof T): boolean {
    const fieldValidators = validators[field] || []
    for (const validator of fieldValidators) {
      const error = validator(form.value[field] || '')
      if (error) {
        errors[field as string] = error
        return false
      }
    }
    errors[field as string] = ''
    return true
  }

  /**
   * Validate all fields, marking them as touched
   * Returns true if all valid, false if any invalid
   */
  function validateAll(): boolean {
    let valid = true
    for (const field of Object.keys(validators)) {
      touched[field] = true
      if (!validateField(field as keyof T)) {
        valid = false
      }
    }
    return valid
  }

  /**
   * Get error message for a field (only if touched)
   * Returns empty string if not touched or no error
   */
  function getError(field: keyof T): string {
    return touched[field as string] ? (errors[field as string] || '') : ''
  }

  /**
   * Mark a field as touched and validate it
   * Call this on blur events
   */
  function touch(field: keyof T): void {
    touched[field as string] = true
    validateField(field)
  }

  /**
   * Reset all validation state
   */
  function reset(): void {
    for (const key of Object.keys(errors)) {
      errors[key] = ''
    }
    for (const key of Object.keys(touched)) {
      touched[key] = false
    }
  }

  return {
    validateAll,
    getError,
    touch,
    reset,
  }
}
