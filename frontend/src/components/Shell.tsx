import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { api } from '../api'
import { useToast } from './ui'

const NAV = [
  { to: '/media', label: '素材库', icon: '▦' },
  { to: '/editor', label: '剪辑台', icon: '✂' },
  { to: '/ai', label: 'AI 工坊', icon: '✦' },
  { to: '/jobs', label: '任务中心', icon: '⇄' },
  { to: '/keys', label: 'API 密钥', icon: '⌘' }
]

export default function Shell() {
  const nav = useNavigate()
  const { toast } = useToast()
  const [busy, setBusy] = useState(false)
  async function logout() {
    setBusy(true)
    await api.logout()
    toast('info', '已退出')
    nav('/login')
  }
  return (
    <div className="flex h-screen overflow-hidden">
      <aside className="w-60 shrink-0 border-r border-line/70 bg-ink-1/80 backdrop-blur flex flex-col">
        <div className="flex items-center gap-2.5 px-5 py-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gold-400 text-ink-0 shadow-glow">
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor"><path d="M6 4l14 8-14 8z" /></svg>
          </div>
          <div>
            <p className="text-sm font-bold tracking-tight leading-none">Filmora WebUI</p>
            <p className="mt-1 text-[10px] uppercase tracking-[0.2em] text-txt-3">AI Video Workstation</p>
          </div>
        </div>
        <nav className="mt-2 flex-1 space-y-1 px-3" aria-label="主导航">
          {NAV.map(item => (
            <NavLink key={item.to} to={item.to}
              className={({ isActive }) =>
                `group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition ${
                  isActive ? 'bg-gold-400/10 text-gold-300 border border-gold-400/20' : 'text-txt-2 hover:bg-white/[.04] hover:text-txt-1 border border-transparent'}`
              }>
              <span className="w-5 text-center text-base leading-none">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-line/70 p-4">
          <div className="mb-3 flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-mint animate-pulseSoft" />
            <span className="mono text-txt-3">PREMIUM · UNLOCKED</span>
          </div>
          <button onClick={logout} disabled={busy} className="btn-outline w-full text-xs">退出登录</button>
        </div>
      </aside>
      <main className="relative flex-1 overflow-y-auto">
        <div className="pointer-events-none absolute inset-0 bg-grain opacity-60" aria-hidden="true" />
        <div className="relative mx-auto max-w-[1400px] p-6 lg:p-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
