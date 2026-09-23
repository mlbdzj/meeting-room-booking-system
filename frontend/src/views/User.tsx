import { useCallback, useEffect, useState } from 'react'
import { Button, Card, Form, Input, Modal, Select, Switch, Table, Tag, type TableColumnsType } from 'antd'
import { PlusOutlined } from '@ant-design/icons'

import { userApi } from '@/api'
import type { Role, UserCreatePayload, UserInfo, UserPayload } from '@/api/types'
import { ROLE_TEXT, useUserStore } from '@/store/user'
import { feedback } from '@/utils/feedback'
import { toDateTimeString } from '@/utils/format'

const PAGE_SIZE = 10

const ROLE_OPTIONS: { label: string; value: Role }[] = [
  { label: ROLE_TEXT.admin, value: 'admin' },
  { label: ROLE_TEXT.user, value: 'user' },
]

interface UserFormValues extends UserPayload {
  username: string
  password?: string
}

export default function UserPage() {
  const currentUserId = useUserStore((state) => state.user?.id)

  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [records, setRecords] = useState<UserInfo[]>([])
  const [total, setTotal] = useState(0)
  const [keywordInput, setKeywordInput] = useState('')
  const [query, setQuery] = useState<{ keyword: string; role: Role | ''; page: number }>({
    keyword: '',
    role: '',
    page: 1,
  })

  const [formOpen, setFormOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form] = Form.useForm<UserFormValues>()

  const [resetOpen, setResetOpen] = useState(false)
  const [resetTarget, setResetTarget] = useState<UserInfo | null>(null)
  const [resetForm] = Form.useForm<{ new_password: string }>()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await userApi.page({
        keyword: query.keyword,
        role: query.role,
        page: query.page,
        page_size: PAGE_SIZE,
      })
      setRecords(data.items)
      setTotal(data.total)
    } catch {
      // 请求层已经提示过错误
    } finally {
      setLoading(false)
    }
  }, [query])

  useEffect(() => {
    void load()
  }, [load])

  const openForm = (row?: UserInfo) => {
    setEditingId(row?.id ?? null)
    form.setFieldsValue({
      username: row?.username || '',
      password: '',
      name: row?.name || '',
      phone: row?.phone || '',
      email: row?.email || '',
      role: row?.role || 'user',
      status: row?.status ?? 1,
    })
    setFormOpen(true)
  }

  const submitForm = async () => {
    const values = await form.validateFields().catch(() => null)
    if (!values) return
    setSubmitting(true)
    try {
      const base: UserPayload = {
        name: values.name,
        phone: values.phone,
        email: values.email,
        role: values.role,
        status: values.status,
      }
      if (editingId) {
        const updated = await userApi.update(editingId, base)
        if (updated.id === currentUserId) useUserStore.getState().setUser(updated)
      } else {
        const payload: UserCreatePayload = {
          ...base,
          username: values.username.trim(),
          password: values.password || '',
        }
        await userApi.create(payload)
      }
      feedback.success('保存成功')
      setFormOpen(false)
      await load()
    } finally {
      setSubmitting(false)
    }
  }

  const toggleStatus = async (row: UserInfo, checked: boolean) => {
    const nextStatus = checked ? 1 : 0
    try {
      await userApi.update(row.id, {
        name: row.name,
        phone: row.phone,
        email: row.email,
        role: row.role,
        status: nextStatus,
      })
      setRecords((prev) => prev.map((item) => (item.id === row.id ? { ...item, status: nextStatus } : item)))
      feedback.success(nextStatus === 1 ? '账号已启用' : '账号已禁用')
    } catch {
      await load()
    }
  }

  const openReset = (row: UserInfo) => {
    setResetTarget(row)
    resetForm.resetFields()
    setResetOpen(true)
  }

  const submitReset = async () => {
    const values = await resetForm.validateFields().catch(() => null)
    if (!values || !resetTarget) return
    setSubmitting(true)
    try {
      await userApi.resetPassword(resetTarget.id, { new_password: values.new_password })
      feedback.success('密码重置成功')
      setResetOpen(false)
    } finally {
      setSubmitting(false)
    }
  }

  const remove = (row: UserInfo) => {
    feedback.confirm({
      title: '提示',
      content: `确定删除会员「${row.name || row.username}」吗？`,
      okText: '确定',
      cancelText: '取消',
      onOk: async () => {
        await userApi.remove(row.id)
        feedback.success('删除成功')
        await load()
      },
    })
  }

  const columns: TableColumnsType<UserInfo> = [
    { title: '账号', dataIndex: 'username', width: 130 },
    { title: '姓名', dataIndex: 'name', width: 110 },
    { title: '手机号', width: 130, render: (_, row) => row.phone || '-' },
    { title: '邮箱', width: 170, render: (_, row) => row.email || '-' },
    {
      title: '角色',
      width: 110,
      render: (_, row) => <Tag color={row.role === 'admin' ? 'error' : 'success'}>{ROLE_TEXT[row.role]}</Tag>,
    },
    {
      title: '状态',
      width: 100,
      render: (_, row) => (
        <Switch
          checked={row.status === 1}
          disabled={row.id === currentUserId}
          onChange={(checked) => void toggleStatus(row, checked)}
        />
      ),
    },
    { title: '创建时间', width: 170, render: (_, row) => toDateTimeString(row.created_at) },
    {
      title: '操作',
      width: 200,
      fixed: 'right',
      render: (_, row) => (
        <>
          <Button type="link" onClick={() => openForm(row)}>
            编辑
          </Button>
          <Button type="link" style={{ color: '#e6a23c' }} onClick={() => openReset(row)}>
            重置密码
          </Button>
          <Button type="link" danger disabled={row.id === currentUserId} onClick={() => remove(row)}>
            删除
          </Button>
        </>
      ),
    },
  ]

  return (
    <div>
      <Card variant="borderless">
        <div className="page-block-head">
          <div className="page-title">会员管理</div>
          <div className="page-toolbar">
            <Input.Search
              value={keywordInput}
              placeholder="搜索会员账号/姓名/手机号"
              allowClear
              style={{ width: 220 }}
              onChange={(event) => setKeywordInput(event.target.value)}
              onSearch={() => setQuery((prev) => ({ ...prev, keyword: keywordInput, page: 1 }))}
            />
            <Select
              value={query.role === '' ? undefined : query.role}
              placeholder="全部角色"
              allowClear
              style={{ width: 140 }}
              options={ROLE_OPTIONS}
              onChange={(value) => setQuery((prev) => ({ ...prev, role: value ?? '', page: 1 }))}
            />
            <Button type="primary" icon={<PlusOutlined />} onClick={() => openForm()}>
              新增会员
            </Button>
          </div>
        </div>
      </Card>

      <Card variant="borderless" style={{ marginTop: 16 }}>
        <Table<UserInfo>
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={records}
          scroll={{ x: 1200 }}
          locale={{ emptyText: '暂无会员数据' }}
          pagination={{
            current: query.page,
            pageSize: PAGE_SIZE,
            total,
            showSizeChanger: false,
            showTotal: (value) => `共 ${value} 条`,
            onChange: (page) => setQuery((prev) => ({ ...prev, page })),
          }}
        />
      </Card>

      <Modal
        title={editingId ? '编辑用户' : '新增会员'}
        open={formOpen}
        width={500}
        okText="保存"
        cancelText="取消"
        confirmLoading={submitting}
        onOk={submitForm}
        onCancel={() => setFormOpen(false)}
      >
        <Form form={form} labelCol={{ span: 6 }} wrapperCol={{ span: 18 }} style={{ marginTop: 20 }}>
          <Form.Item
            label="账号"
            name="username"
            rules={[
              { required: true, message: '请输入账号' },
              { min: 3, max: 20, message: '账号长度为 3-20 位' },
            ]}
          >
            <Input disabled={Boolean(editingId)} placeholder="请输入登录账号" />
          </Form.Item>
          {!editingId && (
            <Form.Item
              label="初始密码"
              name="password"
              rules={[
                { required: true, message: '请输入初始密码' },
                { min: 6, message: '密码至少 6 位' },
              ]}
            >
              <Input.Password placeholder="至少 6 位" />
            </Form.Item>
          )}
          <Form.Item label="姓名" name="name" rules={[{ required: true, message: '请输入姓名' }]}>
            <Input placeholder="请输入姓名" />
          </Form.Item>
          <Form.Item label="手机号" name="phone">
            <Input placeholder="请输入手机号" />
          </Form.Item>
          <Form.Item label="邮箱" name="email">
            <Input placeholder="请输入邮箱" />
          </Form.Item>
          <Form.Item label="角色" name="role">
            <Select options={ROLE_OPTIONS} />
          </Form.Item>
          <Form.Item
            label="状态"
            name="status"
            getValueProps={(value?: number) => ({ checked: value === 1 })}
            normalize={(checked?: boolean) => (checked ? 1 : 0)}
          >
            <Switch checkedChildren="正常" unCheckedChildren="禁用" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="重置密码"
        open={resetOpen}
        width={440}
        okText="确定"
        cancelText="取消"
        confirmLoading={submitting}
        onOk={submitReset}
        onCancel={() => setResetOpen(false)}
      >
        <Form form={resetForm} labelCol={{ span: 5 }} wrapperCol={{ span: 19 }} style={{ marginTop: 20 }}>
          <Form.Item label="账号">
            <Input value={resetTarget?.username} disabled />
          </Form.Item>
          <Form.Item
            label="新密码"
            name="new_password"
            rules={[
              { required: true, message: '请输入新密码' },
              { min: 6, message: '密码至少 6 位' },
            ]}
          >
            <Input.Password placeholder="至少 6 位" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
