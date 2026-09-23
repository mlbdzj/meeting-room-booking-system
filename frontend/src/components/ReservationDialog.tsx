import { useCallback, useEffect, useState } from 'react'
import { DatePicker, Form, Input, InputNumber, Modal, Select, Tag, theme } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'

import { reservationApi, venueApi } from '@/api'
import type { Availability, AvailabilityMeetingRoom, Venue } from '@/api/types'
import { feedback } from '@/utils/feedback'
import { money } from '@/utils/format'

const DAY_FORMAT = 'YYYY-MM-DD'

export interface ReservationDialogProps {
  open: boolean
  /** 指定会议空间时锁定会议空间选择（从会议空间页「预约」按钮进入） */
  venue?: Venue | null
  venues?: Venue[]
  onClose: () => void
  onSuccess?: () => void
}

interface ReservationFormValues {
  venue_id: number
  date_range: [Dayjs, Dayjs]
  meeting_room_id: number
  rooms: number
  attendees: number
  equipment_request?: string
}

function disabledDate(current: Dayjs): boolean {
  return current.valueOf() < Date.now() - 24 * 60 * 60 * 1000
}

const roomTypeLabel = (item: AvailabilityMeetingRoom) =>
  `${item.name}（${item.layout}）${money(item.price)}/晚 · 剩余 ${item.remaining} 间`

