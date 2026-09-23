import { App as AntdApp } from 'antd'
import { RouterProvider } from 'react-router-dom'

import { router } from '@/router'
import { bindFeedbackApi } from '@/utils/feedback'

export default function App() {
  // 把 ConfigProvider 上下文里的 message / modal 交给非组件代码（请求层）使用
  bindFeedbackApi(AntdApp.useApp())

  return <RouterProvider router={router} />
}
