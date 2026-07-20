import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

vi.mock('axios', () => ({
  default: {
    get: vi.fn(async () => ({ data: [] })),
    post: vi.fn(async () => ({ data: {} })),
    put: vi.fn(async () => ({ data: {} })),
  },
}))

vi.mock('../../src/lib/auth.js', () => ({
  getSession: vi.fn(async () => null),
  getUserAuthHeaders: vi.fn(async () => ({})),
  onAuthStateChange: vi.fn(() => () => {}),
  resolveUserId: vi.fn(() => 'test-user'),
  signOut: vi.fn(async () => {}),
  syncUserProfile: vi.fn(async () => ({})),
  isAuthConfigured: vi.fn(() => false),
}))

vi.mock('../../src/lib/voice.js', async () => {
  const actual = await vi.importActual('../../src/lib/voice.js')
  return {
    ...actual,
    isSpeechRecognitionSupported: () => false,
    isSpeechSynthesisSupported: () => false,
    createSpeechRecognizer: () => null,
    speakText: vi.fn(async () => {}),
    stopSpeaking: vi.fn(),
    waitForVoices: vi.fn(async () => []),
  }
})

import ChatInterface from '../../src/components/ChatInterface.vue'

function mountChat(options = {}) {
  return mount(ChatInterface, {
    global: {
      stubs: {
        CopilotWindow: true,
        LoginModal: true,
        HistoryPanel: true,
      },
      mocks: {
        $route: { path: '/', meta: {} },
      },
    },
    ...options,
  })
}

describe('ChatInterface', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('renders input and allows typing', async () => {
    const w = mountChat()
    await flushPromises()
    const input = w.find('.message-input')
    expect(input.exists()).toBe(true)
    await input.setValue('你好小宸光')
    expect(w.vm.userInput).toBe('你好小宸光')
  })

  it('Enter triggers send when not loading', async () => {
    const w = mountChat()
    await flushPromises()
    const spy = vi.spyOn(w.vm, 'sendMessage').mockResolvedValue()
    await w.find('.message-input').setValue('hi')
    await w.find('.message-input').trigger('keyup.enter')
    expect(spy).toHaveBeenCalled()
  })

  it('prevents duplicate send while loading', async () => {
    const w = mountChat()
    await flushPromises()
    w.vm.isLoading = true
    w.vm.userInput = 'x'
    const spy = vi.spyOn(w.vm, 'sendMessage')
    await w.vm.sendMessage()
    // early return - still called once from us, internal should no-op if already loading
    // re-call: sendMessage returns immediately
    const before = w.vm.messages.length
    await w.vm.sendMessage()
    expect(w.vm.messages.length).toBe(before)
    spy.mockRestore()
  })

  it('consumeStreamBuffer hides tool events and meta', async () => {
    const w = mountChat()
    await flushPromises()
    const raw = [
      '__XCG_EVENT__{"type":"tool_status","status":"running","message":"搜尋中","tools":[{"name":"web_search"}]}',
      '答案在這裡',
      '__XCG_META__{"usage":{"total_tokens":9},"blocked":false}',
    ].join('\n')
    const { text, meta } = w.vm.consumeStreamBuffer(raw)
    expect(text).toBe('答案在這裡')
    expect(text).not.toContain('__XCG_EVENT__')
    expect(text).not.toContain('__XCG_META__')
    expect(meta.usage.total_tokens).toBe(9)
    expect(w.vm.toolStatusPhase).toBe('running')
  })

  it('sends voice_mode and car_mode in request body', async () => {
    const w = mountChat()
    await flushPromises()
    w.vm.carMode = true
    w.vm.autoSpeak = true
    w.vm.userInput = '車載測試'
    w.vm.isLoading = false
    w.vm.isStreaming = false

    const bodies = []
    globalThis.fetch = vi.fn(async (_url, init) => {
      bodies.push(JSON.parse(init.body))
      const stream = new ReadableStream({
        start(controller) {
          controller.enqueue(new TextEncoder().encode('回覆'))
          controller.enqueue(
            new TextEncoder().encode(
              '\n__XCG_META__' + JSON.stringify({ usage: { total_tokens: 1 }, blocked: false })
            )
          )
          controller.close()
        },
      })
      return {
        ok: true,
        body: stream,
        status: 200,
        text: async () => '回覆',
      }
    })

    await w.vm.sendMessage({ inputMethod: 'voice' })
    await flushPromises()
    expect(bodies.length).toBeGreaterThan(0)
    expect(bodies[0].car_mode).toBe(true)
    expect(bodies[0].voice_mode).toBe(true)
    expect(bodies[0].input_method).toBe('voice')
  })

  it('shows friendly error on API failure', async () => {
    const w = mountChat()
    await flushPromises()
    w.vm.userInput = 'err'
    globalThis.fetch = vi.fn(async () => ({
      ok: false,
      status: 500,
      text: async () => 'server error',
      body: null,
    }))
    await w.vm.sendMessage()
    await flushPromises()
    const last = w.vm.messages[w.vm.messages.length - 1]
    expect(last.type === 'system' || /錯誤|error|HTTP/i.test(last.content)).toBe(true)
  })
})
