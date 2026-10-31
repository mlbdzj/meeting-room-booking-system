import { useCallback, useEffect, useState } from 'react'
import { DatePicker, Form, Input, InputNumber, Modal, Select, Tag, theme } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'

import { reservationApi, venueApi } from '@/api'
import type { Availability, AvailabilityMeetingRoom, Venue } from '@/api/types'
import { feedback } from '@/utils/feedback'
import { money, toDateTimeString } from '@/utils/format'

const DATETIME_FORMAT = 'YYYY-MM-DD HH:mm'
const API_DATETIME_FORMAT = 'YYYY-MM-DDTHH:mm:ss'

export interface ReservationDialogProps {
  open: boolean
  /** 指定空间时锁定空间选择（从空间页「预约」按钮进入） */
  venue?: Venue | null
  venues?: Venue[]
  onClose: () => void
  onSuccess?: () => void
}

interface ReservationFormValues {
  venue_id: number
  start_at: Dayjs
  end_at: Dayjs
  meeting_room_id: number
  rooms: number
  attendees: number
  equipment_request?: string
}

const meetingRoomLabel = (item: AvailabilityMeetingRoom) =>
  `${item.name}（${item.layout}）${money(item.hourly_price)}/小时 · ${item.capacity} 人 · 剩余 ${item.remaining} 间`

