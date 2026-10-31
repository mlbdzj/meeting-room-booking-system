import { useState } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { Button, Form, Input, theme } from 'antd'
import { ApartmentOutlined, LockOutlined, UserOutlined } from '@ant-design/icons'

import { authApi } from '@/api'
import ThemeToggle from '@/components/ThemeToggle'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { useUserStore } from '@/store/user'
import { feedback } from '@/utils/feedback'

interface LoginFormValues {
  username: string
  password: string
}

export default function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const [form] = Form.useForm<LoginFormValues>()
  const [loading, setLoading] = useState(false)
  const { token } = theme.useToken()

  useDocumentTitle()

  const redirect = (location.state as { redirect?: string } | null)?.redirect
  const initialUsername = searchParams.get('username') || ''

  const submit = async (values: LoginFormValues) => {
    setLoading(true)
    try {
      const data = await authApi.login({ username: values.username.trim(), password: values.password })
      useUserStore.getState().setSession(data.token, data.user)
      feedback.success('登录成功')
      if (redirect && redirect.startsWith('/manager')) {
        navigate(redirect, { replace: true })
      } else {
        navigate('/manager/home', { replace: true })
      }
    } catch (error) {
      feedback.error((error as Error).message || '登录失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-theme">
        <ThemeToggle />
      </div>
      <div className="auth-shell">
        <section className="auth-intro">
          <div className="auth-brand">
            <span className="app-brand-mark">
              <ApartmentOutlined />
            </span>
            <span className="app-brand-copy">
              <strong>会议室预约</strong>
              <small>Meeting Space</small>
            </span>
          </div>
          <div className="auth-eyebrow">SMART WORKSPACE</div>
          <h1>
            让每一次会议，
            <br />
            找到合适的空间。
          </h1>
          <p>更轻量的会议空间管理体验。查看余量、安排时段，也可以直接告诉智能助手你的需求。</p>
          <div className="auth-points">
            <span>实时余量</span>
            <span>自然语言预约</span>
            <span>权限清晰</span>
          </div>
        </section>

        <section className="login-box">
          <div className="auth-form-head">
            <h2>欢迎回来</h2>
            <p>登录后继续管理你的会议安排</p>
          </div>

          <Form form={form} size="large" initialValues={{ username: initialUsername }} onFinish={submit}>
            <Form.Item name="username" rules={[{ required: true, message: '请输入账号' }]}>
              <Input prefix={<UserOutlined />} placeholder="账号" allowClear />
            </Form.Item>
            <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
              <Input.Password prefix={<LockOutlined />} placeholder="密码" />
            </Form.Item>
            <Button size="large" type="primary" htmlType="submit" block loading={loading}>
              登录
            </Button>
            <div className="auth-switch">
              还没有账号？
              <Link style={{ color: token.colorPrimary }} to="/register">
                创建账号
              </Link>
            </div>
          </Form>

          <div className="demo-accounts">
            <div className="demo-title">演示账号</div>
            <div>
              <span>空间管理员</span>
              <code>admin / 123456</code>
            </div>
            <div>
              <span>会员用户</span>
              <code>student / 123456</code>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
