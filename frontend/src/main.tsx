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
          // 品牌色见 assets/css/global.css 里的 --app-primary，两处保持一致
          colorPrimary: '#1677ff',
          borderRadius: 8,
          colorBgLayout: '#f5f7fa',
          fontFamily: '"Microsoft YaHei", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        },
        components: {
          Layout: {
            headerHeight: 64,
            headerPadding: '0 24px',
            headerBg: '#ffffff',
            siderBg: '#ffffff',
            bodyBg: '#f5f7fa',
          },
          Menu: {
            itemBorderRadius: 8,
            itemMarginInline: 8,
            itemMarginBlock: 4,
            itemHeight: 42,
            itemSelectedBg: '#e6f4ff',
            itemSelectedColor: '#1677ff',
          },
          Card: {
            borderRadiusLG: 12,
          },
          Table: {
            headerBg: '#fafafa',
            headerSplitColor: 'transparent',
          },
        },
      }}
    >
      <AntdApp>
        <App />
      </AntdApp>
    </ConfigProvider>
  </StrictMode>,
)
