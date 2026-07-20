import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import LoginModal from '../../src/components/LoginModal.vue'

vi.mock('../../src/lib/auth.js', () => ({
  isAuthConfigured: () => true,
  signInWithEmail: vi.fn(async () => ({ user: { id: 'u1', email: 'a@b.com' } })),
  signUpWithEmail: vi.fn(async () => ({ user: { id: 'u2', email: 'c@d.com' } })),
}))

import { signInWithEmail } from '../../src/lib/auth.js'

describe('LoginModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders when visible', () => {
    const w = mount(LoginModal, { props: { visible: true } })
    expect(w.text()).toContain('登入')
  })

  it('prevents double submit while loading', async () => {
    let resolve
    signInWithEmail.mockImplementation(
      () =>
        new Promise((r) => {
          resolve = r
        })
    )
    const w = mount(LoginModal, { props: { visible: true } })
    await w.find('input[type="email"]').setValue('a@b.com')
    await w.find('input[type="password"]').setValue('secret12')
    const form = w.find('form')
    await form.trigger('submit.prevent')
    await form.trigger('submit.prevent')
    expect(signInWithEmail).toHaveBeenCalledTimes(1)
    resolve({ user: { id: 'u1', email: 'a@b.com' } })
    await flushPromises()
  })

  it('shows error on auth failure without logging password', async () => {
    const spy = vi.spyOn(console, 'log').mockImplementation(() => {})
    signInWithEmail.mockRejectedValueOnce(new Error('Invalid login'))
    const w = mount(LoginModal, { props: { visible: true } })
    await w.find('input[type="email"]').setValue('a@b.com')
    await w.find('input[type="password"]').setValue('bad-password-xyz')
    await w.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(w.text()).toMatch(/Invalid|錯誤|失敗|login/i)
    const logged = spy.mock.calls.map((c) => String(c[0])).join(' ')
    expect(logged).not.toContain('bad-password-xyz')
    spy.mockRestore()
  })
})
