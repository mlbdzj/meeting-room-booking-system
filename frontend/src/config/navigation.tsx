import type { ReactNode } from 'react'
import {
  AuditOutlined,
  BankOutlined,
  CalendarOutlined,
  DashboardOutlined,
  MessageOutlined,
  TagsOutlined,
  TeamOutlined,
} from '@ant-design/icons'
import type { MenuProps } from 'antd'

import type { Role } from '@/api/types'

export interface NavItem {
  path: string
  title: string
  icon: ReactNode
  /** 不填表示所有登录用户可见 */
  roles?: Role[]
}

export const NAV_ITEMS: NavItem[] = [
  { path: '/manager/home', title: '首页概览', icon: <DashboardOutlined /> },
  { path: '/manager/venue', title: '会议空间管理', icon: <BankOutlined /> },
  { path: '/manager/meeting-room', title: '会议室类型管理', icon: <TagsOutlined />, roles: ['admin'] },
  { path: '/manager/user', title: '会员管理', icon: <TeamOutlined />, roles: ['admin'] },
  { path: '/manager/reservation', title: '我的预约', icon: <CalendarOutlined /> },
  { path: '/manager/order-confirm', title: '预约确认', icon: <AuditOutlined />, roles: ['admin'] },
  { path: '/manager/knowledge', title: '客服知识库', icon: <MessageOutlined />, roles: ['admin'] },
]

export function visibleNavItems(role?: Role): NavItem[] {
  return NAV_ITEMS.filter((item) => !item.roles || (role ? item.roles.includes(role) : false))
}

export function navTitle(pathname: string): string | undefined {
  return NAV_ITEMS.find((item) => item.path === pathname)?.title
}

export function toMenuItems(items: NavItem[]): MenuProps['items'] {
  return items.map((item) => ({ key: item.path, icon: item.icon, label: item.title }))
}
