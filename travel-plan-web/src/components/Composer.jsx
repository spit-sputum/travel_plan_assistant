import { useState } from 'react'

export default function Composer({ busy, onSend, onStop }) {
  const [value, setValue] = useState('')

  const submit = () => {
    const text = value.trim()
    if (!text || busy) return
    setValue('')
    onSend(text)
  }

  const handleKeyDown = (event) => {
    // 回车发送；Shift+Enter 换行；中文输入法组词时不触发
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <div className="composer">
      <textarea
        className="composer__input"
        rows={2}
        placeholder="说说你的旅行计划，例如：帮我规划北京三日游，2 人，预算 5000（Enter 发送，Shift+Enter 换行）"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
      />
      {busy ? (
        <button className="btn btn--stop" onClick={onStop}>
          停止生成
        </button>
      ) : (
        <button className="btn" onClick={submit} disabled={!value.trim()}>
          发送
        </button>
      )}
    </div>
  )
}
