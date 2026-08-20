import { useEffect, useMemo, useState } from 'react'
import { api, fmtDuration, fmtSize } from '../api'
import { Empty, Field, Modal, Progress, Spinner, useToast } from '../components/ui'

const FILTER_PRESETS: Record<string, string> = {
  bw: '黑白', sepia: '复古棕', vintage: '老电影', warm: '暖阳', cool: '冷调', vivid: '鲜艳',
  fade: '胶片淡雅', night: '夜色', dream: '梦幻', noir: '暗黑', sunset: '落日', lomo: 'LOMO',
  hdr: 'HDR', pastel: '粉彩', cinema21: '电影宽屏', glitch: '故障', blur_soft: '柔焦',
  sharpen: '锐化', invert: '反色', vignette: '暗角', golden: '金秋', cyberpunk: '赛博'
}

export default function Editor() {
  const { toast } = useToast()
  const [media, setMedia] = useState<any[]>([])
  const [selected, setSelected] = useState<any>(null)
  const [filters, setFilters] = useState<any[]>([])
  const [probe, setProbe] = useState<any>(null)
  const [ops, setOps] = useState<any[]>([])
  const [exportOpts, setExportOpts] = useState<any>({})
  const [jobId, setJobId] = useState<string | null>(null)
  const [job, setJob] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const [concatIds, setConcatIds] = useState<string[]>([])

  useEffect(() => { api.listMedia().then(d => setMedia(d.items)).catch(() => {}) }, [])
  useEffect(() => { api.filters().then(d => setFilters(d.items)).catch(() => {}) }, [])

  async function pick(m: any) {
    setSelected(m); setOps([]); setJobId(null); setJob(null)
    try { setProbe(await api.probe(m.id)) } catch { setProbe(null) }
  }
  useEffect(() => {
    if (!jobId) return
    const t = setInterval(async () => {
      try {
        const j = await api.job(jobId)
        setJob(j)
        if (j.status === 'completed' || j.status === 'failed') clearInterval(t)
      } catch { clearInterval(t) }
    }, 1800)
    return () => clearInterval(t)
  }, [jobId])

  function addOp(op: any) { setOps(p => [...p, { ...op }]) }
  function removeOp(i: number) { setOps(p => p.filter((_, k) => k !== i)) }
  function updateOp(i: number, patch: any) { setOps(p => p.map((o, k) => k === i ? { ...o, ...patch } : o)) }

  async function run() {
    if (!selected) return
    setBusy(true); setJobId(null); setJob(null)
    try {
      const r = await api.applyEditAsync({ media_id: selected.id, ops, export: exportOpts })
      setJobId(r.job_id)
      toast('ok', `任务已提交 ${r.job_id}`)
    } catch (e: any) { toast('err', e.message) }
    finally { setBusy(false) }
  }
  async function concat() {
    if (concatIds.length < 2) { toast('err', '至少选择 2 个视频'); return }
    setBusy(true)
    try { const r = await api.concat(concatIds); setJobId(r.job_id); toast('ok', '合并任务已提交') }
    catch (e: any) { toast('err', e.message) } finally { setBusy(false) }
  }
  const resultUrl = useMemo(() => {
    if (!job?.result) return ''
    try { const r = typeof job.result === 'string' ? JSON.parse(job.result) : job.result; return r.url || r.video_url || '' } catch { return '' }
  }, [job])

  return (
    <div className="animate-fadeUp space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">剪辑台</h1>
        <p className="mt-1 text-sm text-txt-3">组合编辑操作并导出 — 滤镜 / 裁剪 / 变速 / 文字 / 字幕 / 转场</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        {/* source list */}
        <div className="panel p-3">
          <p className="label px-1">选择素材</p>
          <div className="max-h-[70vh] space-y-1.5 overflow-y-auto pr-1">
            {media.filter(m => m.kind === 'video').length === 0 && <Empty title="暂无视频" hint="先到素材库上传" />}
            {media.filter(m => m.kind === 'video').map(m => (
              <button key={m.id} onClick={() => pick(m)}
                className={`flex w-full items-center gap-2.5 rounded-lg border p-2 text-left transition ${selected?.id === m.id ? 'border-gold-400/50 bg-gold-400/10' : 'border-transparent hover:bg-white/[.04]'}`}>
                <img src={`/api/media/${m.id}/thumbnail`} className="h-10 w-16 shrink-0 rounded object-cover" alt="" />
                <div className="min-w-0">
                  <p className="truncate text-xs font-medium">{m.name}</p>
                  <p className="mono text-[10px] text-txt-3">{fmtDuration(m.duration)} · {m.width}×{m.height}</p>
                </div>
              </button>
            ))}
          </div>
          <div className="mt-3 border-t border-line/60 pt-3">
            <p className="label px-1">多片段合并</p>
            <select multiple className="input h-20 text-xs" value={concatIds} onChange={e => setConcatIds(Array.from(e.target.selectedOptions, o => o.value))}>
              {media.filter(m => m.kind === 'video').map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
            </select>
            <button className="btn-outline mt-2 w-full text-xs" onClick={concat} disabled={busy}>合并选中片段</button>
          </div>
        </div>

        {/* editor panel */}
        <div className="space-y-5">
          {!selected ? (
            <div className="panel"><Empty title="尚未选择素材" hint="从左侧选择一个视频开始" icon="✂" /></div>
          ) : (
            <>
              <div className="panel overflow-hidden">
                <video key={selected.id + '-prev'} src={`/api/media/${selected.id}/file`} controls className="aspect-video w-full bg-black object-contain" />
                <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-line/60 px-4 py-2.5 text-xs">
                  <span className="mono text-txt-2">{selected.name}</span>
                  <span className="text-txt-3">{fmtDuration(selected.duration)}</span>
                  <span className="text-txt-3">{selected.width}×{selected.height}</span>
                  <span className="text-txt-3">{fmtSize(selected.size)}</span>
                </div>
              </div>

              <div className="panel p-4">
                <p className="label">添加操作</p>
                <div className="flex flex-wrap gap-2">
                  <button className="chip hover:border-gold-400/50 hover:text-gold-300" onClick={() => addOp({ op: 'filter', filter: 'bw' })}>黑白</button>
                  <button className="chip hover:border-gold-400/50 hover:text-gold-300" onClick={() => addOp({ op: 'filter', filter: 'vintage' })}>老电影</button>
                  <button className="chip hover:border-gold-400/50 hover:text-gold-300" onClick={() => addOp({ op: 'filter', filter: 'vivid' })}>鲜艳</button>
                  <button className="chip hover:border-gold-400/50 hover:text-gold-300" onClick={() => addOp({ op: 'filter', filter: 'dream' })}>梦幻</button>
                  <button className="chip hover:border-gold-400/50 hover:text-gold-300" onClick={() => addOp({ op: 'speed', factor: 2 })}>2× 加速</button>
                  <button className="chip hover:border-gold-400/50 hover:text-gold-300" onClick={() => addOp({ op: 'speed', factor: 0.5 })}>0.5× 慢放</button>
                  <button className="chip hover:border-gold-400/50 hover:text-gold-300" onClick={() => addOp({ op: 'reverse' })}>倒放</button>
                  <button className="chip hover:border-gold-400/50 hover:text-gold-300" onClick={() => addOp({ op: 'rotate', angle: 90 })}>旋转 90°</button>
                  <button className="chip hover:border-gold-400/50 hover:text-gold-300" onClick={() => addOp({ op: 'flip', direction: 'horizontal' })}>水平翻转</button>
                  <button className="chip hover:border-gold-400/50 hover:text-gold-300" onClick={() => addOp({ op: 'mute' })}>静音</button>
                  <button className="chip hover:border-gold-400/50 hover:text-gold-300" onClick={() => addOp({ op: 'trim', start: 0, end: 3 })}>前 3 秒</button>
                  <button className="chip hover:border-gold-400/50 hover:text-gold-300" onClick={() => addOp({ op: 'text', text: 'Filmora', font_size: 56, color: 'white', y: 'h*0.12' })}>标题文字</button>
                </div>
                <div className="mt-3">
                  <label className="label">滤镜</label>
                  <div className="grid grid-cols-4 gap-1.5 sm:grid-cols-6 md:grid-cols-8">
                    {filters.map(f => (
                      <button key={f.id} onClick={() => addOp({ op: 'filter', filter: f.id })}
                        className={`rounded-md border px-1 py-1.5 text-[11px] transition ${ops.some(o => o.filter === f.id) ? 'border-gold-400/50 bg-gold-400/10 text-gold-300' : 'border-line text-txt-2 hover:border-txt-3'}`}>
                        {FILTER_PRESETS[f.id] || f.name}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {ops.length > 0 && (
                <div className="panel p-4 animate-fadeUp">
                  <p className="label">操作队列</p>
                  <div className="space-y-2">
                    {ops.map((op, i) => (
                      <div key={i} className="panel-2 flex items-center justify-between gap-3 px-3 py-2 text-xs">
                        <div className="flex items-center gap-2">
                          <span className="mono text-txt-3">{String(i + 1).padStart(2, '0')}</span>
                          <span className="chip border-gold-400/20 text-gold-300">{op.op}</span>
                          <span className="mono text-txt-2 truncate">{JSON.stringify(op).slice(0, 90)}</span>
                        </div>
                        <button className="btn-ghost px-2 text-txt-3 hover:text-ember" onClick={() => removeOp(i)}>✕</button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="panel p-4">
                <p className="label">导出设置</p>
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                  <Field label="方向"><select className="input" value={exportOpts.orientation || ''} onChange={e => setExportOpts({ ...exportOpts, orientation: e.target.value })}>
                    <option value="">原始</option><option value="16:9">16:9 横屏</option><option value="9:16">9:16 竖屏</option><option value="1:1">1:1 方形</option>
                  </select></Field>
                  <Field label="质量 CRF"><input type="number" min={18} max={32} className="input" value={exportOpts.crf ?? 20} onChange={e => setExportOpts({ ...exportOpts, crf: +e.target.value })} /></Field>
                  <Field label="帧率"><select className="input" value={exportOpts.fps || ''} onChange={e => setExportOpts({ ...exportOpts, fps: e.target.value })}>
                    <option value="">默认</option><option value="24">24</option><option value="30">30</option><option value="60">60</option>
                  </select></Field>
                  <Field label="导出格式"><select className="input" value={exportOpts.format || 'mp4'} onChange={e => setExportOpts({ ...exportOpts, format: e.target.value })}>
                    <option value="mp4">MP4</option><option value="gif">GIF</option>
                  </select></Field>
                </div>
                <div className="mt-4 flex items-center gap-3">
                  <button className="btn-primary" onClick={run} disabled={busy || !selected}>{busy ? <Spinner /> : '导出 / 应用'}</button>
                  {jobId && <span className="mono text-txt-3">{jobId}</span>}
                </div>
                {job && (job.status === 'running' || job.status === 'queued') && (
                  <div className="mt-3"><Progress value={job.progress || 0} /><p className="mono mt-1 text-[10px] text-txt-3">{job.status} · {Math.round((job.progress || 0) * 100)}%</p></div>
                )}
                {job?.status === 'failed' && <p className="mt-3 text-xs text-ember">失败：{job.error?.message || job.error}</p>}
                {resultUrl && (
                  <div className="mt-4 animate-fadeUp">
                    <p className="label">导出结果</p>
                    <video src={resultUrl} controls className="max-h-72 w-full rounded-lg bg-black" />
                    <a className="btn-outline mt-2 text-xs" href={resultUrl} target="_blank" rel="noreferrer">下载文件</a>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
