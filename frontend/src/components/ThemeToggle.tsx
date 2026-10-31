import { MoonOutlined, SunOutlined } from '@ant-design/icons'
import { Button, Tooltip } from 'antd'

import { useThemeStore } from '@/store/theme'

interface ThemeToggleProps {
  compact?: boolean
}

export default function ThemeToggle({ compact = false }: ThemeToggleProps) {
  const mode = useThemeStore((state) => state.mode)
  const toggle = useThemeStore((state) => state.toggle)
  const isDark = mode === 'dark'

  return (
    <Tooltip title={isDark ? '切换到浅色主题' : '切换到深色主题'}>
      <Button
        type="text"
        className={compact ? 'theme-toggle theme-toggle-compact' : 'theme-toggle'}
        icon={isDark ? <SunOutlined /> : <MoonOutlined />}
        aria-label={isDark ? '切换到浅色主题' : '切换到深色主题'}
        onClick={toggle}
      />
    </Tooltip>
  )
}
