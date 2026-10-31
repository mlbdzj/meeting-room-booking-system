import { useCallback, useEffect, useRef, useState } from 'react'
import { MoonOutlined, SunOutlined } from '@ant-design/icons'
import { Button, Tooltip } from 'antd'
import { createPortal } from 'react-dom'

import { useThemeStore, type ThemeMode } from '@/store/theme'

interface ThemeToggleProps {
  compact?: boolean
}

export default function ThemeToggle({ compact = false }: ThemeToggleProps) {
  const mode = useThemeStore((state) => state.mode)
  const toggle = useThemeStore((state) => state.toggle)
  const [wave, setWave] = useState<ThemeMode | null>(null)
  const timers = useRef<number[]>([])
  const isDark = mode === 'dark'

  useEffect(() => {
    return () => {
      timers.current.forEach((timer) => window.clearTimeout(timer))
      delete document.documentElement.dataset.themeTransition
    }
  }, [])

  const switchTheme = useCallback(() => {
    if (wave) return
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduceMotion) {
      toggle()
      return
    }

    const nextMode: ThemeMode = mode === 'dark' ? 'light' : 'dark'
    setWave(nextMode)
    document.documentElement.dataset.themeTransition = 'active'
    timers.current.push(window.setTimeout(toggle, 300))
    timers.current.push(
      window.setTimeout(() => {
        setWave(null)
        delete document.documentElement.dataset.themeTransition
        timers.current = []
      }, 760),
    )
  }, [mode, toggle, wave])

  return (
    <>
      <Tooltip title={isDark ? '切换到浅色主题' : '切换到深色主题'}>
        <Button
          type="text"
          className={compact ? 'theme-toggle theme-toggle-compact' : 'theme-toggle'}
          icon={isDark ? <SunOutlined /> : <MoonOutlined />}
          aria-label={isDark ? '切换到浅色主题' : '切换到深色主题'}
          disabled={Boolean(wave)}
          onClick={switchTheme}
        />
      </Tooltip>
      {wave &&
        createPortal(
          <div className="theme-wave" data-next-theme={wave} aria-hidden="true">
            <span className="theme-wave-glow" />
          </div>,
          document.body,
        )}
    </>
  )
}
