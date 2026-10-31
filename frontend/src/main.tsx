import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App as AntdApp } from 'antd'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
// antd v5 官方为 React 19 提供的兼容补丁（修复静态 message / Modal 等方法）
import '@ant-design/v5-patch-for-react-19'

import App from '@/App'
import '@/assets/css/global.css'
import AppThemeProvider from '@/theme/AppThemeProvider'

dayjs.locale('zh-cn')

const container = document.getElementById('root')
if (!container) {
  throw new Error('找不到挂载节点 #root')
}

createRoot(container).render(
  <StrictMode>
    <AppThemeProvider>
      <AntdApp>
        <App />
      </AntdApp>
    </AppThemeProvider>
  </StrictMode>,
)
