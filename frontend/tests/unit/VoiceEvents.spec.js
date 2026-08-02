import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('axios', () => ({
  default: { get: vi.fn(async () => ({ data: [] })), post: vi.fn(async () => ({ data: {} })), put: vi.fn(async () => ({ data: {} })) },
}))
vi.mock('../../src/lib/auth.js', () => ({
  getSession: vi.fn(async () => null),
  getUserAuthHeaders: vi.fn(async () => ({ 'Content-Type': 'application/json', Authorization: 'Bearer test-voice-token' })),
  onAuthStateChange: vi.fn(() => () => {}),
  resolveUserId: vi.fn(() => 'test-user'),
  signOut: vi.fn(async () => {}),
  syncUserProfile: vi.fn(async () => ({})),
  isAuthConfigured: vi.fn(() => false),
}))
vi.mock('../../src/config.js', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, getClientId: () => '' }
})
vi.mock('../../src/lib/voice.js', async () => {
  const actual = await vi.importActual('../../src/lib/voice.js')
  return { ...actual, isSpeechRecognitionSupported: () => false, isSpeechSynthesisSupported: () => false, createSpeechRecognizer: () => null, speakText: vi.fn(async () => {}), stopSpeaking: vi.fn(), waitForVoices: vi.fn(async () => []) }
})

import ChatInterface from '../../src/components/ChatInterface.vue'

function mountChat() {
  return mount(ChatInterface, { global: { stubs: { CopilotWindow: true, LoginModal: true, HistoryPanel: true }, mocks: { $route: { path: '/', meta: {} } } } })
}

describe('reportVoiceEvent (Task008-002 guard)', () => {
  beforeEach(() => { localStorage.clear(); vi.clearAllMocks() })
  afterEach(() => { vi.unstubAllGlobals() })

  it('POSTs to /api/voice/events with event_type and does not throw on failure', async () => {
    const w = mountChat()
    await flushPromises()
    const calls = []
    globalThis.fetch = vi.fn(async (url, init) => { calls.push({ url: String(url), init }); return { ok: true, status: 200, json: async () => ({ ok: true, recorded: true }) } })
    await w.vm.reportVoiceEvent('speak_start', { transcript: 'hi' })
    await flushPromises()
    const hit = calls.find(c => c.url.includes('/api/voice/events'))
    expect(hit).toBeTruthy()
    expect(hit.init.method).toBe('POST')
    // 帶登入 Authorization header（來自 buildRequestHeaders）
    expect(hit.init.headers.Authorization).toBe('Bearer test-voice-token')
    const body = JSON.parse(hit.init.body)
    expect(body.event_type).toBe('speak_start')
    // Round2 最小 body：只送 event_type（不送 transcript/detail/user_id/conversation_id）
    expect(Object.keys(body)).toEqual(['event_type'])
  })

  it('swallows network failure (non-critical analytics, no throw)', async () => {
    const w = mountChat()
    await flushPromises()
    globalThis.fetch = vi.fn(async () => { throw new Error('network down') })
    await expect(w.vm.reportVoiceEvent('listen_start')).resolves.toBeUndefined()
  })
})
