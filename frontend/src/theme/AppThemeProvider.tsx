import type { PropsWithChildren } from 'react'
import { ConfigProvider, theme as antdTheme } from 'antd'
import zhCN from 'antd/locale/zh_CN'

import { useThemeStore } from '@/store/theme'

export default function AppThemeProvider({ children }: PropsWithChildren) {
  const mode = useThemeStore((state) => state.mode)
  const isDark = mode === 'dark'
  const primary = isDark ? '#2dd4bf' : '#0f766e'
  const layout = isDark ? '#0b0f14' : '#f3f5f5'
  const container = isDark ? '#121820' : '#ffffff'

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: isDark ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
        token: {
          colorPrimary: primary,
          colorInfo: primary,
          colorBgLayout: layout,
          colorBgContainer: container,
          colorBgElevated: isDark ? '#172029' : '#ffffff',
          colorBorderSecondary: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,23,42,0.08)',
          colorText: isDark ? '#edf4f3' : '#18201f',
          colorTextSecondary: isDark ? '#a7b4b2' : '#5d6967',
          colorTextTertiary: isDark ? '#778582' : '#89928f',
          borderRadius: 9,
          borderRadiusLG: 14,
          controlHeight: 38,
          fontFamily:
            '"Segoe UI", "Microsoft YaHei", -apple-system, BlinkMacSystemFont, sans-serif',
        },
        components: {
          Layout: {
            headerHeight: 68,
            headerPadding: '0 28px',
            headerBg: container,
            siderBg: container,
            bodyBg: layout,
          },
          Menu: {
            itemBorderRadius: 9,
            itemMarginInline: 12,
            itemMarginBlock: 4,
            itemHeight: 42,
            itemSelectedBg: isDark ? 'rgba(45,212,191,0.12)' : 'rgba(15,118,110,0.09)',
            itemSelectedColor: primary,
            itemColor: isDark ? '#a7b4b2' : '#5d6967',
          },
          Card: {
            borderRadiusLG: 14,
            headerBg: 'transparent',
          },
          Table: {
            headerBg: isDark ? '#172029' : '#f8faf9',
            headerSplitColor: 'transparent',
            rowHoverBg: isDark ? 'rgba(255,255,255,0.035)' : 'rgba(15,118,110,0.035)',
            borderColor: isDark ? 'rgba(255,255,255,0.07)' : 'rgba(15,23,42,0.07)',
          },
          Button: {
            primaryShadow: 'none',
            defaultShadow: 'none',
          },
          Drawer: {
            colorBgElevated: container,
          },
        },
      }}
    >
      {children}
    </ConfigProvider>
  )
}
