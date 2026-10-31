import { spawn, spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { chromium } from 'playwright-core'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const frontendDir = path.resolve(scriptDir, '..')
const repoRoot = path.resolve(frontendDir, '..')
const backendDir = path.join(repoRoot, 'backend')
const screenshotDir = path.join(repoRoot, 'docs', 'screenshots')
const databasePath = path.join(tmpdir(), `meeting-room-screenshots-${process.pid}.db`)
const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const pythonPath = path.join(backendDir, '.venv', 'Scripts', 'python.exe')
const vitePath = path.join(frontendDir, 'node_modules', 'vite', 'bin', 'vite.js')
const children = []

function launch(command, args, cwd, env = {}) {
  const child = spawn(command, args, {
    cwd,
    env: { ...process.env, ...env },
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  })
  child.stdout.on('data', (chunk) => process.stdout.write(chunk))
  child.stderr.on('data', (chunk) => process.stderr.write(chunk))
  children.push(child)
  return child
}

async function waitForUrl(url, timeoutMs = 30_000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url)
      if (response.ok) return
    } catch {
      // 服务尚未启动完成
    }
    await new Promise((resolve) => setTimeout(resolve, 300))
  }
  throw new Error(`Timed out waiting for ${url}`)
}

async function removeWithRetry(targetPath, attempts = 8) {
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      await rm(targetPath, { force: true })
      return
    } catch (error) {
      if (attempt === attempts) {
        console.warn(`Cleanup warning: ${targetPath}: ${error.message}`)
        return
      }
      await new Promise((resolve) => setTimeout(resolve, 250))
    }
  }
}

function stopProcessTree(pid) {
  if (!pid) return
  spawnSync('taskkill', ['/pid', String(pid), '/T', '/F'], {
    windowsHide: true,
    stdio: 'ignore',
  })
}

async function main() {
  if (!existsSync(pythonPath)) throw new Error(`Python venv not found: ${pythonPath}`)
  if (!existsSync(vitePath)) throw new Error(`Vite not found: ${vitePath}`)
  if (!existsSync(chromePath)) throw new Error(`Chrome not found: ${chromePath}`)

  await rm(databasePath, { force: true })
  launch(
    pythonPath,
    ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000'],
    backendDir,
    {
      DATABASE_URL: `sqlite+pysqlite:///${databasePath.replaceAll('\\', '/')}`,
      INIT_DB_ON_STARTUP: 'true',
      AGENT_PROVIDER: 'local',
      PYTHONIOENCODING: 'utf-8',
    },
  )
  launch(
    process.execPath,
    [vitePath, '--host', '127.0.0.1', '--port', '5173', '--strictPort'],
    frontendDir,
  )

  await Promise.all([
    waitForUrl('http://127.0.0.1:8000/api/health'),
    waitForUrl('http://127.0.0.1:5173'),
  ])

  const loginResponse = await fetch('http://127.0.0.1:8000/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'admin', password: '123456' }),
  })
  if (!loginResponse.ok) {
    throw new Error(`Login failed with HTTP ${loginResponse.status}`)
  }
  const session = await loginResponse.json()

  const browser = await chromium.launch({
    executablePath: chromePath,
    headless: true,
    args: ['--disable-gpu', '--force-device-scale-factor=1'],
  })
  try {
    const publicContext = await browser.newContext({
      viewport: { width: 1440, height: 960 },
      deviceScaleFactor: 1,
      locale: 'zh-CN',
    })
    await publicContext.addInitScript(() => {
      localStorage.setItem('meeting-room-theme', 'light')
    })
    const publicPage = await publicContext.newPage()
    await publicPage.goto('http://127.0.0.1:5173/login', { waitUntil: 'networkidle' })
    await publicPage.getByRole('heading', { name: '欢迎回来' }).waitFor()
    await publicPage.screenshot({ path: path.join(screenshotDir, 'login.png') })
    await publicContext.close()

    const context = await browser.newContext({
      viewport: { width: 1440, height: 960 },
      deviceScaleFactor: 1,
      locale: 'zh-CN',
    })
    await context.addInitScript((value) => {
      localStorage.setItem('meeting-room-agent-session', JSON.stringify(value))
      localStorage.setItem('meeting-room-theme', 'light')
    }, session)
    const page = await context.newPage()

    await page.goto('http://127.0.0.1:5173/manager/home', { waitUntil: 'networkidle' })
    await page.getByText('空间预约排行', { exact: true }).waitFor()
    await page.screenshot({ path: path.join(screenshotDir, 'home.png') })

    await page.goto('http://127.0.0.1:5173/manager/venue', { waitUntil: 'networkidle' })
    await page.locator('.page-title').filter({ hasText: '会议空间管理' }).waitFor()
    await page.locator('.ant-table-row').first().waitFor()
    await page.screenshot({ path: path.join(screenshotDir, 'venues.png') })

    await page.getByRole('button', { name: '预约', exact: true }).first().click()
    const reservationDialog = page.getByRole('dialog')
    await reservationDialog.getByText('预约会议室', { exact: true }).waitFor()
    await reservationDialog.getByText(/剩余 \d+ 间/).first().waitFor()
    await page.screenshot({ path: path.join(screenshotDir, 'reservation.png') })

    await page.goto('http://127.0.0.1:5173/manager/reservation-review', {
      waitUntil: 'networkidle',
    })
    await page.locator('.page-title').filter({ hasText: '预约审核' }).waitFor()
    await page.locator('.ant-table-row').first().waitFor()
    await page.screenshot({ path: path.join(screenshotDir, 'reservation-review.png') })

    await page.goto('http://127.0.0.1:5173/manager/home', { waitUntil: 'networkidle' })
    await page.locator('.ant-float-btn').click()
    const agentInput = page.locator('.agent-footer textarea')
    await agentInput.fill('有哪些会议空间可以预约？')
    await page.locator('.agent-footer button').click()
    await page.getByText(/会议空间列表/).waitFor({ timeout: 15_000 })
    await page.screenshot({ path: path.join(screenshotDir, 'agent.png') })

    await page.goto('http://127.0.0.1:5173/manager/home', { waitUntil: 'networkidle' })
    await page.getByRole('button', { name: '切换到深色主题' }).click()
    await page.waitForFunction(() => document.documentElement.dataset.theme === 'dark')
    await page.getByText('空间预约排行', { exact: true }).waitFor()
    await page.screenshot({ path: path.join(screenshotDir, 'home-dark.png') })

    console.log('Screenshots updated:', screenshotDir)
  } finally {
    await browser.close()
  }
}

let failed = false
try {
  await main()
} catch (error) {
  failed = true
  console.error(error)
} finally {
  for (const child of children.reverse()) stopProcessTree(child.pid)
  await new Promise((resolve) => setTimeout(resolve, 500))
  await removeWithRetry(databasePath)
  await removeWithRetry(`${databasePath}-shm`)
  await removeWithRetry(`${databasePath}-wal`)
}

process.exit(failed ? 1 : 0)
