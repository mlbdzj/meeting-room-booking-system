import { http } from '@/api/request'
import type {
  AgentStatus,
  Availability,
  Reservation,
  ReservationPayload,
  ReservationReviewPayload,
  ChatActionPayload,
  ChatActionResult,
  ChatMessage,
  ChatPayload,
  ChatReply,
  ChatSession,
  FaqItem,
  Venue,
  VenuePayload,
  Knowledge,
  KnowledgePayload,
  LoginPayload,
  LoginResult,
  MessageResult,
  PageResult,
  PasswordPayload,
  ProfilePayload,
  MeetingRoom,
  MeetingRoomPayload,
  StatOverview,
  UserCreatePayload,
  UserInfo,
  UserPayload,
  RegisterPayload,
} from '@/api/types'

export const authApi = {
  login: (data: LoginPayload) => http.post<LoginResult>('/auth/login', data, { silent: true }),
  register: (data: RegisterPayload) => http.post<UserInfo>('/auth/register', data, { silent: true }),
  me: () => http.get<UserInfo>('/auth/me'),
  updateProfile: (data: ProfilePayload) => http.put<UserInfo>('/auth/me', data),
  changePassword: (data: PasswordPayload) => http.put<MessageResult>('/auth/password', data),
}

export const venueApi = {
  list: (params?: Record<string, unknown>) => http.get<PageResult<Venue>>('/venues', params),
  detail: (id: number) => http.get<Venue>(`/venues/${id}`),
  availability: (id: number, startAt: string, endAt: string) =>
    http.get<Availability>(`/venues/${id}/availability`, { start_at: startAt, end_at: endAt }),
  create: (data: VenuePayload) => http.post<Venue>('/venues', data),
  update: (id: number, data: VenuePayload) => http.put<Venue>(`/venues/${id}`, data),
  remove: (id: number) => http.delete<MessageResult>(`/venues/${id}`),
}

export const meetingRoomApi = {
  page: (params?: Record<string, unknown>) =>
    http.get<PageResult<MeetingRoom>>('/meeting-rooms', params),
  all: (params?: Record<string, unknown>) =>
    http.get<MeetingRoom[]>('/meeting-rooms/all', params),
  create: (data: MeetingRoomPayload) => http.post<MeetingRoom>('/meeting-rooms', data),
  update: (id: number, data: MeetingRoomPayload) =>
    http.put<MeetingRoom>(`/meeting-rooms/${id}`, data),
  remove: (id: number) => http.delete<MessageResult>(`/meeting-rooms/${id}`),
}

export const userApi = {
  page: (params?: Record<string, unknown>) => http.get<PageResult<UserInfo>>('/users', params),
  create: (data: UserCreatePayload) => http.post<UserInfo>('/users', data),
  update: (id: number, data: UserPayload) => http.put<UserInfo>(`/users/${id}`, data),
  resetPassword: (id: number, data: { new_password: string }) =>
    http.put<MessageResult>(`/users/${id}/password`, data),
  remove: (id: number) => http.delete<MessageResult>(`/users/${id}`),
}

export const reservationApi = {
  my: (params?: Record<string, unknown>) =>
    http.get<PageResult<Reservation>>('/reservations/my', params),
  page: (params?: Record<string, unknown>) =>
    http.get<PageResult<Reservation>>('/reservations', params),
  create: (data: ReservationPayload) => http.post<Reservation>('/reservations', data),
  review: (id: number, data: ReservationReviewPayload) =>
    http.post<Reservation>(`/reservations/${id}/review`, data),
  cancel: (id: number) => http.post<Reservation>(`/reservations/${id}/cancel`),
  finish: (id: number) => http.post<Reservation>(`/reservations/${id}/finish`),
  remove: (id: number) => http.delete<MessageResult>(`/reservations/${id}`),
}

export const statsApi = {
  overview: () => http.get<StatOverview>('/stats/overview'),
}

export const agentApi = {
  status: () => http.get<AgentStatus>('/agent/status'),
  faq: () => http.get<FaqItem[]>('/agent/faq'),
  sessions: () => http.get<ChatSession[]>('/agent/sessions'),
  createSession: () => http.post<ChatSession>('/agent/sessions'),
  messages: (sessionId: number) => http.get<ChatMessage[]>(`/agent/sessions/${sessionId}/messages`),
  removeSession: (sessionId: number) => http.delete<MessageResult>(`/agent/sessions/${sessionId}`),
  chat: (data: ChatPayload) => http.post<ChatReply>('/agent/chat', data, { silent: true }),
  confirmAction: (data: ChatActionPayload) =>
    http.post<ChatActionResult>('/agent/actions/confirm', data, { silent: true }),
  cancelAction: (data: ChatActionPayload) =>
    http.post<ChatActionResult>('/agent/actions/cancel', data, { silent: true }),
}

export const knowledgeApi = {
  page: (params?: Record<string, unknown>) => http.get<PageResult<Knowledge>>('/knowledge', params),
  categories: () => http.get<string[]>('/knowledge/categories'),
  create: (data: KnowledgePayload) => http.post<Knowledge>('/knowledge', data),
  update: (id: number, data: KnowledgePayload) => http.put<Knowledge>(`/knowledge/${id}`, data),
  remove: (id: number) => http.delete<MessageResult>(`/knowledge/${id}`),
}
