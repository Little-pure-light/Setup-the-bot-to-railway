import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('axios', () => ({
  default: {
    get: vi.fn(async () => ({ data: [] })),
    post: vi.fn(async () => ({ data: {} })),
    put: vi.fn(async () => ({ data: {} })),
  },
}))

const headersState = vi.hoisted(() => ({ value: {} }))
vi.mock('../../src/lib/auth.js', () => ({
  getSession: vi.fn(async () => null),
  getUserAuthHeaders: vi.fn(async () => headersState.value),
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

import axios from 'axios'
import ChatInterface from '../../src/components/ChatInterface.vue'

function mountChat() {
  return mount(ChatInterface, {
    global: {
      stubs: { CopilotWindow: true, LoginModal: true, HistoryPanel: true },
      mocks: { $route: { path: '/', meta: {} } },
    },
  })
}

function lastMessages(w) {
  return w.vm.messages.map((m) => m.content).join('\n')
}

describe('archiveConversation (private owner-scoped)', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    headersState.value = {}
    vi.stubGlobal('confirm', vi.fn(() => true))
  })
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  // case 1：archive 請求確實帶 buildRequestHeaders() 回傳的 Authorization
  it('sends Authorization from buildRequestHeaders on archive request', async () => {
    const w = mountChat()
    await flushPromises()
    headersState.value = { 'Content-Type': 'application/json', Authorization: 'Bearer FRONT-TEST' }
    w.vm.conversationId = 'cid-1'
    w.vm.userId = 'test-user'
    axios.post.mockReset()
    axios.post.mockResolvedValue({ data: { success: true, message: 'ok' } })

    await w.vm.archiveConversation()
    await flushPromises()

    expect(axios.post).toHaveBeenCalledTimes(1)
    const call = axios.post.mock.calls[0]
    expect(String(call[0])).toContain('/api/archive_conversation')
    expect(call[2]).toBeTruthy()
    expect(call[2].headers.Authorization).toBe('Bearer FRONT-TEST')
  })

  // case 2：success 才清除舊 localStorage 並建立新 conversation id
  it('clears old localStorage and starts a new conversation only on success', async () => {
    const w = mountChat()
    await flushPromises()
    localStorage.setItem('xiaochenguang_messages', JSON.stringify([{ a: 1 }]))
    localStorage.setItem('xiaochenguang_conversation_id', 'old-cid')
    w.vm.conversationId = 'old-cid'
    axios.post.mockReset()
    axios.post.mockResolvedValue({ data: { success: true, message: '此對話已安全保留' } })

    await w.vm.archiveConversation()
    await flushPromises()

    expect(localStorage.getItem('xiaochenguang_messages')).toBeNull()
    expect(w.vm.conversationId).not.toBe('old-cid')
    expect(w.vm.conversationId).toBeTruthy()
    expect(lastMessages(w)).toContain('已開始新對話')
  })

  // case 3：401／403／404／500 不清除舊對話，顯示安全訊息
  it.each([401, 403, 404, 500])('keeps old conversation on HTTP %i and shows a safe message', async (status) => {
    const w = mountChat()
    await flushPromises()
    localStorage.setItem('xiaochenguang_messages', JSON.stringify([{ a: 1 }]))
    localStorage.setItem('xiaochenguang_conversation_id', 'keep-cid')
    w.vm.conversationId = 'keep-cid'
    axios.post.mockReset()
    axios.post.mockRejectedValue({ response: { status }, message: 'request failed' })

    await w.vm.archiveConversation()
    await flushPromises()

    expect(localStorage.getItem('xiaochenguang_conversation_id')).toBe('keep-cid')
    expect(localStorage.getItem('xiaochenguang_messages')).not.toBeNull()
    expect(w.vm.conversationId).toBe('keep-cid')
    expect(lastMessages(w)).toContain('仍保留在畫面上')
    expect(lastMessages(w)).not.toContain('已開始新對話')
  })

  // case 4：response 沒有 CID 時不得顯示假 CID／公開 gateway
  it('never displays a CID or public gateway on success', async () => {
    const w = mountChat()
    await flushPromises()
    w.vm.conversationId = 'cid-4'
    axios.post.mockReset()
    // 即使後端回傳 ipfs_cid（不應發生），前端也不讀取／顯示
    axios.post.mockResolvedValue({ data: { success: true, message: 'ok', ipfs_cid: 'bafyFAKECID', gateway_url: 'https://gateway.example/ipfs/bafyFAKECID' } })

    await w.vm.archiveConversation()
    await flushPromises()

    const text = lastMessages(w)
    expect(text).not.toContain('CID')
    expect(text).not.toContain('bafyFAKECID')
    expect(text).not.toContain('gateway')
    expect(text).not.toContain('ipfs')
  })

  // case 5：錯誤內容經 sanitize，不曝露 Bearer／token／內部錯誤
  it('sanitizes error content and never leaks tokens', async () => {
    const w = mountChat()
    await flushPromises()
    w.vm.conversationId = 'cid-5'
    axios.post.mockReset()
    const LEAK = 'Bearer FAKE-PLACEHOLDER-TOKEN failed at https://api/x?token=PLACEHOLDER1234'
    axios.post.mockRejectedValue(new Error(LEAK)) // 無 response.status → 走 sanitize 分支

    await w.vm.archiveConversation()
    await flushPromises()

    const text = lastMessages(w)
    // 元件只使用 sanitizeError 的 errorType，不回顯原始錯誤訊息
    expect(text).not.toContain('FAKE-PLACEHOLDER-TOKEN')
    expect(text).not.toContain('token=PLACEHOLDER1234')
    expect(text).not.toContain('Bearer FAKE-PLACEHOLDER-TOKEN')
    expect(text).toContain('仍保留在畫面上')
  })
})
