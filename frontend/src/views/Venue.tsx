import { useCallback, useEffect, useState } from 'react'
import {
  Button,
  Card,
  Col,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Rate,
  Row,
  Select,
  Spin,
  Switch,
  Table,
  Tag,
  theme,
  TimePicker,
  type TableColumnsType,
} from 'antd'
import {
  AppstoreOutlined,
  ClockCircleOutlined,
  EnvironmentOutlined,
  PlusOutlined,
  StarOutlined,
} from '@ant-design/icons'
import dayjs, { type Dayjs } from 'dayjs'

import { venueApi } from '@/api'
import type { Venue as VenueRecord, VenuePayload } from '@/api/types'
import ReservationDialog from '@/components/ReservationDialog'
import { useUserStore } from '@/store/user'
import { feedback } from '@/utils/feedback'

const PAGE_SIZE = 10

const STATUS_OPTIONS = [
  { label: '开放预约', value: 1 },
  { label: '暂停开放', value: 0 },
]

interface VenueFormValues extends VenuePayload {
  status: number
}

export default function Venue() {
  const isAdmin = useUserStore((state) => state.user?.role === 'admin')
  const { token } = theme.useToken()

  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [venues, setVenues] = useState<VenueRecord[]>([])
  const [total, setTotal] = useState(0)
  const [keywordInput, setKeywordInput] = useState('')
  const [query, setQuery] = useState<{ keyword: string; status: number | ''; page: number }>({
    keyword: '',
    status: '',
    page: 1,
  })

  const [formOpen, setFormOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form] = Form.useForm<VenueFormValues>()

  const [reservationOpen, setReservationOpen] = useState(false)
  const [currentVenue, setCurrentVenue] = useState<VenueRecord | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await venueApi.list({
        keyword: query.keyword,
        status: query.status,
        page: query.page,
        page_size: PAGE_SIZE,
      })
      setVenues(data.items)
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

  const search = () => setQuery((prev) => ({ ...prev, keyword: keywordInput, page: 1 }))

  const openForm = (row?: VenueRecord) => {
    setEditingId(row?.id ?? null)
    form.setFieldsValue({
      name: row?.name || '',
      city: row?.city || '',
      address: row?.address || '',
      rating: row?.rating || 4,
      room_count: row?.room_count || 10,
      open_time: row?.open_time || '09:00',
      close_time: row?.close_time || '18:00',
      status: row?.status ?? 1,
      description: row?.description || '',
    })
    setFormOpen(true)
  }

  const submitForm = async () => {
    const values = await form.validateFields().catch(() => null)
    if (!values) return
    setSubmitting(true)
    try {
      if (editingId) await venueApi.update(editingId, values)
      else await venueApi.create(values)
      feedback.success('保存成功')
      setFormOpen(false)
      await load()
    } finally {
      setSubmitting(false)
    }
  }

  const remove = (row: VenueRecord) => {
    feedback.confirm({
      title: '提示',
      content: `确定删除会议空间「${row.name}」吗？`,
      okText: '确定',
      cancelText: '取消',
      onOk: async () => {
        await venueApi.remove(row.id)
        feedback.success('删除成功')
        await load()
      },
    })
  }

  const openReservation = (row: VenueRecord) => {
    setCurrentVenue(row)
    setReservationOpen(true)
  }

  const columns: TableColumnsType<VenueRecord> = [
    { title: '空间名称', dataIndex: 'name', width: 180, ellipsis: true },
    { title: '城市', dataIndex: 'city', width: 80 },
    { title: '地址', dataIndex: 'address', width: 180, ellipsis: true },
    { title: '配套等级', width: 90, render: (_, row) => `${row.rating} 级` },
    { title: '会议室总数', dataIndex: 'room_count', width: 100 },
    {
      title: '开放时段',
      width: 120,
      render: (_, row) => `${row.open_time} - ${row.close_time}`,
    },
    { title: '会议室规格', dataIndex: 'meeting_room_count', width: 100 },
    { title: '预约', dataIndex: 'reservation_count', width: 70 },
    {
      title: '状态',
      width: 100,
      render: (_, row) => (
        <Tag color={row.status === 1 ? 'success' : 'default'}>
          {row.status === 1 ? '开放预约' : '暂停开放'}
        </Tag>
      ),
    },
    {
      title: '操作',
      width: 150,
      fixed: 'right',
      render: (_, row) => (
        <>
          <Button type="link" onClick={() => openReservation(row)}>
            预约
          </Button>
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
          <div className="page-title">会议空间管理</div>
          <div className="page-toolbar">
            <Input.Search
              value={keywordInput}
              placeholder="搜索空间名称/地址"
              allowClear
              style={{ width: 220 }}
              onChange={(event) => setKeywordInput(event.target.value)}
              onSearch={search}
            />
            <Select
              value={query.status === '' ? undefined : query.status}
              placeholder="开放状态"
              allowClear
              style={{ width: 140 }}
              options={STATUS_OPTIONS}
              onChange={(value) => setQuery((prev) => ({ ...prev, status: value ?? '', page: 1 }))}
            />
            {isAdmin && (
              <Button type="primary" icon={<PlusOutlined />} onClick={() => openForm()}>
                新增空间
              </Button>
            )}
          </div>
        </div>
      </Card>

      {isAdmin ? (
        <Card variant="borderless" style={{ marginTop: 16 }}>
          <Table<VenueRecord>
            rowKey="id"
            loading={loading}
            columns={columns}
            dataSource={venues}
            scroll={{ x: 1120 }}
            locale={{ emptyText: '暂无会议空间数据' }}
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
      ) : (
        <Spin spinning={loading}>
          <Row gutter={16} style={{ marginTop: 16 }}>
            {venues.map((item) => (
              <Col key={item.id} xs={24} sm={12} lg={8}>
                <Card variant="borderless" hoverable style={{ marginBottom: 16 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 16, fontWeight: 'bold' }}>{item.name}</span>
                    <Tag color={item.status === 1 ? 'success' : 'default'}>
                      {item.status === 1 ? '开放预约' : '暂停开放'}
                    </Tag>
                  </div>
                  <div style={{ marginTop: 10, color: token.colorTextSecondary, lineHeight: '24px' }}>
                    <div>
                      <EnvironmentOutlined /> {item.city} · {item.address || '地址待补充'}
                    </div>
                    <div>
                      <StarOutlined /> {item.rating} 级会议空间 · 共 {item.room_count} 间会议室
                    </div>
                    <div>
                      <ClockCircleOutlined /> 开放时段 {item.open_time} - {item.close_time}
                    </div>
                    <div>
                      <AppstoreOutlined /> 可预约会议室规格 {item.meeting_room_count} 个
                    </div>
                  </div>
                  <div style={{ marginTop: 10, color: token.colorTextTertiary, minHeight: 40 }}>
                    {item.description}
                  </div>
                  <Button
                    type="primary"
                    block
                    style={{ marginTop: 8 }}
                    disabled={item.status !== 1}
                    onClick={() => openReservation(item)}
                  >
                    立即预约
                  </Button>
                </Card>
              </Col>
            ))}
            {!venues.length && (
              <Col span={24}>
                <Empty description="暂无可预约的会议空间" />
              </Col>
            )}
          </Row>
        </Spin>
      )}

      <Modal
        title={editingId ? '编辑会议空间' : '新增会议空间'}
        open={formOpen}
        width={560}
        okText="保存"
        cancelText="取消"
        confirmLoading={submitting}
        onOk={submitForm}
        onCancel={() => setFormOpen(false)}
      >
        <Form form={form} labelCol={{ span: 6 }} wrapperCol={{ span: 18 }} style={{ marginTop: 20 }}>
          <Form.Item label="空间名称" name="name" rules={[{ required: true, message: '请输入空间名称' }]}>
            <Input placeholder="例如：杭州西湖商务中心" />
          </Form.Item>
          <Form.Item label="城市" name="city" rules={[{ required: true, message: '请输入城市' }]}>
            <Input placeholder="例如：杭州" />
          </Form.Item>
          <Form.Item label="地址" name="address">
            <Input placeholder="例如：西湖区文三路 88 号" />
          </Form.Item>
          <Form.Item label="配套等级" name="rating">
            <Rate />
          </Form.Item>
          <Form.Item label="会议室总数" name="room_count" rules={[{ required: true, message: '请输入会议室总数' }]}>
            <InputNumber min={1} max={5000} />
          </Form.Item>
          <Form.Item
            label="开放时间"
            name="open_time"
            rules={[{ required: true, message: '请选择开放时间' }]}
            getValueProps={(value?: string) => ({ value: value ? dayjs(value, 'HH:mm') : undefined })}
            normalize={(value?: Dayjs | null) => (value ? value.format('HH:mm') : '')}
          >
            <TimePicker format="HH:mm" minuteStep={30} style={{ width: 150 }} />
          </Form.Item>
          <Form.Item
            label="关闭时间"
            name="close_time"
            rules={[{ required: true, message: '请选择关闭时间' }]}
            getValueProps={(value?: string) => ({ value: value ? dayjs(value, 'HH:mm') : undefined })}
            normalize={(value?: Dayjs | null) => (value ? value.format('HH:mm') : '')}
          >
            <TimePicker format="HH:mm" minuteStep={30} style={{ width: 150 }} />
          </Form.Item>
          <Form.Item
            label="开放状态"
            name="status"
            getValueProps={(value?: number) => ({ checked: value === 1 })}
            normalize={(checked?: boolean) => (checked ? 1 : 0)}
          >
            <Switch checkedChildren="开放预约" unCheckedChildren="暂停开放" />
          </Form.Item>
          <Form.Item label="空间简介">
            <Form.Item name="description" noStyle>
              <Input.TextArea rows={3} maxLength={200} showCount />
            </Form.Item>
          </Form.Item>
        </Form>
      </Modal>

      <ReservationDialog
        open={reservationOpen}
        venue={currentVenue}
        venues={venues}
        onClose={() => setReservationOpen(false)}
        onSuccess={load}
      />
    </div>
  )
}
