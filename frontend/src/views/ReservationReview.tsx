import { useCallback, useEffect, useState } from 'react'
import {
  Button,
  Card,
  DatePicker,
  Descriptions,
  Form,
  Input,
  Modal,
  Select,
  Table,
  Tag,
  type TableColumnsType,
} from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import dayjs, { type Dayjs } from 'dayjs'

import { reservationApi, venueApi } from '@/api'
import type { Reservation, Venue } from '@/api/types'
import { RESERVATION_STATUS_COLOR, RESERVATION_STATUS_TEXT } from '@/store/user'
import { feedback } from '@/utils/feedback'
import { money, stayRange } from '@/utils/format'

const PAGE_SIZE = 10
const DAY_FORMAT = 'YYYY-MM-DD'

const STATUS_OPTIONS = Object.entries(RESERVATION_STATUS_TEXT).map(([value, label]) => ({ value, label }))

export default function ReservationReview() {
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [records, setRecords] = useState<Reservation[]>([])
  const [venues, setVenues] = useState<Venue[]>([])
  const [total, setTotal] = useState(0)
  const [keywordInput, setKeywordInput] = useState('')
  // 默认不限定状态：管理员既能一眼看到待确认预约（列表按待确认优先排序），也能看到已完成等历史预约
  const [query, setQuery] = useState<{
    status: string
    venue_id: number | ''
    start_at: string
    keyword: string
    page: number
  }>({ status: '', venue_id: '', start_at: '', keyword: '', page: 1 })

  const [reviewOpen, setReviewOpen] = useState(false)
  const [reviewRow, setReviewRow] = useState<Reservation | null>(null)
  const [reviewAction, setReviewAction] = useState<'confirm' | 'reject'>('confirm')
  const [reviewForm] = Form.useForm<{ remark: string }>()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await reservationApi.page({
        status: query.status,
        venue_id: query.venue_id,
        start_at: query.start_at,
        keyword: query.keyword,
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

  const emptyText = query.status
    ? `没有「${RESERVATION_STATUS_TEXT[query.status as keyof typeof RESERVATION_STATUS_TEXT]}」的预约，选择「全部状态」可查看历史预约`
    : '暂无预约记录'

  const openReview = (row: Reservation, action: 'confirm' | 'reject') => {
    setReviewRow(row)
    setReviewAction(action)
    reviewForm.setFieldsValue({ remark: action === 'confirm' ? '已确认，房间已保留' : '' })
    setReviewOpen(true)
  }

  const submitReview = async () => {
    if (!reviewRow) return
    const values = await reviewForm.validateFields().catch(() => null)
    if (!values) return
    setSubmitting(true)
    try {
      await reservationApi.review(reviewRow.id, { action: reviewAction, remark: values.remark || '' })
      feedback.success(reviewAction === 'confirm' ? '预约已确认' : '预约已拒绝')
      setReviewOpen(false)
      await load()
    } finally {
      setSubmitting(false)
    }
  }

  const cancel = (row: Reservation) => {
    feedback.confirm({
      title: '提示',
      content: `确定取消「${row.user_name}」在「${row.venue_name}」的预约吗？`,
      okText: '确定',
      cancelText: '取消',
      onOk: async () => {
        await reservationApi.cancel(row.id)
        feedback.success('预约已取消')
        await load()
      },
    })
  }

  const remove = (row: Reservation) => {
    feedback.confirm({
      title: '提示',
      content: '删除后不可恢复，确定删除该预约吗？',
      okText: '确定',
      cancelText: '取消',
      onOk: async () => {
        await reservationApi.remove(row.id)
        feedback.success('删除成功')
        await load()
      },
    })
  }

  const columns: TableColumnsType<Reservation> = [
    {
      title: '会员',
      width: 120,
      render: (_, row) => (
        <div>
          <div>{row.user_name}</div>
          <div style={{ color: '#909399', fontSize: 12 }}>{row.username}</div>
        </div>
      ),
    },
    {
      title: '会议空间 / 会议室类型',
      width: 200,
      ellipsis: true,
      render: (_, row) => (
        <div>
          <div>{row.venue_name}</div>
          <div style={{ color: '#909399', fontSize: 12 }}>{row.meeting_room_name}</div>
        </div>
      ),
    },
    { title: '使用开始 / 使用结束', width: 190, render: (_, row) => stayRange(row) },
    { title: '间数 / 人数', width: 110, render: (_, row) => `${row.rooms} 间 / ${row.attendees} 人` },
    { title: '总价', width: 100, render: (_, row) => money(row.total_amount) },
    {
      title: '状态',
      width: 100,
      render: (_, row) => <Tag color={RESERVATION_STATUS_COLOR[row.status]}>{row.status_text}</Tag>,
    },
    { title: '确认意见', dataIndex: 'remark', width: 140, ellipsis: true, render: (value: string) => value || '-' },
    {
      title: '操作',
      width: 200,
      fixed: 'right',
      render: (_, row) => (
        <>
          {row.status === 'pending' && (
            <>
              <Button type="link" style={{ color: '#67c23a' }} onClick={() => openReview(row, 'confirm')}>
                确认
              </Button>
              <Button type="link" danger onClick={() => openReview(row, 'reject')}>
                拒绝
              </Button>
            </>
          )}
          {(row.status === 'pending' || row.status === 'confirmed') && (
            <Button type="link" style={{ color: '#e6a23c' }} onClick={() => cancel(row)}>
              取消
            </Button>
          )}
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
          <div className="page-title">预约确认</div>
          <div className="page-toolbar">
            <Select
              value={query.status === '' ? undefined : query.status}
              placeholder="全部状态"
              allowClear
              style={{ width: 140 }}
              options={STATUS_OPTIONS}
              onChange={(value) => setQuery((prev) => ({ ...prev, status: value ?? '', page: 1 }))}
            />
            <Select
              value={query.venue_id === '' ? undefined : query.venue_id}
              placeholder="全部会议空间"
              allowClear
              style={{ width: 190 }}
              options={venues.map((item) => ({ value: item.id, label: item.name }))}
              onChange={(value) => setQuery((prev) => ({ ...prev, venue_id: value ?? '', page: 1 }))}
            />
            <DatePicker
              value={query.start_at ? dayjs(query.start_at, DAY_FORMAT) : null}
              placeholder="使用开始日期"
              style={{ width: 160 }}
              onChange={(value: Dayjs | null) =>
                setQuery((prev) => ({
                  ...prev,
                  start_at: value ? value.format(DAY_FORMAT) : '',
                  page: 1,
                }))
              }
            />
            <Input.Search
              value={keywordInput}
              placeholder="搜索会员"
              allowClear
              style={{ width: 170 }}
              onChange={(event) => setKeywordInput(event.target.value)}
              onSearch={() => setQuery((prev) => ({ ...prev, keyword: keywordInput, page: 1 }))}
            />
            <Button icon={<ReloadOutlined />} onClick={() => setQuery((prev) => ({ ...prev }))}>
              刷新
            </Button>
          </div>
        </div>
      </Card>

      <Card variant="borderless" style={{ marginTop: 16 }}>
        <Table<Reservation>
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={records}
          scroll={{ x: 1400 }}
          locale={{ emptyText }}
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
        title={reviewAction === 'confirm' ? '确认预约' : '拒绝预约'}
        open={reviewOpen}
        width={500}
        okText={`确定${reviewAction === 'confirm' ? '确认' : '拒绝'}`}
        cancelText="取消"
        confirmLoading={submitting}
        onOk={submitReview}
        onCancel={() => setReviewOpen(false)}
      >
        <Descriptions
          column={1}
          bordered
          size="small"
          style={{ marginTop: 20, marginBottom: 16 }}
          items={[
            { key: 'venue', label: '会议空间', children: reviewRow?.venue_name },
            { key: 'room', label: '会议室类型', children: reviewRow?.meeting_room_name },
            { key: 'user', label: '会员', children: reviewRow?.user_name },
            {
              key: 'dates',
              label: '使用开始 / 使用结束',
              children: reviewRow ? stayRange(reviewRow) : '',
            },
            {
              key: 'rooms',
              label: '间数 / 人数',
              children: reviewRow ? `${reviewRow.rooms} 间 / ${reviewRow.attendees} 人` : '',
            },
            { key: 'amount', label: '总价', children: money(reviewRow?.total_amount) },
          ]}
        />
        <Form form={reviewForm} layout="vertical">
          <Form.Item label="确认意见" name="remark">
            <Input.TextArea rows={3} maxLength={255} showCount />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
