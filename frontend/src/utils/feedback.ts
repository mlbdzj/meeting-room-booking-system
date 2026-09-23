import { App as AntdApp, Modal, message } from 'antd'

/**
 * antd 的 message / modal 静态方法无法读取 ConfigProvider 的上下文（主题、语言包）。
 * 这里在 App 组件里绑定一次 `App.useApp()` 的实例，让请求层这类非组件代码也能用上。
 */
export type FeedbackApi = ReturnType<typeof AntdApp.useApp>

type ConfirmOptions = Parameters<FeedbackApi['modal']['confirm']>[0]

let bound: FeedbackApi | null = null

export function bindFeedbackApi(api: FeedbackApi) {
  bound = api
}

export const feedback = {
  success(content: string) {
    if (bound) bound.message.success(content)
    else message.success(content)
  },
  error(content: string) {
    if (bound) bound.message.error(content)
    else message.error(content)
  },
  warning(content: string) {
    if (bound) bound.message.warning(content)
    else message.warning(content)
  },
  info(content: string) {
    if (bound) bound.message.info(content)
    else message.info(content)
  },
  confirm(options: ConfirmOptions) {
    if (bound) bound.modal.confirm(options)
    else Modal.confirm(options)
  },
}
