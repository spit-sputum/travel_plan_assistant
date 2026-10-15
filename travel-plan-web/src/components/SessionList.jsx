/** 时间显示：今天只显示 HH:MM，否则显示 M/D */
function formatTime(iso) {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  const now = new Date()
  const hh = String(date.getHours()).padStart(2, '0')
  const mm = String(date.getMinutes()).padStart(2, '0')
  if (date.toDateString() === now.toDateString()) return `${hh}:${mm}`
  return `${date.getMonth() + 1}/${date.getDate()}`
}

export default function SessionList({ sessions, activeId, busy, onOpen, onDelete }) {
  if (!sessions.length) {
    return <p className="session-list__empty">暂无历史会话</p>
  }

  return (
    <div className="session-list">
      {sessions.map((session) => {
        const active = session.conversationId === activeId
        return (
          <div
            key={session.conversationId}
            className={`session${active ? ' session--active' : ''}`}
            onClick={() => !busy && onOpen(session.conversationId)}
            title={session.conversationId}
          >
            <div className="session__body">
              <div className="session__preview">{session.preview || '（空会话）'}</div>
              <div className="session__meta">
                {formatTime(session.lastActive)} · {session.count} 条
              </div>
            </div>
            <button
              className="session__delete"
              title="删除该会话"
              onClick={(event) => {
                event.stopPropagation()
                if (!busy) onDelete(session.conversationId)
              }}
            >
              ×
            </button>
          </div>
        )
      })}
    </div>
  )
}
