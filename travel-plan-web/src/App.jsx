import { useCallback, useEffect, useRef, useState } from 'react'

import {
  deleteSession,
  getHealth,
  getHistory,
  listSessions,
  streamChat,
} from './api/client.js'
import Composer from './components/Composer.jsx'
import MessageList from './components/MessageList.jsx'
import SessionList from './components/SessionList.jsx'

const USER_ID = 'web_user'

/** 更新最后一条助手消息 */
function patchLastAssistant(list, updater) {
  if (!list.length) return list
  const index = list.length - 1
  if (list[index].role !== 'assistant') return list
  const next = [...list]
  next[index] = updater(next[index])
  return next
}

/** 把同名且仍在"查询中"的工具标记为完成，并附上返回摘要 */
function markToolDone(tools, name, preview) {
  const next = [...tools]
  for (let i = next.length - 1; i >= 0; i -= 1) {
    if (next[i].name === name && next[i].status === 'running') {
      next[i] = { ...next[i], preview: preview || '', status: 'done' }
      break
    }
  }
  return next
}

/** 后端历史记录 → 界面消息（只回放真实对话，过滤 Agent 自己写的记忆总结） */
function toMessages(records) {
  const list = records || []
  // 兼容：若接口未返回 metadata（后端未重启），直接全部显示，避免历史看起来是空的
  const withSource = list.some((r) => r.metadata && 'source' in r.metadata)
  const usable = withSource ? list.filter((r) => r.metadata?.source === 'api') : list
  return usable.map((r) => ({
    id: r.id,
    role: r.role === 'user' ? 'user' : 'assistant',
    content: r.content,
    tools: [],
    streaming: false,
    interrupted: Boolean(r.metadata?.interrupted),
  }))
}

export default function App() {
  const [messages, setMessages] = useState([])
  const [conversationId, setConversationId] = useState(null)
  const [sessions, setSessions] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [health, setHealth] = useState(null)

  const aborterRef = useRef(null)
  const bufferRef = useRef('') // 打字机缓冲，避免每个字符都触发一次渲染
  const rafRef = useRef(null)

  const loadSessions = useCallback(async () => {
    try {
      const data = await listSessions(20)
      setSessions(data || [])
    } catch {
      // 会话列表拉取失败不影响主流程
    }
  }, [])

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth(null))
    loadSessions()
  }, [loadSessions])

  /** 把缓冲的文本按帧刷进界面（最多约 60fps） */
  const flushBuffer = useCallback(() => {
    if (rafRef.current) return
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = null
      const buffered = bufferRef.current
      if (!buffered) return
      bufferRef.current = ''
      setMessages((prev) =>
        patchLastAssistant(prev, (m) => ({ ...m, content: m.content + buffered })),
      )
    })
  }, [])

  const handleSend = async (text) => {
    if (busy) return
    setError('')
    setBusy(true)
    bufferRef.current = ''

    setMessages((prev) => [
      ...prev,
      { id: `u-${Date.now()}`, role: 'user', content: text },
      {
        id: `a-${Date.now()}`,
        role: 'assistant',
        content: '',
        tools: [],
        streaming: true,
      },
    ])

    const controller = new AbortController()
    aborterRef.current = controller

    try {
      await streamChat(
        { message: text, conversationId, userId: USER_ID },
        (event, data) => {
          switch (event) {
            case 'start':
              if (data?.conversationId) setConversationId(data.conversationId)
              break
            case 'token':
              if (data?.content) {
                bufferRef.current += data.content
                flushBuffer()
              }
              break
            case 'tool_call':
              setMessages((prev) =>
                patchLastAssistant(prev, (m) => ({
                  ...m,
                  tools: [
                    ...m.tools,
                    {
                      key: `${data?.name}-${Date.now()}-${Math.random()}`,
                      name: data?.name || '',
                      args: data?.args || {},
                      preview: '',
                      status: 'running',
                    },
                  ],
                })),
              )
              break
            case 'tool_result':
              setMessages((prev) =>
                patchLastAssistant(prev, (m) => ({
                  ...m,
                  tools: markToolDone(m.tools, data?.name, data?.preview),
                })),
              )
              break
            case 'error':
              setError(data?.error || '生成过程出错')
              break
            default:
              break
          }
        },
        controller.signal,
      )
    } catch (err) {
      if (err?.name !== 'AbortError') setError(err?.message || '请求失败')
    } finally {
      // 收尾：刷入剩余缓冲、结束生成态、刷新会话列表
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current)
        rafRef.current = null
      }
      const rest = bufferRef.current
      bufferRef.current = ''
      setMessages((prev) =>
        patchLastAssistant(prev, (m) => ({
          ...m,
          content: m.content + rest,
          streaming: false,
        })),
      )
      setBusy(false)
      aborterRef.current = null
      loadSessions()
    }
  }

  const handleStop = () => {
    aborterRef.current?.abort()
    // 立刻在界面上标记"已中断"，不必等请求真正返回
    setMessages((prev) =>
      patchLastAssistant(prev, (m) => ({
        ...m,
        streaming: false,
        interrupted: true,
      })),
    )
  }

  const handleNewChat = () => {
    if (busy) return
    setMessages([])
    setConversationId(null)
    setError('')
  }

  /** 打开某个历史会话：拉取历史消息并回放 */
  const handleOpenSession = async (id) => {
    if (busy || id === conversationId) return
    setError('')
    try {
      const data = await getHistory(id, 200)
      setMessages(toMessages(data?.messages))
      setConversationId(id)
    } catch (err) {
      setError(err?.message || '加载历史失败')
    }
  }

  /** 删除会话 */
  const handleDeleteSession = async (id) => {
    if (busy) return
    if (!window.confirm('确定删除该会话吗？删除后无法恢复。')) return
    try {
      await deleteSession(id)
      if (id === conversationId) {
        setMessages([])
        setConversationId(null)
      }
      await loadSessions()
    } catch (err) {
      setError(err?.message || '删除失败')
    }
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar__brand">AI 旅行规划</div>

        <button className="btn btn--ghost" onClick={handleNewChat} disabled={busy}>
          + 新对话
        </button>

        <div className="sidebar__section">
          <div className="sidebar__section-title">历史会话</div>
          <SessionList
            sessions={sessions}
            activeId={conversationId}
            busy={busy}
            onOpen={handleOpenSession}
            onDelete={handleDeleteSession}
          />
        </div>

        <div className="sidebar__foot">
          <span className={`dot${health ? ' dot--ok' : ' dot--off'}`} />
          {health ? `${health.model} · ${health.tools} 工具` : '后端未连接'}
        </div>
      </aside>

      <main className="main">
        <header className="main__header">
          <h1>旅行规划助手</h1>
          {conversationId && (
            <span className="main__conv" title={conversationId}>
              {conversationId}
            </span>
          )}
          {error && <span className="main__error">{error}</span>}
        </header>

        <MessageList messages={messages} onPickExample={handleSend} />
        <Composer busy={busy} onSend={handleSend} onStop={handleStop} />
      </main>
    </div>
  )
}
