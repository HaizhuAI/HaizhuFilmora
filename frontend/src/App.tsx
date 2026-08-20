import { useEffect, useState } from 'react'
import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom'
import { api } from './api'
import { ToastProvider } from './components/ui'
import Login from './pages/Login'
import Shell from './components/Shell'
import Media from './pages/Media'
import Editor from './pages/Editor'
import AIStudio from './pages/AIStudio'
import Jobs from './pages/Jobs'
import Keys from './pages/Keys'

export default function App() {
  const [authed, setAuthed] = useState<boolean | null>(null)
  useEffect(() => { api.me().then(d => setAuthed(!!d.authed)).catch(() => setAuthed(false)) }, [])
  if (authed === null) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-line border-t-gold-400" />
      </div>
    )
  }
  return (
    <ToastProvider>
      <Routes>
        <Route path="/login" element={authed ? <Navigate to="/" replace /> : <Login onDone={() => setAuthed(true)} />} />
        <Route path="/" element={authed ? <Shell /> : <Navigate to="/login" replace />}>
          <Route index element={<Navigate to="/media" replace />} />
          <Route path="media" element={<Media />} />
          <Route path="editor" element={<Editor />} />
          <Route path="ai" element={<AIStudio />} />
          <Route path="jobs" element={<Jobs />} />
          <Route path="keys" element={<Keys />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ToastProvider>
  )
}
