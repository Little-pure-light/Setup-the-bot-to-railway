import { test, expect } from '@playwright/test'

/**
 * E2E Smoke — 以 page init script mock fetch，不呼叫正式 OpenAI
 */
async function mockChatApi(page) {
  await page.addInitScript(() => {
    const originalFetch = window.fetch.bind(window)
    window.fetch = async (input, init = {}) => {
      const url = typeof input === 'string' ? input : input?.url || ''
      if (url.includes('/api/chat')) {
        let body = {}
        try {
          body = JSON.parse(init.body || '{}')
        } catch {
          body = {}
        }
        const reply =
          body.car_mode || body.voice_mode
            ? '車載模式回覆：收到。'
            : '哈尼～你好呀，這是測試回覆。'
        const payload =
          reply +
          '\n__XCG_META__' +
          JSON.stringify({
            blocked: false,
            usage: {
              prompt_tokens: 1,
              completion_tokens: 2,
              total_tokens: 3,
              cost_usd: 0,
              model: 'mock',
            },
            tools_used: [],
            voice_mode: !!body.voice_mode,
            car_mode: !!body.car_mode,
          })
        return new Response(payload, {
          status: 200,
          headers: { 'Content-Type': 'text/plain; charset=utf-8' },
        })
      }
      if (url.includes('/api/')) {
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      return originalFetch(input, init)
    }
  })
}

test.describe('Chat smoke', () => {
  test('desktop: open chat, send message, see reply, no JS error', async ({ page }) => {
    const errors = []
    page.on('pageerror', (e) => errors.push(String(e)))
    await mockChatApi(page)
    await page.goto('/')
    await expect(page.locator('.message-input')).toBeVisible()
    await page.fill('.message-input', '你好')
    await page.locator('.send-button').click()
    await expect(page.locator('.message-user .message-text').last()).toContainText('你好', {
      timeout: 10_000,
    })
    const reply = page.locator('.message-assistant .message-text').last()
    await expect(reply).toContainText(/哈尼|測試|回覆/, { timeout: 15_000 })
    await page.reload()
    await expect(page.locator('.message-input')).toBeVisible()
    expect(errors, errors.join('\n')).toEqual([])
  })

  test('no horizontal overflow on load', async ({ page }) => {
    await mockChatApi(page)
    await page.goto('/')
    const hasOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth > document.documentElement.clientWidth + 2
    })
    expect(hasOverflow).toBe(false)
  })

  test('car_mode toggle does not crash and can send', async ({ page }) => {
    const errors = []
    page.on('pageerror', (e) => errors.push(String(e)))
    await mockChatApi(page)
    await page.goto('/')
    const carBtn = page.locator('button.car-mode-btn')
    if (await carBtn.count()) {
      await carBtn.click()
      await expect(page.locator('.voice-bar.car, .car-mode-btn.active').first()).toBeVisible()
    }
    await page.fill('.message-input', '車載你好')
    await page.click('.send-button')
    await expect(page.locator('.message-user .message-text').last()).toContainText('車載你好')
    await expect(page.locator('.message-assistant .message-text').last()).toContainText(
      /車載|回覆|哈尼/,
      { timeout: 15_000 }
    )
    expect(errors, errors.join('\n')).toEqual([])
  })
})