export default function ReservationDialog({ open, venue, venues = [], onClose, onSuccess }: ReservationDialogProps) {
  const [form] = Form.useForm<ReservationFormValues>()
  const { token } = theme.useToken()
  const [submitting, setSubmitting] = useState(false)
  const [availabilityLoading, setAvailabilityLoading] = useState(false)
  const [venueList, setVenueList] = useState<Venue[]>([])
  const [availability, setAvailability] = useState<Availability | null>(null)
  const [roomTypeOptions, setMeetingRoomOptions] = useState<AvailabilityMeetingRoom[]>([])

  const venueOptions = venues.length ? venues : venueList

  const venueId = Form.useWatch('venue_id', form)
  const dateRange = Form.useWatch('date_range', form)
  const rooms = Form.useWatch('rooms', form)
  const selectedMeetingRoomId = Form.useWatch('meeting_room_id', form)

  const checkInText = dateRange?.[0]?.format(DAY_FORMAT) ?? ''
  const checkOutText = dateRange?.[1]?.format(DAY_FORMAT) ?? ''

  const selectedMeetingRoom = roomTypeOptions.find((item) => item.id === selectedMeetingRoomId) || null
  const hours = dateRange?.[0] && dateRange?.[1] ? Math.max(0, dateRange[1].diff(dateRange[0], 'day')) : 0
  const currentRooms = rooms || 1
  const totalAmount = (selectedMeetingRoom?.price || 0) * hours * currentRooms
  const maxRooms = Math.max(1, Math.min(20, selectedMeetingRoom?.remaining || 20))
  const maxGuests = Math.max(1, (selectedMeetingRoom?.capacity || 2) * currentRooms)

  const loadAvailability = useCallback(
    async (targetVenueId: number, checkIn: string, checkOut: string) => {
      setAvailabilityLoading(true)
      try {
        const data = await venueApi.availability(targetVenueId, checkIn, checkOut)
        setAvailability(data)
        setMeetingRoomOptions(data.meeting_rooms)
      } catch {
        setAvailability(null)
        setMeetingRoomOptions([])
      } finally {
        setAvailabilityLoading(false)
      }
    },
    [],
  )

  // 打开弹窗时重置表单，并准备好会议空间下拉选项
  useEffect(() => {
    if (!open) return
    let cancelled = false

    const init = async () => {
      let options = venues
      if (!options.length) {
        try {
          const data = await venueApi.list({ page_size: 100 })
          if (cancelled) return
          setVenueList(data.items)
          options = data.items
        } catch {
          // 请求层已经提示过错误
        }
      }
      if (cancelled) return

      const checkIn = dayjs().add(1, 'day')
      form.setFieldsValue({
        venue_id: venue?.id ?? options[0]?.id,
        date_range: [checkIn, checkIn.add(1, 'day')],
        meeting_room_id: undefined as unknown as number,
        rooms: 1,
        attendees: 1,
        equipment_request: '',
      })
      form.setFields([{ name: 'meeting_room_id', errors: [] }])
      setAvailability(null)
      setMeetingRoomOptions([])
    }

    void init()
    return () => {
      cancelled = true
    }
    // 只在弹窗打开时初始化，venues / venue 变化不需要重跑
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  // 会议空间或日期变化时刷新会议室状态
  useEffect(() => {
    if (!open || !venueId || !checkInText || !checkOutText) return
    if (checkOutText <= checkInText) return
    void loadAvailability(venueId, checkInText, checkOutText)
  }, [open, venueId, checkInText, checkOutText, loadAvailability])

  const handleMeetingRoomChange = (value: number) => {
    const target = roomTypeOptions.find((item) => item.id === value)
    if (!target) return
    const limit = Math.max(1, Math.min(20, target.remaining || 20))
    if ((form.getFieldValue('rooms') || 1) > limit) form.setFieldValue('rooms', limit)
    const guestLimit = Math.max(1, target.capacity * (form.getFieldValue('rooms') || 1))
    if ((form.getFieldValue('attendees') || 1) > guestLimit) form.setFieldValue('attendees', guestLimit)
  }

  const handleRoomsChange = (value: number | null) => {
    const nextRooms = value || 1
    const guestLimit = Math.max(1, (selectedMeetingRoom?.capacity || 2) * nextRooms)
    if ((form.getFieldValue('attendees') || 1) > guestLimit) form.setFieldValue('attendees', guestLimit)
  }

  const submit = async () => {
    const values = await form.validateFields().catch(() => null)
    if (!values) return

    const [checkIn, checkOut] = values.date_range
    const stayNights = checkOut.diff(checkIn, 'day')
    if (stayNights <= 0) {
      feedback.warning('使用结束日期必须晚于使用开始日期')
      return
    }
    const guestLimit = Math.max(1, (selectedMeetingRoom?.capacity || 2) * values.rooms)
    if (values.attendees > guestLimit) {
      feedback.warning('使用开始人数超过会议室类型可住人数上限，请增加房间数')
      return
    }

    setSubmitting(true)
    try {
      await reservationApi.create({
        venue_id: values.venue_id,
        meeting_room_id: values.meeting_room_id,
        start_at: checkIn.format(DAY_FORMAT),
        end_at: checkOut.format(DAY_FORMAT),
        rooms: values.rooms,
        attendees: values.attendees,
        equipment_request: values.equipment_request || '',
      })
      feedback.success('预约已提交，等待会议空间确认')
      onSuccess?.()
      onClose()
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      title="预约会议空间"
      open={open}
      width={660}
      okText="提交预约"
      cancelText="取消"
      confirmLoading={submitting}
      onOk={submit}
      onCancel={onClose}
    >
      <Form form={form} labelCol={{ span: 5 }} wrapperCol={{ span: 19 }} style={{ marginTop: 20 }}>
        <Form.Item label="会议空间" name="venue_id" rules={[{ required: true, message: '请选择会议空间' }]}>
          <Select
            placeholder="请选择会议空间"
            disabled={Boolean(venue)}
            onChange={() => form.setFieldValue('meeting_room_id', undefined as unknown as number)}
            options={venueOptions.map((item) => ({
              value: item.id,
              label: `${item.name}（${item.city} ${item.address}）`,
              disabled: item.status !== 1,
            }))}
          />
        </Form.Item>

        <Form.Item
          label="使用开始 / 使用结束"
          name="date_range"
          rules={[{ required: true, message: '请选择使用开始与使用结束日期' }]}
        >
          <DatePicker.RangePicker
            style={{ width: '100%' }}
            format={DAY_FORMAT}
            disabledDate={disabledDate}
            onChange={() => form.setFieldValue('meeting_room_id', undefined as unknown as number)}
          />
        </Form.Item>

        <Form.Item label="会议室类型" name="meeting_room_id" rules={[{ required: true, message: '请选择会议室类型' }]}>
          <Select
            placeholder="请先选择会议空间与日期"
            loading={availabilityLoading}
            onChange={handleMeetingRoomChange}
            options={roomTypeOptions.map((item) => ({
              value: item.id,
              label: roomTypeLabel(item),
              disabled: !item.bookable,
            }))}
          />
        </Form.Item>

        {/* 带 name 的 Form.Item 只能有一个子元素，提示文案用 extra 承载 */}
        <Form.Item
          label="间数"
          name="rooms"
          rules={[{ required: true, message: '请输入间数' }]}
          extra={`该会议室类型剩余 ${selectedMeetingRoom?.remaining ?? '-'} 间`}
        >
          <InputNumber min={1} max={maxRooms} onChange={handleRoomsChange} />
        </Form.Item>

        <Form.Item
          label="使用开始人数"
          name="attendees"
          rules={[{ required: true, message: '请输入使用开始人数' }]}
          extra={selectedMeetingRoom ? `每间可住 ${selectedMeetingRoom.capacity} 人` : '请选择会议室类型'}
        >
          <InputNumber min={1} max={maxGuests} />
        </Form.Item>

        <Form.Item label="特殊要求">
          <Form.Item name="equipment_request" noStyle>
            <Input.TextArea
              rows={2}
              maxLength={200}
              showCount
              placeholder="例如：安静楼层、需要加床、晚到店"
            />
          </Form.Item>
        </Form.Item>

        <Form.Item label="费用预估">
          {hours > 0 && selectedMeetingRoom ? (
            <div style={{ color: token.colorText }}>
              共 <b>{hours}</b> 晚 · <b>{currentRooms}</b> 间 · 总价{' '}
              <b style={{ color: token.colorError, fontSize: 16 }}>{money(totalAmount)}</b>
              <div style={{ marginTop: 4, color: token.colorTextTertiary, fontSize: 12 }}>
                使用开始 {availability?.open_time || '-'} 之后，使用结束 {availability?.close_time || '-'}{' '}
                之前，房价未含到店可能产生的押金与加床费用
              </div>
            </div>
          ) : (
            <span style={{ color: token.colorTextTertiary }}>请选择会议空间、日期与会议室类型</span>
          )}
        </Form.Item>

        <Form.Item label="会议室状态">
          {roomTypeOptions.length ? (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {roomTypeOptions.map((item) => (
                <Tag key={item.id} color={item.bookable ? 'success' : 'default'}>
                  {item.name}：{item.status_text}，剩余 {item.remaining} 间
                </Tag>
              ))}
            </div>
          ) : (
            <span style={{ color: token.colorTextTertiary }}>选择日期后显示会议室类型与剩余会议室余量</span>
          )}
        </Form.Item>
      </Form>
    </Modal>
  )
}