export default function ReservationDialog({
  open,
  venue,
  venues = [],
  onClose,
  onSuccess,
}: ReservationDialogProps) {
  const [form] = Form.useForm<ReservationFormValues>()
  const { token } = theme.useToken()
  const [submitting, setSubmitting] = useState(false)
  const [availabilityLoading, setAvailabilityLoading] = useState(false)
  const [venueList, setVenueList] = useState<Venue[]>([])
  const [availability, setAvailability] = useState<Availability | null>(null)
  const [meetingRoomOptions, setMeetingRoomOptions] = useState<AvailabilityMeetingRoom[]>([])

  const venueOptions = venues.length ? venues : venueList
  const venueId = Form.useWatch('venue_id', form)
  const startAt = Form.useWatch('start_at', form)
  const endAt = Form.useWatch('end_at', form)
  const rooms = Form.useWatch('rooms', form)
  const selectedMeetingRoomId = Form.useWatch('meeting_room_id', form)

  const selectedMeetingRoom =
    meetingRoomOptions.find((item) => item.id === selectedMeetingRoomId) || null
  const hours = startAt && endAt ? Math.max(0, endAt.diff(startAt, 'minute') / 60) : 0
  const currentRooms = rooms || 1
  const totalAmount = (selectedMeetingRoom?.hourly_price || 0) * hours * currentRooms
  const maxRooms = Math.max(1, Math.min(20, selectedMeetingRoom?.remaining || 20))
  const maxAttendees = Math.max(
    1,
    (selectedMeetingRoom?.capacity || 1) * currentRooms,
  )

  const loadAvailability = useCallback(
    async (targetVenueId: number, start: string, end: string) => {
      setAvailabilityLoading(true)
      try {
        const data = await venueApi.availability(targetVenueId, start, end)
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
          // 请求层已经提示错误
        }
      }
      if (cancelled) return

      const tomorrow = dayjs().add(1, 'day').hour(10).minute(0).second(0)
      form.setFieldsValue({
        venue_id: venue?.id ?? options[0]?.id,
        start_at: tomorrow,
        end_at: tomorrow.add(2, 'hour'),
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
    // 只在弹窗打开时初始化
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  useEffect(() => {
    if (!open || !venueId || !startAt || !endAt || endAt.isBefore(startAt)) return
    void loadAvailability(
      venueId,
      startAt.format(API_DATETIME_FORMAT),
      endAt.format(API_DATETIME_FORMAT),
    )
  }, [open, venueId, startAt, endAt, loadAvailability])

  const handleMeetingRoomChange = (value: number) => {
    const target = meetingRoomOptions.find((item) => item.id === value)
    if (!target) return
    const limit = Math.max(1, Math.min(20, target.remaining || 20))
    if ((form.getFieldValue('rooms') || 1) > limit) form.setFieldValue('rooms', limit)
    const attendeeLimit = Math.max(
      1,
      target.capacity * (form.getFieldValue('rooms') || 1),
    )
    if ((form.getFieldValue('attendees') || 1) > attendeeLimit) {
      form.setFieldValue('attendees', attendeeLimit)
    }
  }

  const handleRoomsChange = (value: number | null) => {
    const nextRooms = value || 1
    const attendeeLimit = Math.max(
      1,
      (selectedMeetingRoom?.capacity || 1) * nextRooms,
    )
    if ((form.getFieldValue('attendees') || 1) > attendeeLimit) {
      form.setFieldValue('attendees', attendeeLimit)
    }
  }

  const submit = async () => {
    const values = await form.validateFields().catch(() => null)
    if (!values) return
    if (!values.end_at.isAfter(values.start_at)) {
      feedback.warning('结束时间必须晚于开始时间')
      return
    }
    const attendeeLimit = Math.max(
      1,
      (selectedMeetingRoom?.capacity || 1) * values.rooms,
    )
    if (values.attendees > attendeeLimit) {
      feedback.warning('参会人数超过会议室容量，请增加会议室数量')
      return
    }

    setSubmitting(true)
    try {
      await reservationApi.create({
        venue_id: values.venue_id,
        meeting_room_id: values.meeting_room_id,
        start_at: values.start_at.format(API_DATETIME_FORMAT),
        end_at: values.end_at.format(API_DATETIME_FORMAT),
        rooms: values.rooms,
        attendees: values.attendees,
        equipment_request: values.equipment_request || '',
      })
      feedback.success('预约已提交，等待空间管理员确认')
      onSuccess?.()
      onClose()
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      title="预约会议室"
      open={open}
      width={700}
      okText="提交预约"
      cancelText="取消"
      confirmLoading={submitting}
      onOk={submit}
      onCancel={onClose}
    >
      <Form
        form={form}
        labelCol={{ span: 5 }}
        wrapperCol={{ span: 19 }}
        style={{ marginTop: 20 }}
      >
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
          label="开始时间"
          name="start_at"
          rules={[{ required: true, message: '请选择开始时间' }]}
        >
          <DatePicker
            showTime={{ format: 'HH:mm' }}
            format={DATETIME_FORMAT}
            style={{ width: '100%' }}
            disabledDate={(current) => current.isBefore(dayjs(), 'day')}
            onChange={() => form.setFieldValue('meeting_room_id', undefined as unknown as number)}
          />
        </Form.Item>

        <Form.Item
          label="结束时间"
          name="end_at"
          rules={[{ required: true, message: '请选择结束时间' }]}
        >
          <DatePicker
            showTime={{ format: 'HH:mm' }}
            format={DATETIME_FORMAT}
            style={{ width: '100%' }}
            disabledDate={(current) => current.isBefore(dayjs(), 'day')}
            onChange={() => form.setFieldValue('meeting_room_id', undefined as unknown as number)}
          />
        </Form.Item>

        <Form.Item
          label="会议室"
          name="meeting_room_id"
          rules={[{ required: true, message: '请选择会议室' }]}
        >
          <Select
            placeholder="请先选择会议空间与时间"
            loading={availabilityLoading}
            onChange={handleMeetingRoomChange}
            options={meetingRoomOptions.map((item) => ({
              value: item.id,
              label: meetingRoomLabel(item),
              disabled: !item.available,
            }))}
          />
        </Form.Item>

        <Form.Item
          label="间数"
          name="rooms"
          rules={[{ required: true, message: '请输入间数' }]}
          extra={`该规格剩余 ${selectedMeetingRoom?.remaining ?? '-'} 间`}
        >
          <InputNumber min={1} max={maxRooms} onChange={handleRoomsChange} />
        </Form.Item>

        <Form.Item
          label="参会人数"
          name="attendees"
          rules={[{ required: true, message: '请输入参会人数' }]}
          extra={selectedMeetingRoom ? `每间可容纳 ${selectedMeetingRoom.capacity} 人` : '请选择会议室'}
        >
          <InputNumber min={1} max={maxAttendees} />
        </Form.Item>

        <Form.Item label="设备需求">
          <Form.Item name="equipment_request" noStyle>
            <Input.TextArea
              rows={2}
              maxLength={200}
              showCount
              placeholder="例如：需要视频会议、额外白板、茶歇或提前布置"
            />
          </Form.Item>
        </Form.Item>

        <Form.Item label="费用预估">
          {hours > 0 && selectedMeetingRoom ? (
            <div style={{ color: token.colorText }}>
              共 <b>{hours}</b> 小时 · <b>{currentRooms}</b> 间 · 总价{' '}
              <b style={{ color: token.colorError, fontSize: 16 }}>{money(totalAmount)}</b>
              <div style={{ marginTop: 4, color: token.colorTextTertiary, fontSize: 12 }}>
                开放时段 {availability?.open_time || '-'} - {availability?.close_time || '-'}，
                提交后仍需管理员确认
              </div>
            </div>
          ) : (
            <span style={{ color: token.colorTextTertiary }}>请选择有效时间段与会议室</span>
          )}
        </Form.Item>

        <Form.Item label="会议室余量">
          {meetingRoomOptions.length ? (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {meetingRoomOptions.map((item) => (
                <Tag key={item.id} color={item.available ? 'success' : 'default'}>
                  {item.name}：{item.status_text}，剩余 {item.remaining} 间
                </Tag>
              ))}
            </div>
          ) : (
            <span style={{ color: token.colorTextTertiary }}>
              {startAt ? `${toDateTimeString(startAt.toISOString())} 后显示余量` : '选择时间后显示余量'}
            </span>
          )}
        </Form.Item>
      </Form>
    </Modal>
  )
}
