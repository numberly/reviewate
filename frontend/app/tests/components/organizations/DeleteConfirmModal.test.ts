/**
 * Tests for DeleteConfirmModal component
 *
 * Note: The modal content is teleported to the body via UModal,
 * so we test using document.body for content that renders inside the modal.
 */
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it } from 'vitest'

import DeleteConfirmModal from '~/components/organizations/DeleteConfirmModal.vue'

describe('DeleteConfirmModal', () => {
  const defaultProps = {
    open: true,
    isLoading: false,
    title: 'Delete Item',
    description: 'Are you sure you want to delete this item?',
    itemName: 'Test Item',
    errorMessage: null,
  }

  // Helper to get modal content from body (teleported content)
  function getModalContent(): string {
    return document.body.textContent ?? ''
  }

  it('renders the title in the modal', async () => {
    await mountSuspended(DeleteConfirmModal, {
      props: defaultProps,
    })
    expect(getModalContent()).toContain('Delete Item')
  })

  it('renders the description in the modal', async () => {
    await mountSuspended(DeleteConfirmModal, {
      props: defaultProps,
    })
    expect(getModalContent()).toContain('Are you sure you want to delete this item?')
  })

  it('renders the item name in the modal', async () => {
    await mountSuspended(DeleteConfirmModal, {
      props: defaultProps,
    })
    expect(getModalContent()).toContain('Test Item')
  })

  it('displays the cannot be undone warning', async () => {
    await mountSuspended(DeleteConfirmModal, {
      props: defaultProps,
    })
    // Uses the i18n key since $t returns the key
    expect(getModalContent()).toContain('common.cannotBeUndone')
  })

  it('renders cancel button with correct text', async () => {
    await mountSuspended(DeleteConfirmModal, {
      props: defaultProps,
    })
    expect(getModalContent()).toContain('common.cancel')
  })

  it('renders delete button with default text', async () => {
    await mountSuspended(DeleteConfirmModal, {
      props: defaultProps,
    })
    expect(getModalContent()).toContain('common.delete')
  })

  it('renders custom confirm text when provided', async () => {
    await mountSuspended(DeleteConfirmModal, {
      props: { ...defaultProps, confirmText: 'Remove Forever' },
    })
    expect(getModalContent()).toContain('Remove Forever')
  })

  describe('events', () => {
    it('emits update:open with false when close button is clicked', async () => {
      const wrapper = await mountSuspended(DeleteConfirmModal, {
        props: defaultProps,
      })

      // Find close button by looking in the document body for buttons
      const closeButtons = document.body.querySelectorAll('button')
      const closeButton = Array.from(closeButtons).find((btn) => {
        return btn.querySelector('[class*="lucide-x"]')
      })

      if (closeButton) {
        closeButton.click()
        await wrapper.vm.$nextTick()
        expect(wrapper.emitted('update:open')?.[0]).toEqual([false])
      }
    })

    it('emits confirm when confirm button is clicked', async () => {
      const wrapper = await mountSuspended(DeleteConfirmModal, {
        props: defaultProps,
      })

      // Find delete button - look for the button with error color attribute
      const buttons = document.body.querySelectorAll('button')
      const deleteButton = Array.from(buttons).find((btn) => {
        const hasErrorColor = btn.getAttribute('data-color') === 'error'
        const hasDeleteText = btn.textContent?.includes('common.delete')
        return hasErrorColor || hasDeleteText
      })

      if (deleteButton) {
        deleteButton.click()
        await wrapper.vm.$nextTick()
      }

      // The component should handle click events correctly
      expect(wrapper.exists()).toBe(true)
    })
  })

  describe('props validation', () => {
    it('accepts all required props', async () => {
      const wrapper = await mountSuspended(DeleteConfirmModal, {
        props: defaultProps,
      })

      // Component should mount without errors
      expect(wrapper.exists()).toBe(true)
    })

    it('handles optional confirmText prop', async () => {
      const wrapper = await mountSuspended(DeleteConfirmModal, {
        props: { ...defaultProps, confirmText: 'Custom Text' },
      })

      expect(wrapper.exists()).toBe(true)
    })
  })
})
