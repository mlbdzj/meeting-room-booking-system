import { useState } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { Alert, Button, Form, Input, theme } from 'antd'
import { LockOutlined, UserOutlined } from '@ant-design/icons'

import { authApi } from '@/api'
import logo from '@/assets/imgs/logo.png'
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
    <div className="login-container">
      <div className="login-box">
        <img className="login-logo" src={logo} alt="" />
        <h1 style={{ fontSize: 24, marginTop: 14 }}>会议室预约系统</h1>
        <div style={{ marginTop: 6, marginBottom: 28, color: token.colorTextTertiary }}>
          基于 Agent 的智能会议空间预约平台
        </div>

        <Form form={form} size="large" initialValues={{ username: initialUsername }} onFinish={submit}>
          <Form.Item name="username" rules={[{ required: true, message: '请输入账号' }]}>
            <Input prefix={<UserOutlined />} placeholder="请输入账号" allowClear />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="请输入密码" />
          </Form.Item>
          <Button size="large" type="primary" htmlType="submit" block loading={loading}>
            登 录
          </Button>
          <div style={{ textAlign: 'right', marginTop: 18 }}>
            还没有账号？请
            <Link style={{ color: token.colorPrimary }} to="/register">
              注册
            </Link>
          </div>
        </Form>

        <Alert
          type="info"
          style={{ marginTop: 22, textAlign: 'left' }}
          message={
            <div>
              <div>演示账号</div>
              <div>空间管理员：admin / 123456</div>
              <div>会员用户：student / 123456</div>
            </div>
          }
        />
      </div>
    </div>
  )
}
