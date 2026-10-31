import { useCallback, useEffect, useState } from 'react'
import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Table,
  Tag,
  type TableColumnsType,
} from 'antd'
import { PlusOutlined } from '@ant-design/icons'

import { meetingRoomApi, venueApi } from '@/api'
import type {
  MeetingRoom as MeetingRoomRecord,
  MeetingRoomPayload,
  MeetingRoomStatus,
  Venue,
} from '@/api/types'
import { MEETING_ROOM_STATUS_COLOR, MEETING_ROOM_STATUS_TEXT } from '@/store/user'
import { feedback } from '@/utils/feedback'
import { money } from '@/utils/format'

const PAGE_SIZE = 10
const STATUS_OPTIONS = Object.entries(MEETING_ROOM_STATUS_TEXT).map(([value, label]) => ({
  value,
  label,
}))

export default function MeetingRoom() {
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [records, setRecords] = useState<MeetingRoomRecord[]>([])
  const [venues, setVenues] = useState<Venue[]>([])
  const [total, setTotal] = useState(0)
  const [keywordInput, setKeywordInput] = useState('')
  const [query, setQuery] = useState<{
    keyword: string
    venue_id: number | ''
    status: MeetingRoomStatus | ''
    page: number
  }>({ keyword: '', venue_id: '', status: '', page: 1 })

  const [formOpen, setFormOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form] = Form.useForm<MeetingRoomPayload>()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await meetingRoomApi.page({
        keyword: query.keyword,
        venue_id: query.venue_id,
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

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    venueApi
      .list({ page_size: 100 })
      .then((data) => setVenues(data.items))
      .catch(() => setVenues([]))
  }, [])

  const openForm = (row?: MeetingRoomRecord) => {
    setEditingId(row?.id ?? null)
    form.setFieldsValue({
      name: row?.name || '',
      code: row?.code || '',
      layout: row?.layout || '',
      venue_id: row?.venue_id ?? (query.venue_id || venues[0]?.id),
      hourly_price: row?.hourly_price ?? 0,
      capacity: row?.capacity ?? 10,
      quantity: row?.quantity ?? 1,
      equipment: row?.equipment || '',
      status: row?.status || 'open',
      description: row?.description || '',
    })
    setFormOpen(true)
  }

  const submitForm = async () => {
    const values = await form.validateFields().catch(() => null)
    if (!values) return
    setSubmitting(true)
    try {
      if (editingId) await meetingRoomApi.update(editingId, values)
      else await meetingRoomApi.create(values)
      feedback.success('保存成功')
      setFormOpen(false)
      await load()
    } finally {
      setSubmitting(false)
    }
  }

  const remove = (row: MeetingRoomRecord) => {
    feedback.confirm({
      title: '提示',
      content: `确定删除会议室规格「${row.name}」吗？`,
      okText: '确定',
      cancelText: '取消',
      onOk: async () => {
        await meetingRoomApi.remove(row.id)
        feedback.success('删除成功')
        await load()
      },
    })
  }

  const columns: TableColumnsType<MeetingRoomRecord> = [
    { title: '会议室名称', dataIndex: 'name', width: 140, ellipsis: true },
    { title: '编号', dataIndex: 'code', width: 110 },
    { title: '布局', dataIndex: 'layout', width: 100 },
    { title: '所属空间', dataIndex: 'venue_name', width: 160, ellipsis: true },
    { title: '时租价', width: 90, render: (_, row) => `${money(row.hourly_price)}/时` },
    { title: '容纳人数', dataIndex: 'capacity', width: 90 },
    { title: '数量', dataIndex: 'quantity', width: 70 },
    { title: '设备', dataIndex: 'equipment', width: 160, ellipsis: true },
    {
      title: '状态',
      width: 90,
      render: (_, row) => (
        <Tag color={MEETING_ROOM_STATUS_COLOR[row.status]}>
          {MEETING_ROOM_STATUS_TEXT[row.status]}
        </Tag>
      ),
    },
    {
      title: '操作',
      width: 110,
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
          <div className="page-title">会议室管理</div>
          <div className="page-toolbar">
            <Input.Search
              value={keywordInput}
              placeholder="搜索会议室名称/编号/布局/设备"
              allowClear
              style={{ width: 250 }}
              onChange={(event) => setKeywordInput(event.target.value)}
              onSearch={() => setQuery((prev) => ({ ...prev, keyword: keywordInput, page: 1 }))}
            />
            <Select
              value={query.venue_id === '' ? undefined : query.venue_id}
              placeholder="全部空间"
              allowClear
              style={{ width: 190 }}
              options={venues.map((item) => ({ value: item.id, label: item.name }))}
              onChange={(value) => setQuery((prev) => ({ ...prev, venue_id: value ?? '', page: 1 }))}
            />
            <Select
              value={query.status === '' ? undefined : query.status}
              placeholder="全部状态"
              allowClear
              style={{ width: 140 }}
              options={STATUS_OPTIONS}
              onChange={(value) => setQuery((prev) => ({ ...prev, status: value ?? '', page: 1 }))}
            />
            <Button type="primary" icon={<PlusOutlined />} onClick={() => openForm()}>
              新增会议室
            </Button>
          </div>
        </div>
      </Card>

      <Card variant="borderless" style={{ marginTop: 16 }}>
        <Table<MeetingRoomRecord>
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={records}
          scroll={{ x: 1220 }}
          locale={{ emptyText: '暂无会议室数据' }}
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
        title={editingId ? '编辑会议室' : '新增会议室'}
        open={formOpen}
        width={580}
        okText="保存"
        cancelText="取消"
        confirmLoading={submitting}
        onOk={submitForm}
        onCancel={() => setFormOpen(false)}
      >
        <Form form={form} labelCol={{ span: 6 }} wrapperCol={{ span: 18 }} style={{ marginTop: 20 }}>
          <Form.Item label="会议室名称" name="name" rules={[{ required: true, message: '请输入会议室名称' }]}>
            <Input placeholder="例如：西湖 A 会议室" />
          </Form.Item>
          <Form.Item label="会议室编号" name="code">
            <Input placeholder="例如：MR-HZ-001" />
          </Form.Item>
          <Form.Item label="布局" name="layout">
            <Input placeholder="例如：U 型 / 课桌式 / 剧院式" />
          </Form.Item>
          <Form.Item label="所属空间" name="venue_id" rules={[{ required: true, message: '请选择所属空间' }]}>
            <Select
              placeholder="请选择会议空间"
              options={venues.map((item) => ({ value: item.id, label: item.name }))}
            />
          </Form.Item>
          <Form.Item label="时租价" name="hourly_price" rules={[{ required: true, message: '请输入时租价' }]}>
            <InputNumber min={0} max={999999} step={10} />
          </Form.Item>
          <Form.Item label="容纳人数" name="capacity">
            <InputNumber min={1} max={500} />
          </Form.Item>
          <Form.Item label="会议室数量" name="quantity" rules={[{ required: true, message: '请输入数量' }]}>
            <InputNumber min={1} max={999} />
          </Form.Item>
          <Form.Item label="设备">
            <Form.Item name="equipment" noStyle>
              <Input.TextArea
                rows={2}
                maxLength={500}
                showCount
                placeholder="例如：双屏、无线投屏、视频会议、白板"
              />
            </Form.Item>
          </Form.Item>
          <Form.Item label="状态" name="status" rules={[{ required: true, message: '请选择状态' }]}>
            <Select options={STATUS_OPTIONS} />
          </Form.Item>
          <Form.Item label="说明">
            <Form.Item name="description" noStyle>
              <Input.TextArea rows={3} maxLength={200} showCount />
            </Form.Item>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
