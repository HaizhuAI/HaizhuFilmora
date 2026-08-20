import React, { useEffect, useState, useCallback } from 'react'

export function Spinner({ className = 'h-4 w-4' }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none">
      <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
      <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}

export function Progress({ value, className = '' }: { value: number; className?: string }) {
  const v = Math.max(0, Math.min(100, Math.round(value * 100)))
  return (
    <div className={`h-1.5 w-full overflow-hidden rounded-full bg-white/5 ${className}`}>
      <div className="h-full rounded-full bg-gold-400 transition-[width] duration-300" style={{ width: `${v}%` }} />
    </div>
  )
}

export function Modal({ open, onClose, title, children, wide = false }: { open: boolean; onClose: () => void; title: string; children: React.ReactNode; wide?: boolean }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label={title}>
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className={`relative w-full ${wide ? 'max-w-3xl' : 'max-w-md'} panel animate-fadeUp p-5`}>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-base font-semibold">{title}</h3>
          <button onClick={onClose} className="btn-ghost -mr-2 px-2 py-1 text-txt-3 hover:text-txt-1" aria-label="关闭">✕</button>
        </div>
        {children}
      </div>
    </div>
  )
}

type ToastKind = 'ok' | 'err' | 'info'
interface Toast { id: number; kind: ToastKind; text: string }
const ToastCtx = React.createContext<{ toast: (kind: ToastKind, text: string) => void }>({ toast: () => {} })
export const useToast = () => React.useContext(ToastCtx)

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<Toast[]>([])
  const toast = useCallback((kind: ToastKind, text: string) => {
    const id = Date.now() + Math.random()
    setItems(p => [...p, { id, kind, text }])
    setTimeout(() => setItems(p => p.filter(t => t.id !== id)), 4200)
  }, [])
  return (
    <ToastCtx.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-5 right-5 z-[60] flex flex-col gap-2" aria-live="polite">
        {items.map(t => (
          <div key={t.id} className={`panel animate-fadeUp px-4 py-2.5 text-sm flex items-center gap-2.5 border-l-2 ${
            t.kind === 'ok' ? 'border-mint' : t.kind === 'err' ? 'border-ember' : 'border-sky2'
          }`}>
            <span className={`h-2 w-2 rounded-full ${t.kind === 'ok' ? 'bg-mint' : t.kind === 'err' ? 'bg-ember' : 'bg-sky2'}`} />
            <span className="text-txt-1">{t.text}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}

export function Empty({ title, hint, icon = '◌' }: { title: string; hint?: string; icon?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl border border-dashed border-line text-xl text-txt-3">{icon}</div>
      <p className="text-sm font-medium text-txt-2">{title}</p>
      {hint && <p className="mt-1 text-xs text-txt-3">{hint}</p>}
    </div>
  )
}

export function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <div>
      <label className="label">{label}</label>
      {children}
      {hint && <p className="mt-1 text-[11px] text-txt-3">{hint}</p>}
    </div>
  )
}

export function usePolling<T>(fn: () => Promise<T>, deps: any[], interval = 2500, enabled = true) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let alive = true
    let timer: any
    const run = async () => {
      try {
        const d = await fn()
        if (alive) { setData(d); setError(null) }
      } catch (e: any) {
        if (alive) setError(e.message || '请求失败')
      } finally {
        if (alive) setLoading(false)
      }
    }
    run()
    if (enabled) timer = setInterval(run, interval)
    return () => { alive = false; clearInterval(timer) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  return { data, loading, error, refetch: () => {} }
}
