import { vi } from 'vitest'

// localStorage polyfill for jsdom gaps
const store = new Map()
const localStorageMock = {
  getItem: (k) => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => store.set(k, String(v)),
  removeItem: (k) => store.delete(k),
  clear: () => store.clear(),
}
Object.defineProperty(globalThis, 'localStorage', { value: localStorageMock })

// avoid speech API noise
globalThis.speechSynthesis = {
  speak: vi.fn(),
  cancel: vi.fn(),
  getVoices: () => [],
  speaking: false,
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  resume: vi.fn(),
}
