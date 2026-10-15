import { useEffect, useRef } from 'react'

import ToolTimeline from './ToolTimeline.jsx'

const EXAMPLES = [
  '帮我规划北京三日游，2 人，预算 5000',
  '我下周去成都，想吃辣、看熊猫，怎么安排？',
  '上海周末两天，带老人，行程别太赶',
]

function EmptyState({ onPick }) {
  return (
    <div className="empty">
      <h2 className="empty__title">告诉我你的旅行计划</h2>
      <p className="empty__desc">
        我会先回忆你的偏好，再查攻略、算交通、找餐厅和酒店，最后整合成一份可执行的行程。
      </p>
      <div className="empty__examples">
        {EXAMPLES.map((text) => (
          <button key={text} className="chip" onClick={() => onPick(text)}>
            {text}
          </button>
        ))}
      </div>
    </div>
  )
}

export default function MessageList({ messages, onPickExample }) {
  const bottomRef = useRef(null)

  // 有新内容时自动滚到底部
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages])

  if (!messages.length) return <EmptyState onPick={onPickExample} />

  return (
    <div className="messages">
      {messages.map((msg) => (
        <div key={msg.id} className={`msg msg--${msg.role}`}>
          <div className="msg__avatar">{msg.role === 'user' ? '我' : 'AI'}</div>
          <div className="msg__body">
            {msg.role === 'assistant' && msg.tools?.length > 0 && (
              <ToolTimeline tools={msg.tools} />
            )}
            {(msg.content || msg.streaming) && (
              <div className="msg__text">
                {msg.content}
                {msg.streaming && <span className="caret" />}
              </div>
            )}
            {msg.interrupted && <div className="msg__flag">已停止生成</div>}
          </div>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
