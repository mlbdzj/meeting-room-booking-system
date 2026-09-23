import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button, Form, Input } from 'antd'
import { IdcardOutlined, LockOutlined, PhoneOutlined, UserOutlined } from '@ant-design/icons'

import { authApi } from '@/api'
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
    <div className="register-container">
      <div className="register-box">
        <h1 style={{ fontSize: 24, marginBottom: 26 }}>欢迎注册智能会议室预约系统</h1>

        <Form form={form} labelCol={{ span: 5 }} wrapperCol={{ span: 19 }} size="large" onFinish={submit}>
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
            注 册
          </Button>
          <div style={{ textAlign: 'right', marginTop: 18 }}>
            已有账号？请
            <Link style={{ color: '#409eff' }} to="/login">
              登录
            </Link>
          </div>
        </Form>
      </div>
    </div>
  )
}
