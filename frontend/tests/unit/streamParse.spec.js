import { describe, it, expect } from 'vitest'
import { parseStreamBuffer, stripInternalMarkers } from '../../src/lib/streamParse.js'

describe('parseStreamBuffer', () => {
  it('hides tool events and meta from visible text', () => {
    const raw = [
      '__XCG_EVENT__{"type":"tool_status","status":"planning","tools":[]}',
      '哈尼～',
      '你好',
      '__XCG_META__{"usage":{"total_tokens":3},"blocked":false}',
    ].join('\n')
    const { text, meta, events } = parseStreamBuffer(raw)
    expect(text).toContain('哈尼～')
    expect(text).toContain('你好')
    expect(text).not.toContain('__XCG_EVENT__')
    expect(text).not.toContain('__XCG_META__')
    expect(meta.usage.total_tokens).toBe(3)
    expect(events[0].status).toBe('planning')
  })

  it('tolerates broken event JSON without crashing', () => {
    const { text, events } = parseStreamBuffer('__XCG_EVENT__{bad\nOK')
    expect(text).toContain('OK')
    expect(events).toEqual([])
  })

  it('stripInternalMarkers removes markers', () => {
    expect(stripInternalMarkers('__XCG_META__{"a":1}\nHi')).toContain('Hi')
    expect(stripInternalMarkers('__XCG_META__{"a":1}\nHi')).not.toContain('__XCG_META__')
  })
})
