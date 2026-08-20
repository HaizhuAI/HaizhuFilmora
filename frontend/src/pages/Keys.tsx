import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, Field, Spinner, useToast } from '../components/ui'

export default function Keys() {
  const { toast } = useToast()
  const [keys, setKeys] = useState<any[]>([])
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [showNew, setShowNew] = useState<string | null>(null)

  async function load() { try { setKeys((await api.listKeys()).items) } catch {} }
  useEffect(() => { load() }, [])
  async function create() {
    setBusy(true)
    try { const k = await api.createKey(name || 'default'); setShowNew(k.key); setName(''); toast('ok', '密钥已创建'); load() }
    catch (e: any) { toast('err', e.message) } finally { setBusy(false) }
  }
  async function del(key: string) {
    if (!confirm('撤销该密钥？')) return
    try { await api.deleteKey(key); toast('ok', '已撤销'); load() } catch (e: any) { toast('err', e.message) }
  }
  async function copy(t: string) {
    try { await navigator.clipboard.writeText(t); toast('ok', '已复制') } catch { toast('err', '复制失败') }
  }

  return (
    <div className="animate-fadeUp space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">API 密钥</h1>
          <p className="mt-1 text-sm text-txt-3">OpenAI 兼容接口凭据：调用地址 <code className="mono text-gold-300">/v1/videos/generations</code>，用 <code className="mono text-gold-300">Authorization: Bearer &lt;key&gt;</code> 鉴权</p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[340px_1fr]">
        <div className="panel p-5">
          <p className="label">创建新密钥</p>
          <div className="space-y-3">
            <Field label="名称"><input className="input" value={name} onChange={e => setName(e.target.value)} placeholder="如：production / 测试" /></Field>
            <button className="btn-primary w-full" onClick={create} disabled={busy}>{busy ? <Spinner /> : '创建密钥'}</button>
          </div>
          {showNew && (
            <div className="mt-4 rounded-lg border border-mint/30 bg-mint/5 p-3 animate-fadeUp">
              <p className="text-xs font-semibold text-mint">新密钥（仅显示一次）</p>
              <div className="mt-2 flex items-center gap-2">
                <code className="mono min-w-0 flex-1 break-all text-[11px] text-txt-1">{showNew}</code>
                <button className="btn-outline px-2 py-1 text-[11px]" onClick={() => copy(showNew)}>复制</button>
              </div>
            </div>
          )}
          <div className="mt-5 panel-2 p-3">
            <p className="label">调用示例</p>
            <pre className="mono whitespace-pre-wrap text-[11px] leading-relaxed text-txt-2">{`POST {base}/v1/videos/generations
Authorization: Bearer sk-...
{"model":"filmora-t2v","prompt":"...","duration":5}`}</pre>
          </div>
        </div>

        <div className="panel overflow-hidden">
          {keys.length === 0 ? <Empty title="暂无密钥" hint="创建密钥以启用 OpenAI 兼容 API" icon="⌘" /> : (
            <table className="w-full text-left">
              <thead className="border-b border-line/70 text-[11px] uppercase tracking-wider text-txt-3">
                <tr><th className="cell">密钥</th><th className="cell">名称</th><th className="cell">状态</th><th className="cell">操作</th></tr>
              </thead>
              <tbody className="divide-y divide-line/50">
                {keys.map(k => (
                  <tr key={k.key}>
                    <td className="cell"><code className="mono text-[11px] text-txt-1">{k.key.slice(0, 18)}…{k.key.slice(-6)}</code></td>
                    <td className="cell">{k.name}</td>
                    <td className="cell"><span className="chip border-mint/40 text-mint">● 启用</span></td>
                    <td className="cell">
                      <div className="flex gap-2">
                        <button className="btn-ghost px-2 py-1 text-[11px]" onClick={() => copy(k.key)}>复制</button>
                        <button className="btn-danger px-2 py-1 text-[11px]" onClick={() => del(k.key)}>撤销</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
