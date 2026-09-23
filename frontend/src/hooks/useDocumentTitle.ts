import { useEffect } from 'react'

const BASE_TITLE = '智能会议室预约系统'

export function useDocumentTitle(title?: string) {
  useEffect(() => {
    document.title = title ? `${title} - ${BASE_TITLE}` : BASE_TITLE
  }, [title])
}
