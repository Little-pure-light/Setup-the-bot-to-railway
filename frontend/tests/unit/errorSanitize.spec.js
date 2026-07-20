import { describe, it, expect, vi } from 'vitest'
import {
  redactSecrets,
  sanitizeError,
  logClientError,
} from '../../src/lib/errorSanitize.js'

describe('errorSanitize', () => {
  it('redacts API keys, JWT, Bearer, and query strings', () => {
    const raw =
      'fail sk-proj-ABCDEFGHIJKLMNOP url=https://x.com/a?token=secret123 Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.aaaa.bbbb'
    const out = redactSecrets(raw)
    expect(out).not.toContain('sk-proj-ABCDEFGHIJKLMNOP')
    expect(out).not.toContain('eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9')
    expect(out).not.toContain('token=secret123')
    expect(out).toMatch(/REDACTED/)
  })

  it('production mode does not include full error message', () => {
    const err = new Error('OpenAI key sk-proj-LEAKEDSECRETVALUE failed')
    const s = sanitizeError(err, {
      production: true,
      info: 'ChatInterface',
      requestId: 'rid123',
    })
    expect(s.safeMessage).toContain('Error')
    expect(s.safeMessage).toContain('ChatInterface')
    expect(s.safeMessage).toContain('rid123')
    expect(s.safeMessage).not.toContain('LEAKEDSECRETVALUE')
    expect(s.safeMessage).not.toContain('sk-proj')
    expect(s.rawIncluded).toBe(false)
  })

  it('dev mode still redacts secrets in short message', () => {
    const err = new TypeError('Bearer abc.def.ghi boom')
    const s = sanitizeError(err, { production: false })
    expect(s.safeMessage).toContain('TypeError')
    expect(s.safeMessage).not.toMatch(/Bearer\s+abc/)
  })

  it('logClientError does not pass raw secret message as first args only summary', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    const err = new Error('authorization: Bearer super-secret-token')
    logClientError('[test]', err, { production: true, requestId: 'r1' })
    const joined = spy.mock.calls.flat().map(String).join(' ')
    expect(joined).not.toContain('super-secret-token')
    expect(joined).toContain('r1')
    spy.mockRestore()
  })
})
