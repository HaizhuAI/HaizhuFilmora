import { chromium } from 'playwright-core'

const EXE = '/snap/bin/chromium'
const base = 'http://127.0.0.1:8001'
const outDir = '/tmp/ui_shots'
import { mkdirSync } from 'fs'
mkdirSync(outDir, { recursive: true })

const browser = await chromium.launch({ executablePath: EXE, args: ['--no-sandbox', '--disable-gpu'] })
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
const errors = []
page.on('console', m => { if (m.type() === 'error') errors.push(m.text()) })
page.on('pageerror', e => errors.push(String(e)))

// 1. login
await page.goto(base + '/login', { waitUntil: 'networkidle' })
await page.screenshot({ path: outDir + '/01-login.png' })
await page.fill('#pw', 'admin123')
await page.click('button[type=submit]')
await page.waitForURL('**/media', { timeout: 10000 })
await page.waitForTimeout(1200)
await page.screenshot({ path: outDir + '/02-media.png' })

// 2. editor
await page.click('a[href="/editor"]')
await page.waitForTimeout(1200)
await page.screenshot({ path: outDir + '/03-editor.png' })

// 3. AI studio
await page.click('a[href="/ai"]')
await page.waitForTimeout(1200)
await page.screenshot({ path: outDir + '/04-ai.png' })

// 4. keys
await page.click('a[href="/keys"]')
await page.waitForTimeout(1200)
await page.screenshot({ path: outDir + '/05-keys.png' })

// 5. create key
await page.click('text=创建密钥')
await page.waitForTimeout(600)
await page.screenshot({ path: outDir + '/06-keys-created.png' })

console.log('CONSOLE_ERRORS:', errors.length ? JSON.stringify(errors.slice(0, 5)) : 'none')
await browser.close()
