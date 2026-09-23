import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Avatar, Button, Drawer, Dropdown, FloatButton, Input, Tag, type MenuProps } from 'antd'
import {
  ClockCircleOutlined,
  CloseOutlined,
  CustomerServiceOutlined,
  PlusOutlined,
  SendOutlined,
} from '@ant-design/icons'

import { agentApi } from '@/api'
import { ApiError } from '@/api/request'
import type { AgentStatus, ChatAction, ChatMessage, ChatReply, ChatSession, FaqItem } from '@/api/types'
import { useUserStore } from '@/store/user'
import { feedback } from '@/utils/feedback'

/** 界面上的消息：本地发送的用户消息还没有服务端 id，用 key 区分 */
interface ChatItem {
  key: string
  role: 'user' | 'assistant'
  content: string
  source: string
  action: ChatAction | null
  messageId?: number
}

const EMPTY_STATUS: AgentStatus = {
  provider: 'local',
  model: '',
  llm_enabled: false,
  knowledge_total: 0,
  tools: [],
}

function toChatItem(message: ChatMessage): ChatItem {
  return {
    key: String(message.id),
    role: message.role === 'user' ? 'user' : 'assistant',
    content: message.content,
    source: message.source || '',
    action: message.action ?? null,
    messageId: message.id,
  }
}

function sourceText(source: string): string {
  if (source === 'llm') return '由大模型结合系统数据生成'
  if (source === 'local-fallback') return '大模型暂不可用，回答来自本地知识库'
  if (source === 'system') return '系统操作结果'
  return '回答来自本地知识库'
}

function actionStatusText(status?: string): string {
  if (status === 'pending') return '待确认'
  if (status === 'confirmed') return '已下单'
  if (status === 'canceled') return '已取消'
  if (status === 'failed') return '下单失败'
  return '信息不完整'
}

function actionTagColor(status?: string): string {
  if (status === 'pending') return 'warning'
  if (status === 'confirmed') return 'success'
  if (status === 'failed') return 'error'
  return 'default'
}

/** 只支持 **加粗** 与换行的轻量渲染，避免直接使用 dangerouslySetInnerHTML */
function RichText({ text }: { text: string }) {
  const lines = String(text ?? '').split('\n')
  return (
    <>
      {lines.map((line, lineIndex) => (
        <Fragment key={lineIndex}>
          {lineIndex > 0 && <br />}
          {line.split(/\*\*(.+?)\*\*/g).map((part, partIndex) =>
            partIndex % 2 === 1 ? <strong key={partIndex}>{part}</strong> : <Fragment key={partIndex}>{part}</Fragment>,
          )}
        </Fragment>
      ))}
    </>
  )
}

interface ActionCardProps {
  action: ChatAction
  loading: boolean
  onConfirm: () => void
  onCancel: () => void
}

function ActionCard({ action, loading, onConfirm, onCancel }: ActionCardProps) {
  const payload = action.payload ?? {}
  const problems = action.problems ?? []

  return (
    <div className="agent-action">
      <div className="agent-action-head">
        <span>预约确认卡</span>
        <Tag color={actionTagColor(action.status)}>{actionStatusText(action.status)}</Tag>
      </div>

      <div className="agent-action-row">
        <span className="agent-action-label">会议空间</span>
        <span>{payload.venue_name || '待确认'}</span>
      </div>
      <div className="agent-action-row">
        <span className="agent-action-label">会议室类型</span>
        <span>{payload.meeting_room_name || '待确认'}</span>
      </div>
      <div className="agent-action-row">
        <span className="agent-action-label">使用开始</span>
        <span>{payload.start_at || '待确认'}</span>
      </div>
      <div className="agent-action-row">
        <span className="agent-action-label">使用结束</span>
        <span>
          {payload.end_at || '待确认'}
          {payload.hours ? `（${payload.hours} 晚）` : ''}
        </span>
      </div>
      <div className="agent-action-row">
        <span className="agent-action-label">房间</span>
        <span>
          {payload.rooms ? `${payload.rooms} 间` : '待确认'} / {payload.attendees ? `${payload.attendees} 人` : '待确认'}
        </span>
      </div>
      <div className="agent-action-row">
        <span className="agent-action-label">总价</span>
        <span>{payload.total_amount ? `¥${payload.total_amount}` : '待确认'}</span>
      </div>
      <div className="agent-action-row">
        <span className="agent-action-label">特殊要求</span>
        <span>{payload.equipment_request || '无'}</span>
      </div>

      {problems.length > 0 && (
        <div className="agent-action-problems">
          {problems.map((problem, index) => (
            <div key={index}>· {problem}</div>
          ))}
        </div>
      )}
      {action.error && <div className="agent-action-problems">· {action.error}</div>}
      {action.note && problems.length === 0 && <div className="agent-action-note">{action.note}</div>}

      {action.status === 'pending' && problems.length === 0 ? (
        <div className="agent-action-buttons">
          <Button type="primary" size="small" loading={loading} onClick={onConfirm}>
            确认下单
          </Button>
          <Button size="small" disabled={loading} onClick={onCancel}>
            不用了
          </Button>
        </div>
      ) : action.reservation_id ? (
        <div className="agent-action-note">
          已生成预约 #{action.reservation_id}，可在「我的预约」中查看。
        </div>
      ) : problems.length > 0 ? (
        <div className="agent-action-note">请补充或修改上述信息后重新告诉我要怎么订。</div>
      ) : null}
    </div>
  )
}

