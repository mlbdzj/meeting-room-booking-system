import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button, Form, Input, theme } from 'antd'
import {
  ApartmentOutlined,
  IdcardOutlined,
  LockOutlined,
  PhoneOutlined,
  UserOutlined,
} from '@ant-design/icons'

import { authApi } from '@/api'
import ThemeToggle from '@/components/ThemeToggle'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { feedback } from '@/utils/feedback'

interface RegisterFormValues {
  username: string
  name: string
  phone: string
  password: string
  confirmPassword: string
}

export default function Register() {
  const navigate = useNavigate()
  const [form] = Form.useForm<RegisterFormValues>()
  const [loading, setLoading] = useState(false)
  const { token } = theme.useToken()

  useDocumentTitle()

  const submit = async (values: RegisterFormValues) => {
    setLoading(true)
    try {
      await authApi.register({
        username: values.username.trim(),
        name: values.name.trim(),
        phone: values.phone,
        email: '',
        password: values.password,
        confirm_password: values.confirmPassword,
      })
      feedback.success('注册成功，请登录')
      navigate({ pathname: '/login', search: `?username=${encodeURIComponent(values.username.trim())}` })
    } catch (error) {
      feedback.error((error as Error).message || '注册失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-theme">
        <ThemeToggle />
      </div>
      <div className="auth-shell register-shell">
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
          <div className="auth-eyebrow">START IN MINUTES</div>
          <h1>
            一个账号，
            <br />
            管理所有会议安排。
          </h1>
          <p>创建会员账号后即可查看空间、预约会议室，并通过智能助手快速完成安排。</p>
          <div className="auth-points">
            <span>简单注册</span>
            <span>安全登录</span>
            <span>随时查看</span>
          </div>
        </section>

        <section className="register-box">
          <div className="auth-form-head">
            <h2>创建账号</h2>
            <p>填写基本信息即可开始使用</p>
          </div>

          <Form form={form} layout="vertical" size="large" onFinish={submit}>
          <Form.Item
            label="账号"
            name="username"
            rules={[
              { required: true, message: '请输入账号' },
              { min: 3, max: 20, message: '账号长度为 3-20 位' },
              { pattern: /^\w+$/, message: '账号只能包含字母、数字和下划线' },
            ]}
          >
            <Input prefix={<UserOutlined />} placeholder="3-20 位字母、数字或下划线" allowClear />
          </Form.Item>
          <Form.Item label="姓名" name="name" rules={[{ required: true, message: '请输入姓名' }]}>
            <Input prefix={<IdcardOutlined />} placeholder="请输入真实姓名" allowClear />
          </Form.Item>
          <Form.Item
            label="手机号"
            name="phone"
            rules={[{ pattern: /^1[3-9]\d{9}$/, message: '手机号格式不正确' }]}
          >
            <Input prefix={<PhoneOutlined />} placeholder="请输入手机号" allowClear />
          </Form.Item>
          <Form.Item
            label="密码"
            name="password"
            rules={[
              { required: true, message: '请输入密码' },
              { min: 6, message: '密码至少 6 位' },
            ]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="至少 6 位" />
          </Form.Item>
          <Form.Item
            label="确认密码"
            name="confirmPassword"
            dependencies={['password']}
            rules={[
              { required: true, message: '请确认密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('password') === value) return Promise.resolve()
                  return Promise.reject(new Error('两次输入的密码不一致'))
                },
              }),
            ]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="请再次输入密码" />
          </Form.Item>
            <Button size="large" type="primary" htmlType="submit" block loading={loading}>
              创建账号
            </Button>
            <div className="auth-switch">
              已有账号？
              <Link style={{ color: token.colorPrimary }} to="/login">
                返回登录
              </Link>
            </div>
          </Form>
        </section>
      </div>
    </div>
  )
}
