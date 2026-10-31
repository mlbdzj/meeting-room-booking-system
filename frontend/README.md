# 智能会议室预约系统 · 前端

React 19 + TypeScript + Ant Design 5 + Vite 8 单页应用。

## 技术栈

| 关注点 | 选型 |
| --- | --- |
| 框架 | React 19 + TypeScript |
| 构建 | Vite 8 |
| 路由 | React Router 7（`createBrowserRouter`） |
| UI 组件 | Ant Design 5（中文语言包 + 统一 design token，主色取 antd 默认蓝） |
| 状态 | Zustand（登录态持久化到 localStorage） |
| HTTP | 原生 `fetch` 封装（`src/api/request.ts`） |
| 日期 | dayjs |

## 常用命令

```sh
npm install          # 安装依赖
npm run dev          # 开发服务器（/api 已代理到 127.0.0.1:8000）
npm run build        # 类型检查 + 生产构建
npm run preview      # 预览构建产物
npm run typecheck    # 只做 TypeScript 类型检查
```

## 目录结构

```
src/
  api/         请求层与接口封装（request.ts 统一处理 Token、401 与错误文案）
  components/  ReservationDialog（预约弹窗）、AgentChat（智能助手）、PageLoading
  config/      侧边菜单配置（同时用于菜单渲染与页面标题）
  hooks/       useDocumentTitle 等通用 Hook
  layouts/     主框架（顶栏、角色化菜单、个人信息 / 修改密码、悬浮助手）
  router/      路由表与登录态 / 角色守卫
  store/       Zustand 登录态与角色、预约状态字典
  utils/       format（日期与金额格式化）、feedback（非组件代码里的 message / modal）
  views/       登录、注册、首页概览、会议空间、会议室、会员、我的预约、预约审核、预约知识库
```
