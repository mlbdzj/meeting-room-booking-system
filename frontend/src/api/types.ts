export type Role = 'admin' | 'user'

export type ReservationStatus = 'pending' | 'confirmed' | 'rejected' | 'canceled' | 'completed'

export type MeetingRoomStatus = 'open' | 'maintenance' | 'closed'

/** 后端统一的分页返回结构 */
export interface PageResult<T> {
  total: number
  items: T[]
}

export interface MessageResult {
  message: string
}

export interface UserInfo {
  id: number
  username: string
  name: string
  phone: string
  email: string
  role: Role
  status: number
  created_at?: string | null
}

export interface LoginResult {
  token: string
  user: UserInfo
}

export interface LoginPayload {
  username: string
  password: string
}

export interface RegisterPayload {
  username: string
  name: string
  phone: string
  email: string
  password: string
  confirm_password: string
}

export interface ProfilePayload {
  name: string
  phone: string
  email: string
}

export interface PasswordPayload {
  old_password?: string
  new_password: string
}

export interface UserPayload extends ProfilePayload {
  role: Role
  status: number
}

export interface UserCreatePayload extends UserPayload {
  username: string
  password: string
}

export interface Venue {
  id: number
  name: string
  city: string
  address: string
  star: number
  room_count: number
  open_time: string
  close_time: string
  status: number
  description: string
  created_at?: string | null
  meeting_room_count: number
  reservation_count: number
}

export interface VenuePayload {
  name: string
  city: string
  address: string
  star: number
  room_count: number
  open_time: string
  close_time: string
  status: number
  description: string
}

export interface MeetingRoom {
  id: number
  name: string
  code: string
  layout: string
  venue_id: number
  venue_name: string
  price: number
  capacity: number
  quantity: number
  status: MeetingRoomStatus
  description: string
  created_at?: string | null
}

export interface MeetingRoomPayload {
  name: string
  code: string
  layout: string
  venue_id: number
  price: number
  capacity: number
  quantity: number
  status: MeetingRoomStatus
  description: string
}

/** 会议室状态查询返回的单个会议室类型（带实时剩余会议室余量） */
export interface AvailabilityMeetingRoom {
  id: number
  name: string
  layout: string
  price: number
  capacity: number
  quantity: number
  remaining: number
  status: MeetingRoomStatus
  status_text: string
  bookable: boolean
}

export interface Availability {
  venue_id: number
  venue_name: string
  check_in: string
  check_out: string
  hours: number
  open_time: string
  close_time: string
  meeting_rooms: AvailabilityMeetingRoom[]
}

export interface Reservation {
  id: number
  venue_id: number
  venue_name: string
  meeting_room_id: number
  meeting_room_name: string
  user_id: number
  username: string
  user_name: string
  start_at: string
  end_at: string
  hours: number
  rooms: number
  attendees: number
  contact_phone: string
  total_amount: number
  equipment_request: string
  status: ReservationStatus
  status_text: string
  remark: string
  reviewer_name: string
  reviewed_at?: string | null
  created_at?: string | null
}

export interface ReservationPayload {
  venue_id: number
  meeting_room_id: number
  start_at: string
  end_at: string
  rooms: number
  attendees: number
  contact_phone?: string
  equipment_request?: string
}

export interface ReservationReviewPayload {
  action: 'confirm' | 'reject'
  remark: string
}

export interface VenueRankingItem {
  venue_id: number
  venue_name: string
  reservation_count: number
}

export interface StatOverview {
  venue_total: number
  meeting_room_total: number
  user_total: number
  reservation_total: number
  pending_total: number
  today_check_in_total: number
  occupancy_rate: number
  week_total: number
  week_start: string
  week_end: string
  venue_ranking: VenueRankingItem[]
  recent_reservations: Reservation[]
}

export interface Knowledge {
  id: number
  category: string
  question: string
  answer: string
  keywords: string
  status: number
  created_at?: string | null
  updated_at?: string | null
}

export interface KnowledgePayload {
  category: string
  question: string
  answer: string
  keywords: string
  status: number
}

export interface AgentStatus {
  provider: string
  model: string
  llm_enabled: boolean
  knowledge_total: number
  tools: string[]
}

export interface FaqItem {
  category: string
  question: string
}

export interface ChatSession {
  id: number
  title: string
  created_at?: string | null
  updated_at?: string | null
}

/** 助手生成的预约草稿内容，字段可以缺失（信息不完整时后端会给出 problems） */
export interface ReservationDraftPayload {
  venue_id?: number | null
  venue_name?: string
  meeting_room_id?: number | null
  meeting_room_name?: string
  start_at?: string
  end_at?: string
  hours?: number
  rooms?: number
  attendees?: number
  total_amount?: number
  equipment_request?: string
}

export type ChatActionStatus = 'pending' | 'confirmed' | 'canceled' | 'failed'

export interface ChatAction {
  type?: string
  status?: ChatActionStatus
  payload?: ReservationDraftPayload
  problems?: string[]
  note?: string
  error?: string
  reservation_id?: number
}

export interface ChatMessage {
  id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  source: string
  tools: string
  action: ChatAction | null
  created_at?: string | null
}

export interface ChatReply {
  session_id: number
  reply: ChatMessage
  suggestions: string[]
  provider: string
  action: ChatAction | null
}

export interface ChatActionResult {
  action: ChatAction
  message: ChatMessage
  reservation: Reservation | null
}

export interface ChatPayload {
  message: string
  session_id?: number | null
}

export interface ChatActionPayload {
  session_id: number
  message_id: number
}
