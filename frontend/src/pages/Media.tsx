import { useEffect, useRef, useState } from 'react'
import { api, fmtDuration, fmtSize } from '../api'
import { Empty, Spinner, useToast, Modal } from '../components/ui'

export default function Media() {
  const { toast } = useToast()
  const [items, setItems] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [preview, setPreview] = useState<any>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  async function load() {
    setLoading(true)
    try { const d = await api.listMedia(); setItems(d.items) }
    catch (e: any) { toast('err', e.message) }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  async function onUpload(files: FileList | null) {
    if (!files || !files.length) return
    setUploading(true)
    for (const f of Array.from(files)) {
      try { await api.uploadMedia(f); toast('ok', `已上传 ${f.name}`) }
      catch (e: any) { toast('err', e.message) }
    }
    setUploading(false)
    if (fileRef.current) fileRef.current.value = ''
    load()
  }
  async function del(item: any) {
    if (!confirm(`删除 ${item.name}？`)) return
    try { await api.deleteMedia(item.id); toast('ok', '已删除'); load() }
    catch (e: any) { toast('err', e.message) }
  }
  const kindIcon: Record<string, string> = { video: '▶', image: '🖼', audio: '♪' }

  return (
    <div className="animate-fadeUp">
      <div className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">素材库</h1>
          <p className="mt-1 text-sm text-txt-3">上传视频 / 图片 / 音频，作为剪辑与 AI 处理的输入</p>
        </div>
        <button className="btn-primary" onClick={() => fileRef.current?.click()} disabled={uploading}>
          {uploading ? <Spinner /> : '＋'} {uploading ? '上传中…' : '上传素材'}
        </button>
        <input ref={fileRef} type="file" multiple accept="video/*,image/*,audio/*" className="hidden" onChange={e => onUpload(e.target.files)} />
      </div>

      {loading ? (
        <div className="flex justify-center py-24"><Spinner className="h-8 w-8 text-gold-400" /></div>
      ) : items.length === 0 ? (
        <div className="panel"><Empty title="暂无素材" hint="点击右上角上传第一个视频文件" icon="▦" /></div>
      ) : (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">
          {items.map((m, i) => (
            <div key={m.id} className="panel group overflow-hidden animate-fadeUp" style={{ animationDelay: `${i * 40}ms` }}>
              <div className="relative aspect-video cursor-pointer overflow-hidden bg-black/40" onClick={() => setPreview(m)}>
                {m.kind === 'video' ? (
                  <img src={`/api/media/${m.id}/thumbnail`} alt={m.name} className="h-full w-full object-cover opacity-80 transition duration-300 group-hover:scale-[1.03] group-hover:opacity-100" loading="lazy" />
                ) : m.kind === 'image' ? (
                  <img src={`/api/media/${m.id}/file`} alt={m.name} className="h-full w-full object-cover opacity-90 transition duration-300 group-hover:scale-[1.03]" loading="lazy" />
                ) : (
                  <div className="flex h-full items-center justify-center text-4xl text-txt-3">♪</div>
                )}
                <div className="absolute left-2 top-2 chip bg-black/50 border-white/10 text-txt-1">
                  <span>{kindIcon[m.kind] || '▣'}</span>
                </div>
                {m.kind === 'video' && (
                  <span className="absolute bottom-2 right-2 mono rounded bg-black/60 px-1.5 py-0.5 text-txt-2">{fmtDuration(m.duration)}</span>
                )}
                <div className="absolute inset-0 flex items-center justify-center bg-black/0 opacity-0 transition group-hover:bg-black/30 group-hover:opacity-100">
                  <span className="flex h-10 w-10 items-center justify-center rounded-full bg-gold-400 text-ink-0 shadow-glow">▶</span>
                </div>
              </div>
              <div className="flex items-center justify-between gap-2 px-3 py-2.5">
                <div className="min-w-0">
                  <p className="truncate text-xs font-medium" title={m.name}>{m.name}</p>
                  <p className="mono mt-0.5 text-[10px] text-txt-3">{m.kind.toUpperCase()} · {fmtSize(m.size)}</p>
                </div>
                <button onClick={() => del(m)} className="btn-ghost px-2 py-1 text-xs text-txt-3 hover:text-ember" aria-label={`删除 ${m.name}`}>✕</button>
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal open={!!preview} onClose={() => setPreview(null)} title={preview?.name || ''} wide>
        {preview?.kind === 'video' ? (
          <video src={`/api/media/${preview?.id}/file`} controls className="w-full rounded-lg bg-black" />
        ) : preview?.kind === 'image' ? (
          <img src={`/api/media/${preview?.id}/file`} alt={preview?.name} className="mx-auto max-h-[60vh] rounded-lg" />
        ) : (
          <audio src={`/api/media/${preview?.id}/file`} controls className="w-full" />
        )}
        <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
          <div className="panel-2 px-3 py-2"><span className="label">时长</span><span className="mono">{fmtDuration(preview?.duration)}</span></div>
          <div className="panel-2 px-3 py-2"><span className="label">尺寸</span><span className="mono">{preview?.width}×{preview?.height}</span></div>
        </div>
      </Modal>
    </div>
  )
}
