/**
 * 前端錯誤訊息淨化：避免 JWT / Bearer / API Key / Query 洩漏到 console 或 UI。
 */

const SECRET_PATTERNS = [
  /sk-[a-zA-Z0-9_\-]{10,}/gi,
  /eyJ[a-zA-Z0-9_\-]{20,}\.[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+/g,
  /Bearer\s+[^\s]+/gi,
  /(?:api[_-]?key|authorization)\s*[:=]\s*[^\s&]+/gi,
  /[?&](token|key|api_key|access_token|refresh_token)=[^&\s]+/gi,
]

export function isProduction() {
  try {
    return import.meta.env?.PROD === true || import.meta.env?.MODE === 'production'
  } catch {
    return false
  }
}

/** 遮蔽字串中的敏感片段 */
export function redactSecrets(text) {
  if (text == null) return ''
  let out = String(text)
  for (const re of SECRET_PATTERNS) {
    out = out.replace(re, '[REDACTED]')
  }
  // 去掉 query string 整段（URL 中）
  out = out.replace(/(https?:\/\/[^\s?]+)\?[^\s]*/gi, '$1?[REDACTED_QUERY]')
  return out
}

/**
 * 將任意錯誤轉成可安全記錄的摘要。
 * Production：僅類型、元件 info、requestId；不輸出完整 message。
 * Dev：可含脫敏後的短訊息。
 */
export function sanitizeError(err, options = {}) {
  const {
    info = '',
    requestId = '',
    production = isProduction(),
    maxLen = 160,
  } = options

  const name =
    (err && err.name) ||
    (typeof err === 'object' && err !== null && err.constructor && err.constructor.name) ||
    typeof err ||
    'Error'

  const rawMessage =
    err == null
      ? ''
      : typeof err === 'string'
        ? err
        : err.message != null
          ? String(err.message)
          : String(err)

  const redacted = redactSecrets(rawMessage).slice(0, maxLen)
  const rid = requestId || (typeof window !== 'undefined' && window.__XCG_REQUEST_ID) || ''

  if (production) {
    return {
      safeMessage: `[${name}]${info ? ` @${info}` : ''}${rid ? ` rid=${rid}` : ''}`,
      errorType: name,
      info: info || undefined,
      requestId: rid || undefined,
      // 明確不暴露原始 message
      rawIncluded: false,
    }
  }

  return {
    safeMessage: redactSecrets(
      `[${name}]${info ? ` ${info}:` : ''} ${redacted}${rid ? ` rid=${rid}` : ''}`
    ).slice(0, maxLen + 40),
    errorType: name,
    info: info || undefined,
    requestId: rid || undefined,
    rawIncluded: false,
  }
}

export function logClientError(tag, err, options = {}) {
  const summary = sanitizeError(err, options)
  // 只輸出摘要物件，不把 err 原樣丟進 console（避免展開 stack 含 query）
  console.error(tag, summary.safeMessage, {
    type: summary.errorType,
    info: summary.info,
    requestId: summary.requestId,
  })
  return summary
}
