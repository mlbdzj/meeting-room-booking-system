import { lazy, Suspense, useEffect, type ReactNode } from 'react'
import { createBrowserRouter, Navigate, useLocation } from 'react-router-dom'

import type { Role } from '@/api/types'
import PageLoading from '@/components/PageLoading'
import Layout from '@/layouts/Layout'
import { useUserStore } from '@/store/user'
import { feedback } from '@/utils/feedback'

const Home = lazy(() => import('@/views/Home'))
const Venue = lazy(() => import('@/views/Venue'))
const MeetingRoom = lazy(() => import('@/views/MeetingRoom'))
const UserPage = lazy(() => import('@/views/User'))
const Reservation = lazy(() => import('@/views/Reservation'))
const ReservationReview = lazy(() => import('@/views/ReservationReview'))
const Knowledge = lazy(() => import('@/views/Knowledge'))
const Login = lazy(() => import('@/views/Login'))
const Register = lazy(() => import('@/views/Register'))

function LazyView({ children }: { children: ReactNode }) {
  return <Suspense fallback={<PageLoading />}>{children}</Suspense>
}

/** 登录态与角色校验：未登录跳登录页，角色不符回首页 */
function Protected({ roles, children }: { roles?: Role[]; children: ReactNode }) {
  const token = useUserStore((state) => state.token)
  const role = useUserStore((state) => state.user?.role)
  const location = useLocation()

  const hasToken = Boolean(token)
  const denied = hasToken && Boolean(roles?.length) && (!role || !roles?.includes(role))

  useEffect(() => {
    if (denied) feedback.warning('无权访问该页面')
  }, [denied])

  if (!hasToken) {
    return <Navigate to="/login" replace state={{ redirect: `${location.pathname}${location.search}` }} />
  }
  if (denied) return <Navigate to="/manager/home" replace />
  return <>{children}</>
}

/** 已登录用户不再看到登录 / 注册页 */
function PublicOnly({ children }: { children: ReactNode }) {
  const token = useUserStore((state) => state.token)
  if (token) return <Navigate to="/manager/home" replace />
  return <>{children}</>
}

export const router = createBrowserRouter([
  { path: '/', element: <Navigate to="/manager/home" replace /> },
  {
    path: '/manager',
    element: (
      <Protected>
        <LazyView>
          <Layout />
        </LazyView>
      </Protected>
    ),
    children: [
      { index: true, element: <Navigate to="/manager/home" replace /> },
      {
        path: 'home',
        element: (
          <LazyView>
            <Home />
          </LazyView>
        ),
      },
      {
        path: 'venue',
        element: (
          <LazyView>
            <Venue />
          </LazyView>
        ),
      },
      {
        path: 'meeting-room',
        element: (
          <Protected roles={['admin']}>
            <LazyView>
              <MeetingRoom />
            </LazyView>
          </Protected>
        ),
      },
      {
        path: 'user',
        element: (
          <Protected roles={['admin']}>
            <LazyView>
              <UserPage />
            </LazyView>
          </Protected>
        ),
      },
      {
        path: 'reservation',
        element: (
          <LazyView>
            <Reservation />
          </LazyView>
        ),
      },
      {
        path: 'reservation-review',
        element: (
          <Protected roles={['admin']}>
            <LazyView>
              <ReservationReview />
            </LazyView>
          </Protected>
        ),
      },
      {
        path: 'knowledge',
        element: (
          <Protected roles={['admin']}>
            <LazyView>
              <Knowledge />
            </LazyView>
          </Protected>
        ),
      },
    ],
  },
  {
    path: '/login',
    element: (
      <PublicOnly>
        <LazyView>
          <Login />
        </LazyView>
      </PublicOnly>
    ),
  },
  {
    path: '/register',
    element: (
      <PublicOnly>
        <LazyView>
          <Register />
        </LazyView>
      </PublicOnly>
    ),
  },
  { path: '*', element: <Navigate to="/manager/home" replace /> },
])
