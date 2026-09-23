import { useCallback, useEffect, useState } from 'react'
import { AutoComplete, Button, Card, Form, Input, Modal, Select, Switch, Table, Tag, type TableColumnsType } from 'antd'
import { PlusOutlined } from '@ant-design/icons'

import { knowledgeApi } from '@/api'
import type { Knowledge as KnowledgeRecord, KnowledgePayload } from '@/api/types'
import { feedback } from '@/utils/feedback'

const PAGE_SIZE = 10

const STATUS_OPTIONS = [
  { label: '启用', value: 1 },
  { label: '停用', value: 0 },
]

export default function Knowledge() {
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [records, setRecords] = useState<KnowledgeRecord[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [total, setTotal] = useState(0)
  const [keywordInput, setKeywordInput] = useState('')
  const [query, setQuery] = useState<{
    keyword: string
    category: string
    status: number | ''
    page: number
  }>({ keyword: '', category: '', status: '', page: 1 })

  const [formOpen, setFormOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form] = Form.useForm<KnowledgePayload>()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await knowledgeApi.page({
        keyword: query.keyword,
        category: query.category,
        status: query.status,
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

  const loadCategories = useCallback(async () => {
    try {
      setCategories(await knowledgeApi.categories())
    } catch {
      setCategories([])
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    void loadCategories()
  }, [loadCategories])

  const openForm = (row?: KnowledgeRecord) => {
    setEditingId(row?.id ?? null)
    form.setFieldsValue({
      category: row?.category || '常见问题',
      question: row?.question || '',
      answer: row?.answer || '',
      keywords: row?.keywords || '',
      status: row?.status ?? 1,
    })
    setFormOpen(true)
  }

  const submitForm = async () => {
    const values = await form.validateFields().catch(() => null)
    if (!values) return
    setSubmitting(true)
    try {
      if (editingId) await knowledgeApi.update(editingId, values)
      else await knowledgeApi.create(values)
      feedback.success('保存成功，助手会立即使用新的知识')
      setFormOpen(false)
      await load()
      await loadCategories()
    } finally {
      setSubmitting(false)
    }
  }

  const remove = (row: KnowledgeRecord) => {
    feedback.confirm({
      title: '提示',
      content: `确定删除知识条目「${row.question}」吗？`,
      okText: '确定',
      cancelText: '取消',
      onOk: async () => {
        await knowledgeApi.remove(row.id)
        feedback.success('删除成功')
        await load()
      },
    })
  }

  const columns: TableColumnsType<KnowledgeRecord> = [
    { title: '分类', dataIndex: 'category', width: 120 },
    { title: '问题', dataIndex: 'question', width: 200, ellipsis: true },
    { title: '答案', dataIndex: 'answer', width: 280, ellipsis: true },
    { title: '关键词', width: 160, ellipsis: true, render: (_, row) => row.keywords || '-' },
    {
      title: '状态',
      width: 90,
      render: (_, row) => (
        <Tag color={row.status === 1 ? 'success' : 'default'}>{row.status === 1 ? '启用' : '停用'}</Tag>
      ),
    },
    {
      title: '操作',
      width: 130,
      fixed: 'right',
      render: (_, row) => (
        <>
          <Button type="link" onClick={() => openForm(row)}>
            编辑
          </Button>
          <Button type="link" danger onClick={() => remove(row)}>
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
          <div>
            <div className="page-title">客服知识库</div>
            <div style={{ marginTop: 6, color: '#909399', fontSize: 13 }}>
              知识库是客服助手回答同学提问的依据，也是大模型不可用时的兜底答案，建议把常见问题都补充进来。
            </div>
          </div>
          <div className="page-toolbar">
            <Input.Search
              value={keywordInput}
              placeholder="搜索问题/答案/关键词"
              allowClear
              style={{ width: 220 }}
              onChange={(event) => setKeywordInput(event.target.value)}
              onSearch={() => setQuery((prev) => ({ ...prev, keyword: keywordInput, page: 1 }))}
            />
            <Select
              value={query.category === '' ? undefined : query.category}
              placeholder="全部分类"
              allowClear
              style={{ width: 150 }}
              options={categories.map((item) => ({ value: item, label: item }))}
              onChange={(value) => setQuery((prev) => ({ ...prev, category: value ?? '', page: 1 }))}
            />
            <Select
              value={query.status === '' ? undefined : query.status}
              placeholder="全部状态"
              allowClear
              style={{ width: 130 }}
              options={STATUS_OPTIONS}
              onChange={(value) => setQuery((prev) => ({ ...prev, status: value ?? '', page: 1 }))}
            />
            <Button type="primary" icon={<PlusOutlined />} onClick={() => openForm()}>
              新增条目
            </Button>
          </div>
        </div>
      </Card>

      <Card variant="borderless" style={{ marginTop: 16 }}>
        <Table<KnowledgeRecord>
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={records}
          scroll={{ x: 1100 }}
          locale={{ emptyText: '暂无知识库条目' }}
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
        title={editingId ? '编辑知识条目' : '新增知识条目'}
        open={formOpen}
        width={620}
        okText="保存"
        cancelText="取消"
        confirmLoading={submitting}
        onOk={submitForm}
        onCancel={() => setFormOpen(false)}
      >
        <Form form={form} labelCol={{ span: 5 }} wrapperCol={{ span: 19 }} style={{ marginTop: 20 }}>
          <Form.Item label="分类" name="category" rules={[{ required: true, message: '请选择或输入分类' }]}>
            <AutoComplete
              options={categories.map((item) => ({ value: item }))}
              placeholder="请选择或输入分类"
              filterOption={(input, option) => (option?.value ?? '').includes(input)}
            />
          </Form.Item>
          <Form.Item label="问题" name="question" rules={[{ required: true, message: '请输入问题' }]}>
            <Input placeholder="同学们可能这样问……" maxLength={200} showCount />
          </Form.Item>
          <Form.Item label="答案" name="answer" rules={[{ required: true, message: '请输入答案' }]}>
            <Input.TextArea rows={6} maxLength={1000} showCount />
          </Form.Item>
          <Form.Item label="关键词" name="keywords">
            <Input placeholder="用逗号分隔，例如：预约,怎么约,订会议空间" />
          </Form.Item>
          <Form.Item
            label="状态"
            name="status"
            getValueProps={(value?: number) => ({ checked: value === 1 })}
            normalize={(checked?: boolean) => (checked ? 1 : 0)}
          >
            <Switch checkedChildren="启用" unCheckedChildren="停用" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