export default function AgentChat() {
  const displayName = useUserStore((state) => (state.user?.name || state.user?.username || '我').slice(0, 1))

  const [visible, setVisible] = useState(false)
  const [loading, setLoading] = useState(false)
  const [input, setInput] = useState('')
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [items, setItems] = useState<ChatItem[]>([])
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [faq, setFaq] = useState<FaqItem[]>([])
  const [status, setStatus] = useState<AgentStatus>(EMPTY_STATUS)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [narrow, setNarrow] = useState(() => typeof window !== 'undefined' && window.innerWidth < 520)

  const listRef = useRef<HTMLDivElement>(null)
  const localKeyRef = useRef(0)

  const scrollToBottom = useCallback(() => {
    const element = listRef.current
    if (element) element.scrollTop = element.scrollHeight
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [items, loading, scrollToBottom])

  useEffect(() => {
    const onResize = () => setNarrow(window.innerWidth < 520)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  useEffect(() => {
    agentApi
      .status()
      .then(setStatus)
      .catch(() => {
        // 未登录或接口异常时保持默认状态
      })
  }, [])

  const loadSessions = useCallback(async () => {
    try {
      setSessions(await agentApi.sessions())
    } catch {
      setSessions([])
    }
  }, [])

  const open = useCallback(async () => {
    setVisible(true)
    try {
      const [statusData, faqData] = await Promise.all([
        agentApi.status(),
        faq.length ? Promise.resolve(faq) : agentApi.faq(),
      ])
      setStatus(statusData)
      setFaq(faqData)
    } catch {
      // 状态获取失败不影响对话
    }
    void loadSessions()
    scrollToBottom()
  }, [faq, loadSessions, scrollToBottom])

  const newSession = useCallback(() => {
    setSessionId(null)
    setItems([])
    setSuggestions([])
    setInput('')
  }, [])

  const loadSession = useCallback(
    async (id: number) => {
      try {
        const messages = await agentApi.messages(id)
        setSessionId(id)
        setItems(messages.map(toChatItem))
        setSuggestions([])
        scrollToBottom()
      } catch {
        // 请求层已经提示过错误
      }
    },
    [scrollToBottom],
  )

  const send = useCallback(
    async (text?: string) => {
      const question = (text ?? input).trim()
      if (!question || loading) return

      localKeyRef.current += 1
      setItems((prev) => [
        ...prev,
        { key: `local-${localKeyRef.current}`, role: 'user', content: question, source: '', action: null },
      ])
      setInput('')
      setSuggestions([])
      setLoading(true)

      const appendReply = (reply: ChatReply) => {
        setSessionId(reply.session_id)
        setItems((prev) => [...prev, toChatItem(reply.reply)])
        setSuggestions(reply.suggestions || [])
      }

      try {
        let data: ChatReply
        try {
          data = await agentApi.chat({ message: question, session_id: sessionId })
        } catch (error) {
          // 会话已被删除（例如在其它设备上清理过），自动开启新会话重试一次
          if (error instanceof ApiError && error.status === 404 && sessionId) {
            setSessionId(null)
            data = await agentApi.chat({ message: question })
          } else {
            throw error
          }
        }
        appendReply(data)
        void loadSessions()
      } catch (error) {
        setItems((prev) => [
          ...prev,
          {
            key: `error-${Date.now()}`,
            role: 'assistant',
            content: `抱歉，回答失败：${(error as Error).message || '服务暂时不可用'}。请稍后再试，或联系空间管理员。`,
            source: '',
            action: null,
          },
        ])
      } finally {
        setLoading(false)
      }
    },
    [input, loadSessions, loading, sessionId],
  )

  const confirmAction = useCallback(
    async (item: ChatItem) => {
      if (!sessionId || !item.messageId) return
      setActionLoading(item.key)
      try {
        const data = await agentApi.confirmAction({ session_id: sessionId, message_id: item.messageId })
        setItems((prev) =>
          prev.map((current) => (current.key === item.key ? { ...current, action: data.action } : current)),
        )
        setItems((prev) => [...prev, toChatItem(data.message)])
        setSuggestions([])
        feedback.success('预约已提交，等待管理员确认')
        void loadSessions()
      } catch (error) {
        feedback.error((error as Error).message || '确认失败')
        await loadSession(sessionId)
      } finally {
        setActionLoading(null)
      }
    },
    [loadSession, loadSessions, sessionId],
  )

  const cancelAction = useCallback(
    async (item: ChatItem) => {
      if (!sessionId || !item.messageId) return
      setActionLoading(item.key)
      try {
        const data = await agentApi.cancelAction({ session_id: sessionId, message_id: item.messageId })
        setItems((prev) =>
          prev.map((current) => (current.key === item.key ? { ...current, action: data.action } : current)),
        )
        setItems((prev) => [...prev, toChatItem(data.message)])
      } catch (error) {
        feedback.error((error as Error).message || '取消失败')
      } finally {
        setActionLoading(null)
      }
    },
    [sessionId],
  )

  const historyItems = useMemo<MenuProps['items']>(() => {
    if (!sessions.length) return [{ key: 'empty', label: '暂无历史对话', disabled: true }]
    return sessions.map((item) => ({
      key: `load:${item.id}`,
      label: item.title,
      style: item.id === sessionId ? { color: '#409eff', fontWeight: 'bold' } : undefined,
    }))
  }, [sessionId, sessions])

  const handleHistoryClick = useCallback<NonNullable<MenuProps['onClick']>>(
    ({ key }) => {
      if (typeof key === 'string' && key.startsWith('load:')) void loadSession(Number(key.slice(5)))
    },
    [loadSession],
  )

  return (
    <>
      <FloatButton
        type="primary"
        icon={<CustomerServiceOutlined />}
        tooltip="有问题？问问客服助手"
        style={{ right: 28, bottom: 32, width: 52, height: 52 }}
        onClick={open}
      />

      <Drawer
        open={visible}
        onClose={() => setVisible(false)}
        placement="right"
        width={narrow ? '100%' : 440}
        closable={false}
        rootClassName="agent-drawer"
      >
        <div className="agent-header">
          <div>
            <div className="agent-title">
              <CustomerServiceOutlined />
              <span>客服助手</span>
            </div>
            <div className="agent-subtitle">
              <Tag color={status.llm_enabled ? 'success' : 'default'}>
                {status.llm_enabled ? '大模型模式' : '本地知识库模式'}
              </Tag>
              {status.llm_enabled && <span className="agent-model">{status.model}</span>}
              <span className="agent-model">知识库 {status.knowledge_total} 条</span>
            </div>
          </div>
          <div>
            <Dropdown menu={{ items: historyItems, onClick: handleHistoryClick }} trigger={['click']}>
              <Button type="text" icon={<ClockCircleOutlined />}>
                历史
              </Button>
            </Dropdown>
            <Button type="text" icon={<PlusOutlined />} onClick={newSession}>
              新对话
            </Button>
            <Button type="text" icon={<CloseOutlined />} onClick={() => setVisible(false)} />
          </div>
        </div>

        <div className="agent-body" ref={listRef}>
          {!items.length && (
            <div className="agent-welcome">
              <div className="agent-welcome-title">你好，我是会议室预约系统助手</div>
              <div className="agent-welcome-desc">
                可以问我预约流程、会议空间空闲情况、预约状态、会议室类型使用等问题。
              </div>
              <div className="agent-chips">
                {faq.map((item) => (
                  <Tag key={item.question} className="agent-chip" onClick={() => void send(item.question)}>
                    {item.question}
                  </Tag>
                ))}
              </div>
            </div>
          )}

          {items.map((item) => (
            <div key={item.key} className={`agent-row ${item.role === 'user' ? 'agent-row-user' : 'agent-row-bot'}`}>
              <Avatar size={28} style={item.role === 'user' ? undefined : { background: '#409eff' }}>
                {item.role === 'user' ? displayName : 'A'}
              </Avatar>
              <div className="agent-bubble">
                <div className="agent-content">
                  <RichText text={item.content} />
                </div>
                {item.action && (
                  <ActionCard
                    action={item.action}
                    loading={actionLoading === item.key}
                    onConfirm={() => void confirmAction(item)}
                    onCancel={() => void cancelAction(item)}
                  />
                )}
                {item.role === 'assistant' && item.source && (
                  <div className="agent-source">{sourceText(item.source)}</div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="agent-row agent-row-bot">
              <Avatar size={28} style={{ background: '#409eff' }}>
                A
              </Avatar>
              <div className="agent-bubble agent-typing">
                <span />
                <span />
                <span />
              </div>
            </div>
          )}

          {suggestions.length > 0 && items.length > 0 && (
            <div className="agent-chips agent-chips-inline">
              {suggestions.map((item) => (
                <Tag key={item} className="agent-chip" onClick={() => void send(item)}>
                  {item}
                </Tag>
              ))}
            </div>
          )}
        </div>

        <div className="agent-footer">
          <Input.TextArea
            value={input}
            rows={2}
            maxLength={500}
            placeholder="输入你的问题，回车发送（Shift + 回车换行）"
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                void send()
              }
            }}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            loading={loading}
            style={{ marginTop: 8, width: '100%' }}
            onClick={() => void send()}
          >
            发送
          </Button>
        </div>
      </Drawer>
    </>
  )
}
