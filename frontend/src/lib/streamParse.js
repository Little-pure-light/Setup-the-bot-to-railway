/**
 * 串流緩衝解析（與 ChatInterface 協議一致）
 * - __XCG_EVENT__：工具狀態
 * - __XCG_META__：用量 / blocked 等
 */

export function parseStreamBuffer(fullText) {
  if (!fullText) {
    return { text: '', meta: null, events: [] }
  }
  const lines = String(fullText).split('\n')
  const visible = []
  const events = []
  let meta = null
  for (const line of lines) {
    if (line.startsWith('__XCG_EVENT__')) {
      try {
        events.push(JSON.parse(line.slice('__XCG_EVENT__'.length)))
      } catch {
        /* ignore bad event JSON */
      }
      continue
    }
    if (line.startsWith('__XCG_META__')) {
      try {
        meta = JSON.parse(line.slice('__XCG_META__'.length))
      } catch {
        meta = null
      }
      continue
    }
    visible.push(line)
  }
  return {
    text: visible.join('\n'),
    meta,
    events,
  }
}

export function stripInternalMarkers(text) {
  const { text: clean } = parseStreamBuffer(text || '')
  return clean
}
