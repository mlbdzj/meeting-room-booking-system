import { useCallback, useEffect, useState } from 'react'
import { Button, Card, Select, Table, Tag, type TableColumnsType } from 'antd'
import { PlusOutlined } from '@ant-design/icons'

import { reservationApi, venueApi } from '@/api'
import type { Reservation as ReservationRecord, Venue } from '@/api/types'
import ReservationDialog from '@/components/ReservationDialog'
import { RESERVATION_STATUS_COLOR, RESERVATION_STATUS_TEXT } from '@/store/user'
import { feedback } from '@/utils/feedback'
import { money, stayRange } from '@/utils/format'

const PAGE_SIZE = 10

const STATUS_OPTIONS = Object.entries(RESERVATION_STATUS_TEXT).map(([value, label]) => ({ value, label }))

export default function Reservation() {
  const [loading, setLoading] = useState(false)
  const [records, setRecords] = useState<ReservationRecord[]>([])
  const [total, setTotal] = useState(0)
  const [venues, setVenues] = useState<Venue[]>([])
  const [dialogOpen, setDialogOpen] = useState(false)
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await reservationApi.my({ status, page, page_size: PAGE_SIZE })
      setRecords(data.items)
      setTotal(data.total)
    } catch {
      // 请求层已经提示过错误
    } finally {
      setLoading(false)
    }
  }, [page, status])

  const loadVenues = useCallback(async () => {
    try {
      const data = await venueApi.list({ page_size: 100, status: 1 })
      setVenues(data.items)
    } catch {
      // 请求层已经提示过错误
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    void loadVenues()
  }, [loadVenues])

  const cancel = (row: ReservationRecord) => {
    feedback.confirm({
      title: '提示',
      content: `确定取消「${row.venue_name} ${row.meeting_room_name}」的预约吗？`,
      okText: '确定',
      cancelText: '取消',
      onOk: async () => {
        await reservationApi.cancel(row.id)
        feedback.success('预约已取消')
        await load()
      },
    })
  }

  const columns: TableColumnsType<ReservationRecord> = [
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
      title: '特殊要求',
      dataIndex: 'equipment_request',
      width: 140,
      ellipsis: true,
      render: (value: string) => value || '-',
    },
    {
      title: '状态',
      width: 100,
      render: (_, row) => <Tag color={RESERVATION_STATUS_COLOR[row.status]}>{row.status_text}</Tag>,
    },
    {
      title: '确认意见',
      dataIndex: 'remark',
      width: 150,
      ellipsis: true,
      render: (value: string) => value || '-',
    },
    {
      title: '操作',
      width: 110,
      fixed: 'right',
      render: (_, row) =>
        row.status === 'pending' || row.status === 'confirmed' ? (
          <Button type="link" danger onClick={() => cancel(row)}>
            取消预约
          </Button>
        ) : (
          <span style={{ color: '#c0c4cc' }}>-</span>
        ),
    },
  ]

  return (
    <div>
      <Card variant="borderless">
        <div className="page-block-head">
          <div className="page-title">我的预约</div>
          <div className="page-toolbar">
            <Select
              value={status}
              placeholder="全部状态"
              allowClear
              style={{ width: 150 }}
              options={STATUS_OPTIONS}
              onChange={(value) => setStatus(value ?? '')}
            />
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setDialogOpen(true)}>
              预约会议空间
            </Button>
          </div>
        </div>
      </Card>

      <Card variant="borderless" style={{ marginTop: 16 }}>
        <Table<ReservationRecord>
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={records}
          scroll={{ x: 1100 }}
          locale={{ emptyText: '暂无预约，去「会议空间管理」预约一间吧' }}
          pagination={{
            current: page,
            pageSize: PAGE_SIZE,
            total,
            showSizeChanger: false,
            showTotal: (value) => `共 ${value} 条`,
            onChange: setPage,
          }}
        />
      </Card>

      <ReservationDialog
        open={dialogOpen}
        venues={venues}
        onClose={() => setDialogOpen(false)}
        onSuccess={load}
      />
    </div>
  )
}
