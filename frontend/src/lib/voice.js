/**
 * 瀏覽器語音輸入 / 輸出封裝
 * - SpeechRecognition（含 webkit 前綴）
 * - SpeechSynthesis
 * 車載模式：連聽、自動送出、TTS 結束後自動再開麥
 */

const STORAGE_KEY = 'xiaochenguang_voice_settings'

export const DEFAULT_VOICE_SETTINGS = {
  lang: 'zh-TW',
  rate: 1.0,
  pitch: 1.0,
  volume: 1.0,
  autoSpeak: false,
  carMode: false,
  autoSend: true,
  continuous: false,
  stripEmojisForSpeech: true,
}

export function isSpeechRecognitionSupported() {
  return Boolean(
    typeof window !== 'undefined' &&
      (window.SpeechRecognition || window.webkitSpeechRecognition)
  )
}

export function isSpeechSynthesisSupported() {
  return Boolean(
    typeof window !== 'undefined' &&
      window.speechSynthesis &&
      typeof window.SpeechSynthesisUtterance !== 'undefined'
  )
}

export function getSpeechRecognitionConstructor() {
  if (typeof window === 'undefined') return null
  return window.SpeechRecognition || window.webkitSpeechRecognition || null
}

export function loadVoiceSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { ...DEFAULT_VOICE_SETTINGS }
    return { ...DEFAULT_VOICE_SETTINGS, ...JSON.parse(raw) }
  } catch {
    return { ...DEFAULT_VOICE_SETTINGS }
  }
}

export function saveVoiceSettings(settings) {
  const merged = { ...DEFAULT_VOICE_SETTINGS, ...settings }
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(merged))
  } catch (e) {
    console.warn('[voice] 無法儲存設定:', e)
  }
  return merged
}

