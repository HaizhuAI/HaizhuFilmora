import { useEffect, useState } from 'react'
import { api, fmtDuration } from '../api'
import { Empty, Field, Progress, Spinner, useToast } from '../components/ui'

type Tab = 't2v' | 'subtitles' | 'remove' | 'autoclip'

export default function AIStudio() {
  const { toast } = useToast()
  const [tab, setTab] = useState<Tab>('t2v')
  const [media, setMedia] = useState<any[]>([])
  const [jobId, setJobId] = useState<string | null>(null)
  const [job, setJob] = useState<any>(null)
  const [busy, setBusy] = useState(false)

  // t2v state
  const [prompt, setPrompt] = useState('一只猫在夏日的阳台上弹钢琴，暖色调，电影感')
  const [duration, setDuration] = useState(6)
  const [orientation, setOrientation] = useState('16:9')
  const [voiceover, setVoiceover] = useState('')
  // subtitles
  const [subMedia, setSubMedia] = useState('')
  const [subBurn, setSubBurn] = useState(true)
  // remove
  const [rmMedia, setRmMedia] = useState('')
  const [rmMode, setRmMode] = useState('background')
  // autoclip
  const [acMedia, setAcMedia] = useState('')
  const [acMax, setAcMax] = useState(5)

  useEffect(() => { api.listMedia().then(d => { setMedia(d.items); const v = d.items.find(i => i.kind === 'video'); if (v) { setSubMedia(subMedia || v.id); setRmMedia(rmMedia || v.id); setAcMedia(acMedia || v.id) } }).catch(() => {}) }, [])
  useEffect(() => {
    if (!jobId) return
    const t = setInterval(async () => {
      try { const j = await api.job(jobId); setJob(j); if (j.status === 'completed' || j.status === 'failed') clearInterval(t) } catch { clearInterval(t) }
    }, 1800)
    return () => clearInterval(t)
  }, [jobId])

  function launch(fn: () => Promise<any>) {
    setBusy(true); setJobId(null); setJob(null)
    fn().then(r => { setJobId(r.job_id); toast('ok', '任务已提交') }).catch((e: any) => toast('err', e.message)).finally(() => setBusy(false))
  }

  const TABS: { id: Tab; label: string; icon: string }[] = [
    { id: 't2v', label: '文生视频', icon: '✦' },
    { id: 'subtitles', label: '智能字幕', icon: '≡' },
    { id: 'remove', label: 'AI 消除', icon: '◐' },
    { id: 'autoclip', label: 'AI 自动剪辑', icon: '❖' }
  ]
  const resultUrl = (() => {
    if (!job?.result) return ''
    try { const r = typeof job.result === 'string' ? JSON.parse(job.result) : job.result; return r.url || r.video_url || (r.result?.url) || (r.result?.video_url) || '' } catch { return '' }
  })()
  const resultMeta = (() => {
    if (!job?.result) return null
    try { const r = typeof job.result === 'string' ? JSON.parse(job.result) : job.result; return r } catch { return null }
  })()

  return (
    <div className="animate-fadeUp space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">AI 工坊</h1>
        <p className="mt-1 text-sm text-txt-3">封装自 Filmora 高级版 AI 能力：文生视频 / 智能字幕 / AI 消除 / 自动剪辑</p>
      </div>

      <div className="flex gap-2" role="tablist">
        {TABS.map(t => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}
            className={`rounded-lg border px-4 py-2 text-sm transition ${tab === t.id ? 'border-gold-400/40 bg-gold-400/10 text-gold-300' : 'border-line text-txt-2 hover:text-txt-1'}`}>
            <span className="mr-1.5">{t.icon}</span>{t.label}
          </button>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
        <div className="panel p-5">
          {tab === 't2v' && (
            <div className="space-y-4">
              <Field label="提示词"><textarea className="input min-h-[110px] resize-y" value={prompt} onChange={e => setPrompt(e.target.value)} placeholder="描述你想生成的视频…" /></Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="时长(秒)"><input type="number" min={1.5} max={30} className="input" value={duration} onChange={e => setDuration(+e.target.value)} /></Field>
                <Field label="方向"><select className="input" value={orientation} onChange={e => setOrientation(e.target.value)}>
                  <option value="16:9">16:9 横屏</option><option value="9:16">9:16 竖屏</option><option value="1:1">1:1 方形</option>
                </select></Field>
              </div>
              <Field label="配音文案（可选，edge-tts 合成）"><input className="input" value={voiceover} onChange={e => setVoiceover(e.target.value)} placeholder="留空为无配音" /></Field>
              <button className="btn-primary w-full" disabled={busy || !prompt.trim()} onClick={() => launch(() => api.t2v({ prompt, duration, orientation, voiceover, provider: 'local' }))}>
                {busy ? <Spinner /> : '生成视频'}
              </button>
              <p className="text-[11px] text-txt-3">本地引擎直接产出 MP4；配 T2V_API_BASE 可切换到外部模型</p>
            </div>
          )}
          {tab === 'subtitles' && (
            <div className="space-y-4">
              <Field label="视频"><select className="input" value={subMedia} onChange={e => setSubMedia(e.target.value)}>
                {media.filter(m => m.kind === 'video').map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
              </select></Field>
              <label className="flex items-center gap-2 text-sm text-txt-2"><input type="checkbox" checked={subBurn} onChange={e => setSubBurn(e.target.checked)} className="accent-gold-400" /> 烧录字幕到画面</label>
              <button className="btn-primary w-full" disabled={busy || !subMedia} onClick={() => launch(() => api.subtitles({ media_id: subMedia, lang: 'auto', burn_in: subBurn }))}>
                {busy ? <Spinner /> : '生成智能字幕'}
              </button>
              <p className="text-[11px] text-txt-3">安装 faster-whisper 后为真实语音转写；未安装时输出占位 SRT</p>
            </div>
          )}
          {tab === 'remove' && (
            <div className="space-y-4">
              <Field label="媒体"><select className="input" value={rmMedia} onChange={e => setRmMedia(e.target.value)}>
                {media.map(m => <option key={m.id} value={m.id}>{m.name} · {m.kind}</option>)}
              </select></Field>
              <Field label="模式"><select className="input" value={rmMode} onChange={e => setRmMode(e.target.value)}>
                <option value="background">背景消除（抠像）</option>
              </select></Field>
              <button className="btn-primary w-full" disabled={busy || !rmMedia} onClick={() => launch(() => api.remove({ media_id: rmMedia, mode: rmMode }))}>
                {busy ? <Spinner /> : 'AI 消除'}
              </button>
            </div>
          )}
          {tab === 'autoclip' && (
            <div className="space-y-4">
              <Field label="视频"><select className="input" value={acMedia} onChange={e => setAcMedia(e.target.value)}>
                {media.filter(m => m.kind === 'video').map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
              </select></Field>
              <Field label="最大片段数"><input type="number" min={1} max={20} className="input" value={acMax} onChange={e => setAcMax(+e.target.value)} /></Field>
              <button className="btn-primary w-full" disabled={busy || !acMedia} onClick={() => launch(() => api.autoclip({ media_id: acMedia, mode: 'highlights', max_clips: acMax }))}>
                {busy ? <Spinner /> : '自动剪辑高光片段'}
              </button>
            </div>
          )}
        </div>

        <div className="space-y-4">
          {!jobId && !job && <div className="panel"><Empty title="等待任务" hint="配置左侧参数并提交" icon="✦" /></div>}
          {jobId && job && (
            <div className="panel p-5 animate-fadeUp">
              <div className="mb-3 flex items-center justify-between">
                <span className="mono text-txt-3">{jobId}</span>
                <span className={`chip ${job.status === 'completed' ? 'border-mint/40 text-mint' : job.status === 'failed' ? 'border-ember/40 text-ember' : 'border-sky2/40 text-sky2'}`}>
                  {job.status}
                </span>
              </div>
              {(job.status === 'running' || job.status === 'queued') && (
                <>
                  <Progress value={job.progress || 0} />
                  <p className="mono mt-2 text-[11px] text-txt-3">{Math.round((job.progress || 0) * 100)}% · {job.result?.note || ''}</p>
                </>
              )}
              {job.status === 'failed' && <p className="mt-2 text-xs text-ember">{(job.error?.message || job.error || '').slice(0, 500)}</p>}
            </div>
          )}
          {resultUrl && (
            <div className="panel overflow-hidden animate-fadeUp">
              <div className="px-4 py-3 border-b border-line/60"><p className="label mb-0">生成结果</p></div>
              <div className="p-4">
                {resultUrl.endsWith('.webm') || resultUrl.endsWith('.mp4') ? (
                  <video src={resultUrl} controls className="max-h-[50vh] w-full rounded-lg bg-black" />
                ) : (
                  <img src={resultUrl} alt="result" className="max-h-[50vh] rounded-lg bg-black" />
                )}
                <div className="mt-3 flex flex-wrap gap-2">
                  <a className="btn-outline text-xs" href={resultUrl} target="_blank" rel="noreferrer">下载</a>
                  {resultMeta?.clips && (
                    <div className="w-full space-y-1.5">
                      {resultMeta.clips.map((c: any) => (
                        <a key={c.index} href={c.path} target="_blank" rel="noreferrer" className="flex items-center justify-between rounded-lg border border-line px-3 py-2 text-xs hover:border-gold-400/40">
                          <span>片段 {c.index}</span><span className="mono text-txt-3">{fmtDuration(c.duration)}</span>
                        </a>
                      ))}
                    </div>
                  )}
                  {resultMeta?.segments && (
                    <div className="w-full space-y-1.5">
                      {resultMeta.segments.map((s: any, i: number) => (
                        <div key={i} className="rounded-lg border border-line px-3 py-2 text-xs">
                          <span className="mono text-txt-3">{fmtDuration(s.start)} → {fmtDuration(s.end)}</span>
                          <span className="ml-2 text-txt-1">{s.text}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
