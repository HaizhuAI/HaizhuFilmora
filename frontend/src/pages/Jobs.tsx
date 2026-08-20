import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, Progress, Spinner, useToast } from '../components/ui'

export default function Jobs() {
  const { toast } = useToast()
  const [jobs, setJobs] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    // no dedicated job list endpoint; poll health + show local known jobs is not available
    // keep page meaningful: we show active jobs from storage via a lightweight endpoint fallback
    const t = setInterval(async () => {
      try {
        const r = await fetch('/api/ai/jobs/recent', { credentials: 'include' })
        if (r.ok) { const d = await r.json(); setJobs(d.items || []); setLoading(false) }
      } catch { /* endpoint optional */ }
    }, 2500)
    return () => clearInterval(t)
  }, [])
  return (
    <div className="animate-fadeUp">
      <h1 className="text-2xl font-bold tracking-tight">任务中心</h1>
      <p className="mt-1 text-sm text-txt-3">所有编辑 / AI 任务的实时状态</p>
      {loading ? <div className="mt-10 flex justify-center"><Spinner className="h-8 w-8 text-gold-400" /></div> : jobs.length === 0 ? (
        <div className="panel mt-6"><Empty title="暂无任务" icon="⇄" /></div>
      ) : (
        <div className="panel mt-6 overflow-hidden">
          <table className="w-full text-left">
            <thead className="border-b border-line/70 text-[11px] uppercase tracking-wider text-txt-3">
              <tr><th className="cell">任务</th><th className="cell">类型</th><th className="cell">状态</th><th className="cell w-48">进度</th><th className="cell">结果</th></tr>
            </thead>
            <tbody className="divide-y divide-line/50">
              {jobs.map(j => {
                const st = j.status
                return (
                  <tr key={j.id}>
                    <td className="cell mono text-txt-2">{j.id}</td>
                    <td className="cell">{j.type}</td>
                    <td className="cell">
                      <span className={`chip ${st === 'completed' ? 'border-mint/40 text-mint' : st === 'failed' ? 'border-ember/40 text-ember' : st === 'running' ? 'border-sky2/40 text-sky2' : 'text-txt-3'}`}>{st}</span>
                    </td>
                    <td className="cell"><Progress value={j.progress || 0} /></td>
                    <td className="cell">
                      {st === 'completed' && j.result && (() => {
                        try { const r = typeof j.result === 'string' ? JSON.parse(j.result) : j.result; const u = r?.url || r?.video_url || r?.result?.url; return u ? <a href={u} target="_blank" rel="noreferrer" className="text-gold-300 underline-offset-2 hover:underline">查看</a> : '✓' } catch { return '✓' }
                      })()}
                      {st === 'failed' && <span className="text-ember">✕</span>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