/** 供 TTS 朗讀的文字清理（去 markdown / 代碼塊 / 過多符號） */
export function sanitizeForSpeech(text, { stripEmojis = true } = {}) {
  if (!text || typeof text !== 'string') return ''
  let t = text
  // 隱藏後端 meta / tool 事件殘片
  t = t.replace(/__XCG_META__[\s\S]*$/g, '')
  t = t.replace(/__XCG_EVENT__[^\n]*/g, '')
  // 代碼塊
  t = t.replace(/```[\s\S]*?```/g, '（程式碼略過）')
  t = t.replace(/`([^`]+)`/g, '$1')
  // 連結 [label](url) → label
  t = t.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
  t = t.replace(/https?:\/\/\S+/g, '')
  // markdown 標題/列表/粗斜體
  t = t.replace(/^#{1,6}\s+/gm, '')
  t = t.replace(/^\s*[-*+]\s+/gm, '')
  t = t.replace(/^\s*\d+\.\s+/gm, '')
  t = t.replace(/(\*\*|__)(.*?)\1/g, '$2')
  t = t.replace(/(\*|_)(.*?)\1/g, '$2')
  // HTML
  t = t.replace(/<[^>]+>/g, '')
  if (stripEmojis) {
    // 常見 emoji 範圍（不完全，但夠車載朗讀用）
    t = t.replace(
      /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE00}-\u{FE0F}\u{200D}]/gu,
      ''
    )
  }
  t = t.replace(/\s{2,}/g, ' ').trim()
  return t
}

/**
 * 建立語音辨識控制器
 * @returns {{ start, stop, abort, isSupported, recognition } | null}
 */
export function createSpeechRecognizer(options = {}) {
  const Ctor = getSpeechRecognitionConstructor()
  if (!Ctor) return null

  const recognition = new Ctor()
  recognition.lang = options.lang || 'zh-TW'
  recognition.continuous = Boolean(options.continuous)
  recognition.interimResults = options.interimResults !== false
  recognition.maxAlternatives = 1

  let active = false

  recognition.onstart = () => {
    active = true
    options.onStart?.()
  }
  recognition.onend = () => {
    active = false
    options.onEnd?.()
  }
  recognition.onerror = (event) => {
    active = false
    // aborted / no-speech 在車載連聽很常見，不必當致命錯誤
    const soft = ['aborted', 'no-speech', 'audio-capture'].includes(event.error)
    options.onError?.(event.error, { soft, event })
  }
  recognition.onresult = (event) => {
    let interim = ''
    let finalText = ''
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const res = event.results[i]
      const transcript = res[0]?.transcript || ''
      if (res.isFinal) finalText += transcript
      else interim += transcript
    }
    options.onResult?.({
      interim,
      final: finalText,
      raw: event,
    })
  }

  return {
    recognition,
    isSupported: true,
    get active() {
      return active
    },
    start() {
      try {
        recognition.start()
        return true
      } catch (e) {
        // InvalidStateError：已在聽
        console.warn('[voice] recognition.start:', e?.message || e)
        return false
      }
    },
    stop() {
      try {
        recognition.stop()
      } catch (_) {
        /* ignore */
      }
    },
    abort() {
      try {
        recognition.abort()
      } catch (_) {
        /* ignore */
      }
    },
    setLang(lang) {
      recognition.lang = lang || 'zh-TW'
    },
    setContinuous(on) {
      recognition.continuous = Boolean(on)
    },
  }
}

/** 列出可用語音（可能需等待 voiceschanged） */
export function listVoices() {
  if (!isSpeechSynthesisSupported()) return []
  return window.speechSynthesis.getVoices() || []
}

export function pickPreferredVoice(lang = 'zh-TW', preferredName = '') {
  const voices = listVoices()
  if (!voices.length) return null
  if (preferredName) {
    const byName = voices.find((v) => v.name === preferredName)
    if (byName) return byName
  }
  const langBase = (lang || 'zh').split('-')[0].toLowerCase()
  const exact = voices.find((v) => v.lang?.toLowerCase() === lang.toLowerCase())
  if (exact) return exact
  const partial = voices.find((v) =>
    v.lang?.toLowerCase().startsWith(langBase)
  )
  if (partial) return partial
  // 中文後備
  const zh = voices.find((v) => /zh|cmn|chinese/i.test(v.lang + v.name))
  return zh || voices[0]
}

/**
 * 朗讀文字
 * @returns {Promise<void>} 朗讀結束（或取消/失敗）
 */
export function speakText(text, options = {}) {
  return new Promise((resolve, reject) => {
    if (!isSpeechSynthesisSupported()) {
      reject(new Error('瀏覽器不支援語音合成'))
      return
    }
    const clean = sanitizeForSpeech(text, {
      stripEmojis: options.stripEmojis !== false,
    })
    if (!clean) {
      resolve()
      return
    }

    // 打斷目前朗讀
    window.speechSynthesis.cancel()

    const utter = new SpeechSynthesisUtterance(clean)
    utter.lang = options.lang || 'zh-TW'
    utter.rate = clamp(Number(options.rate ?? 1), 0.5, 2)
    utter.pitch = clamp(Number(options.pitch ?? 1), 0, 2)
    utter.volume = clamp(Number(options.volume ?? 1), 0, 1)

    const voice = pickPreferredVoice(utter.lang, options.voiceName)
    if (voice) utter.voice = voice

    utter.onend = () => {
      options.onEnd?.()
      resolve()
    }
    utter.onerror = (e) => {
      // interrupted / canceled 視為正常
      const err = e?.error || 'synthesis-error'
      if (err === 'interrupted' || err === 'canceled') {
        resolve()
        return
      }
      options.onError?.(err)
      reject(new Error(err))
    }

    options.onStart?.(clean)
    // Chrome 偶發 pause bug：短延遲再 speak
    window.speechSynthesis.resume()
    window.speechSynthesis.speak(utter)
  })
}

export function stopSpeaking() {
  if (isSpeechSynthesisSupported()) {
    window.speechSynthesis.cancel()
  }
}

export function isSpeaking() {
  return isSpeechSynthesisSupported() && window.speechSynthesis.speaking
}

function clamp(n, min, max) {
  if (Number.isNaN(n)) return min
  return Math.min(max, Math.max(min, n))
}

/** 等待 voices 載入（最多 timeoutMs） */
export function waitForVoices(timeoutMs = 1500) {
  return new Promise((resolve) => {
    if (!isSpeechSynthesisSupported()) {
      resolve([])
      return
    }
    const existing = listVoices()
    if (existing.length) {
      resolve(existing)
      return
    }
    const timer = setTimeout(() => {
      window.speechSynthesis?.removeEventListener?.('voiceschanged', onChange)
      resolve(listVoices())
    }, timeoutMs)
    const onChange = () => {
      clearTimeout(timer)
      window.speechSynthesis.removeEventListener('voiceschanged', onChange)
      resolve(listVoices())
    }
    window.speechSynthesis.addEventListener('voiceschanged', onChange)
  })
}
