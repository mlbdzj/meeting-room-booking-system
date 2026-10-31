import { useCallback, useMemo, useState } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  Avatar,
  Dropdown,
  Form,
  Input,
  Layout as AntdLayout,
  Menu,
  Modal,
  theme,
  type MenuProps,
} from 'antd'
import { ApartmentOutlined, DownOutlined } from '@ant-design/icons'

import { authApi } from '@/api'
import type { ProfilePayload } from '@/api/types'
import AgentChat from '@/components/AgentChat'
import ThemeToggle from '@/components/ThemeToggle'
import { navTitle, toMenuItems, visibleNavItems } from '@/config/navigation'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { ROLE_TEXT, useUserStore } from '@/store/user'
import { useThemeStore } from '@/store/theme'
import { feedback } from '@/utils/feedback'

const { Header, Sider, Content } = AntdLayout

interface PasswordFormValues {
  old_password: string
  new_password: string
  confirm_password: string
}

const userMenuItems: MenuProps['items'] = [
  { key: 'profile', label: '个人信息' },
  { key: 'password', label: '修改密码' },
  { type: 'divider' },
  { key: 'logout', label: '退出登录' },
]

export default function Layout() {
  const navigate = useNavigate()
  const location = useLocation()
  const user = useUserStore((state) => state.user)
  const themeMode = useThemeStore((state) => state.mode)
  const displayName = user?.name || user?.username || '未登录'
  const { token } = theme.useToken()

  useDocumentTitle(navTitle(location.pathname))

  const menuItems = useMemo(() => toMenuItems(visibleNavItems(user?.role)), [user?.role])

  const [profileOpen, setProfileOpen] = useState(false)
  const [profileSaving, setProfileSaving] = useState(false)
  const [profileForm] = Form.useForm<ProfilePayload>()

  const [passwordOpen, setPasswordOpen] = useState(false)
  const [passwordSaving, setPasswordSaving] = useState(false)
  const [passwordForm] = Form.useForm<PasswordFormValues>()

  const openProfile = useCallback(async () => {
    const detail = await authApi.me()
    profileForm.setFieldsValue({ name: detail.name, phone: detail.phone, email: detail.email })
    setProfileOpen(true)
  }, [profileForm])

  const saveProfile = useCallback(async () => {
    const values = await profileForm.validateFields().catch(() => null)
    if (!values) return
    setProfileSaving(true)
    try {
      const updated = await authApi.updateProfile(values)
      useUserStore.getState().setUser(updated)
      setProfileOpen(false)
      feedback.success('个人信息已更新')
    } finally {
      setProfileSaving(false)
    }
  }, [profileForm])

  const openPassword = useCallback(() => {
    passwordForm.resetFields()
    setPasswordOpen(true)
  }, [passwordForm])

  const savePassword = useCallback(async () => {
    const values = await passwordForm.validateFields().catch(() => null)
    if (!values) return
    setPasswordSaving(true)
    try {
      await authApi.changePassword({
        old_password: values.old_password,
        new_password: values.new_password,
      })
      setPasswordOpen(false)
      feedback.success('密码修改成功，请重新登录')
      useUserStore.getState().clear()
      navigate('/login')
    } finally {
      setPasswordSaving(false)
    }
  }, [navigate, passwordForm])

  const logout = useCallback(() => {
    feedback.confirm({
      title: '提示',
      content: '确定要退出登录吗？',
      okText: '确定',
      cancelText: '取消',
      onOk: () => {
        useUserStore.getState().clear()
        feedback.success('已退出登录')
        navigate('/login')
      },
    })
  }, [navigate])

  const handleUserMenu = useCallback<NonNullable<MenuProps['onClick']>>(
    ({ key }) => {
      if (key === 'profile') void openProfile()
      if (key === 'password') openPassword()
      if (key === 'logout') logout()
    },
    [logout, openPassword, openProfile],
  )

  return (
    <AntdLayout style={{ minHeight: '100vh' }}>
      <Header className="app-header">
        <div className="app-brand">
          <span className="app-brand-mark">
            <ApartmentOutlined />
          </span>
          <span className="app-brand-copy">
            <strong>会议室预约</strong>
            <small>Meeting Space</small>
          </span>
        </div>
        <div className="app-user">
          <ThemeToggle compact />
          {(!user || ROLE_TEXT[user.role] !== displayName) && (
            <span className="app-role">{user ? ROLE_TEXT[user.role] : '访客'}</span>
          )}
          <Dropdown menu={{ items: userMenuItems, onClick: handleUserMenu }} trigger={['click']}>
            <span className="app-user-trigger">
              <Avatar size={32} style={{ backgroundColor: token.colorPrimary }}>
                {(displayName || 'U').slice(0, 1)}
              </Avatar>
              <span>{displayName}</span>
              <DownOutlined style={{ fontSize: 12 }} />
            </span>
          </Dropdown>
        </div>
      </Header>

      <AntdLayout>
        <Sider width={228} theme={themeMode} className="app-sider">
          <Menu
            mode="inline"
            selectedKeys={[location.pathname]}
            items={menuItems}
            style={{ height: '100%', borderRight: 'none', paddingTop: 8 }}
            onClick={({ key }) => navigate(key)}
          />
        </Sider>

        <Content className="app-main-content">
          <div className="app-content">
            <Outlet />
          </div>
        </Content>
      </AntdLayout>

      <Modal
        title="个人信息"
        open={profileOpen}
        width={460}
        okText="保存"
        cancelText="取消"
        confirmLoading={profileSaving}
        onOk={saveProfile}
        onCancel={() => setProfileOpen(false)}
      >
        <Form form={profileForm} labelCol={{ span: 5 }} wrapperCol={{ span: 19 }} style={{ marginTop: 20 }}>
          <Form.Item label="账号">
            <Input value={user?.username} disabled />
          </Form.Item>
          <Form.Item label="姓名" name="name">
            <Input placeholder="请输入姓名" />
          </Form.Item>
          <Form.Item label="手机号" name="phone">
            <Input placeholder="请输入手机号" />
          </Form.Item>
          <Form.Item label="邮箱" name="email">
            <Input placeholder="请输入邮箱" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="修改密码"
        open={passwordOpen}
        width={420}
        okText="确定"
        cancelText="取消"
        confirmLoading={passwordSaving}
        onOk={savePassword}
        onCancel={() => setPasswordOpen(false)}
      >
        <Form form={passwordForm} labelCol={{ span: 5 }} wrapperCol={{ span: 19 }} style={{ marginTop: 20 }}>
          <Form.Item
            label="原密码"
            name="old_password"
            rules={[{ required: true, message: '请输入原密码' }]}
          >
            <Input.Password />
          </Form.Item>
          <Form.Item
            label="新密码"
            name="new_password"
            rules={[
              { required: true, message: '请输入新密码' },
              { min: 6, message: '密码至少 6 位' },
            ]}
          >
            <Input.Password />
          </Form.Item>
          <Form.Item
            label="确认密码"
            name="confirm_password"
            dependencies={['new_password']}
            rules={[
              { required: true, message: '请确认新密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('new_password') === value) return Promise.resolve()
                  return Promise.reject(new Error('两次输入的密码不一致'))
                },
              }),
            ]}
          >
            <Input.Password />
          </Form.Item>
        </Form>
      </Modal>

      <AgentChat />
    </AntdLayout>
  )
}
