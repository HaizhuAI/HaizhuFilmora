import { FormEvent, useState } from 'react'
import { api } from '../api'

export default function Login({ onDone }: { onDone: () => void }) {
  const [pw, setPw] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true); setErr('')
    try { await api.login(pw); onDone() }
    catch (x: any) { setErr(x.message || '登录失败') }
    finally { setBusy(false) }
  }
  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute left-1/2 top-1/3 h-72 w-72 -translate-x-1/2 rounded-full bg-gold-400/10 blur-[110px]" />
      </div>
      <div className="relative w-full max-w-sm panel animate-fadeUp p-7">
        <div className="mb-6 flex flex-col items-center text-center">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-gold-400 text-ink-0 shadow-glow">
            <svg viewBox="0 0 24 24" className="h-6 w-6" fill="currentColor"><path d="M6 4l14 8-14 8z" /></svg>
          </div>
          <h1 className="text-lg font-bold tracking-tight">Filmora WebUI</h1>
          <p className="mt-1 text-xs text-txt-3">AI 视频工作台 · 管理员入口</p>
        </div>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="label" htmlFor="pw">管理员密码</label>
            <input id="pw" type="password" className="input" placeholder="输入密码"
              value={pw} onChange={e => setPw(e.target.value)} autoFocus />
          </div>
          {err && <p className="text-xs text-ember" role="alert">{err}</p>}
          <button type="submit" disabled={busy || !pw} className="btn-primary w-full">
            {busy ? '验证中…' : '进入工作台'}
          </button>
        </form>
        <p className="mt-5 text-center text-[10px] uppercase tracking-[0.2em] text-txt-3">
          Premium 功能已全部解锁 · 无广告
        </p>
      </div>
    </div>
  )
}
