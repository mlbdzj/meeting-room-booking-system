import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App as AntdApp, ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
// antd v5 官方为 React 19 提供的兼容补丁（修复静态 message / Modal 等方法）
import '@ant-design/v5-patch-for-react-19'

import App from '@/App'
import '@/assets/css/global.css'

dayjs.locale('zh-cn')

const container = document.getElementById('root')
if (!container) {
  throw new Error('找不到挂载节点 #root')
}

createRoot(container).render(
  <StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          // 与 Element Plus 的默认主色保持一致，尽量贴近原有视觉
          colorPrimary: '#409eff',
          colorInfo: '#409eff',
          colorSuccess: '#67c23a',
          colorWarning: '#e6a23c',
          colorError: '#f56c6c',
          fontFamily: '"Microsoft YaHei", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        },
      }}
    >
      <AntdApp>
        <App />
      </AntdApp>
    </ConfigProvider>
  </StrictMode>,
)
