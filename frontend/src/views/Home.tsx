import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Card, Col, Row, Table, Tag, theme, type TableColumnsType } from 'antd'
import {
  ApartmentOutlined,
  CalendarOutlined,
  ClockCircleOutlined,
  TeamOutlined,
} from '@ant-design/icons'

import { statsApi } from '@/api'
import type { Reservation, StatOverview } from '@/api/types'
import { RESERVATION_STATUS_COLOR, useUserStore } from '@/store/user'
import { money, reservationRange } from '@/utils/format'

const EMPTY_OVERVIEW: StatOverview = {
  venue_total: 0,
  meeting_room_total: 0,
  user_total: 0,
  reservation_total: 0,
  pending_total: 0,
  today_reservation_total: 0,
  utilization_rate: 0,
  week_total: 0,
  week_start: '',
  week_end: '',
  venue_ranking: [],
  recent_reservations: [],
}

function greeting(): string {
  const hour = new Date().getHours()
  if (hour < 6) return '凌晨好'
  if (hour < 12) return '上午好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
}

export default function Home() {
  const navigate = useNavigate()
  const user = useUserStore((state) => state.user)
  const isAdmin = user?.role === 'admin'
  const displayName = user?.name || user?.username || '用户'
  const { token } = theme.useToken()

  const tones = {
    blue: { color: token.colorPrimary, soft: token.colorPrimaryBg },
    green: { color: token.colorSuccess, soft: token.colorSuccessBg },
    gold: { color: token.colorWarning, soft: token.colorWarningBg },
    red: { color: token.colorError, soft: token.colorErrorBg },
  }

  const rankColor = (index: number) =>
    index === 0 ? token.colorWarning : index === 1 ? token.colorPrimary : token.colorTextTertiary

  const [loading, setLoading] = useState(false)
  const [overview, setOverview] = useState<StatOverview>(EMPTY_OVERVIEW)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setOverview(await statsApi.overview())
    } catch {
      // 请求层已经提示过错误
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const weekText = (() => {
    const { week_start: start, week_end: end } = overview
    if (!start || !end) return ''
    const short = (value: string) => String(value).slice(5).replace('-', '/')
    return `${short(start)} ~ ${short(end)}`
  })()

  const cards = isAdmin
    ? [
        { label: '会议空间', value: overview.venue_total, icon: <ApartmentOutlined />, tone: tones.blue, tip: '可管理的会议空间' },
        { label: '会议室规格', value: overview.meeting_room_total, icon: <ClockCircleOutlined />, tone: tones.green, tip: '可预约会议室类型' },
        { label: '会员数', value: overview.user_total, icon: <TeamOutlined />, tone: tones.gold, tip: '注册会员总数' },
        { label: '待确认预约', value: overview.pending_total, icon: <CalendarOutlined />, tone: tones.red, tip: '等待审核的预约' },
      ]
    : [
        { label: '会议空间', value: overview.venue_total, icon: <ApartmentOutlined />, tone: tones.blue, tip: '可预约会议空间' },
        { label: '会议室规格', value: overview.meeting_room_total, icon: <ClockCircleOutlined />, tone: tones.green, tip: '可预约会议室类型' },
        { label: '我的预约', value: overview.reservation_total, icon: <CalendarOutlined />, tone: tones.gold, tip: '累计预约数' },
        { label: '今日预约', value: overview.today_reservation_total, icon: <CalendarOutlined />, tone: tones.red, tip: '今天使用的会议室' },
      ]

  const columns: TableColumnsType<Reservation> = [
    {
      title: '空间 / 会议室',
      dataIndex: 'venue_name',
      width: 200,
      ellipsis: true,
      render: (_, row) => (
        <div>
          <div>{row.venue_name}</div>
          <div style={{ color: token.colorTextTertiary, fontSize: 12 }}>
            {row.meeting_room_name}
          </div>
        </div>
      ),
    },
    ...(isAdmin ? [{ title: '会员', dataIndex: 'user_name' as const, width: 90 }] : []),
    { title: '预约时段', width: 235, render: (_, row) => reservationRange(row) },
    { title: '总价', width: 90, render: (_, row) => money(row.total_amount) },
    {
      title: '状态',
      width: 100,
      render: (_, row) => (
        <Tag color={RESERVATION_STATUS_COLOR[row.status]}>{row.status_text}</Tag>
      ),
    },
  ]

  return (
    <div>
      <Card variant="borderless" style={{ marginBottom: 16 }} loading={loading}>
        <div className="page-block-head">
          <div>
            <div style={{ fontSize: 18, fontWeight: 600 }}>
              {greeting()}，{displayName}
            </div>
            <div style={{ marginTop: 6, color: token.colorTextSecondary }}>
              {isAdmin
                ? '这里可以查看空间使用情况、审核预约并维护会议室资源。'
                : '您可以查找会议空间、预约会议室，也可以直接问智能助手。'}
            </div>
          </div>
          <div className="page-toolbar">
            <Button
              type="primary"
              icon={<ApartmentOutlined />}
              onClick={() => navigate('/manager/venue')}
            >
              预约会议室
            </Button>
            <Button onClick={() => navigate('/manager/reservation')}>我的预约</Button>
            {isAdmin && (
              <Button onClick={() => navigate('/manager/reservation-review')}>
                预约审核
              </Button>
            )}
          </div>
        </div>
      </Card>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        {cards.map((card) => (
          <Col key={card.label} xs={12} sm={12} md={6}>
            <Card variant="borderless" style={{ marginBottom: 16 }} loading={loading}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                <span
                  style={{
                    flex: 'none',
                    width: 46,
                    height: 46,
                    borderRadius: 12,
                    display: 'grid',
                    placeItems: 'center',
                    fontSize: 22,
                    color: card.tone.color,
                    background: card.tone.soft,
                  }}
                >
                  {card.icon}
                </span>
                <div style={{ minWidth: 0 }}>
                  <div style={{ color: token.colorTextTertiary, fontSize: 13 }}>{card.label}</div>
                  <div style={{ fontSize: 26, fontWeight: 600, lineHeight: 1.2 }}>{card.value}</div>
                </div>
              </div>
              <div style={{ marginTop: 12, color: token.colorTextTertiary, fontSize: 12 }}>
                {card.tip}
              </div>
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={16}>
        <Col xs={24} md={10}>
          <Card
            variant="borderless"
            loading={loading}
            style={{ marginBottom: 16 }}
            title="空间预约排行"
            extra={
              <span style={{ fontSize: 12, color: token.colorTextTertiary }}>
                本周 {weekText}
              </span>
            }
          >
            {overview.venue_ranking.length === 0 && (
              <div style={{ color: token.colorTextTertiary }}>暂无数据</div>
            )}
            {overview.venue_ranking.map((item, index) => (
              <div
                key={item.venue_id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '9px 0',
                  borderBottom: `1px solid ${token.colorSplit}`,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ color: rankColor(index), fontWeight: 600, width: 16 }}>
                    {index + 1}
                  </span>
                  <span>{item.venue_name}</span>
                </div>
                <span style={{ color: token.colorTextSecondary }}>
                  {item.reservation_count} 次
                </span>
              </div>
            ))}
            <div style={{ marginTop: 12, color: token.colorTextTertiary, fontSize: 12 }}>
              今日会议室使用率{' '}
              <b style={{ color: token.colorPrimary }}>{overview.utilization_rate}%</b>
              ，排行按本周有效预约数统计，已取消 / 已拒绝不计入。
            </div>
          </Card>
        </Col>

        <Col xs={24} md={14}>
          <Card variant="borderless" title="最近预约" loading={loading}>
            <Table<Reservation>
              rowKey="id"
              size="small"
              loading={loading}
              columns={columns}
              dataSource={overview.recent_reservations}
              pagination={false}
              locale={{ emptyText: '暂无预约记录' }}
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
