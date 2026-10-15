/**
 * 后端接口封装。
 *
 * 后端统一返回信封 { code, success, message, data }，这里统一解包 data，失败直接抛错。
 * 所有路径都走 Vite 代理的 /api，无需关心后端地址与跨域。
 */

const BASE = '/api/v1'

/** 通用请求：解包信封 */
export async function request(path, { method = 'GET', body } = {}) {
  const res = await fetch(BASE + path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`)
  const json = await res.json()
  if (json.success === false) throw new Error(json.message || '请求失败')
  return json.data
}

/** 健康检查 */
export const getHealth = () => request('/health')

/** 非流式对话 */
export const sendMessage = (payload) =>
  request('/chat/message', { method: 'POST', body: payload })

/** 会话列表 */
export const listSessions = (limit = 20) => request(`/chat/sessions?limit=${limit}`)

/** 某会话的历史消息 */
export const getHistory = (conversationId, limit = 100) =>
  request(
    `/chat/history?conversationId=${encodeURIComponent(conversationId)}&limit=${limit}`,
  )

/** 删除会话 */
export const deleteSession = (conversationId) =>
  request(`/chat/session/${encodeURIComponent(conversationId)}`, { method: 'DELETE' })

/**
 * SSE 流式对话。
 *
 * 因为浏览器原生 EventSource 不支持 POST，这里用 fetch + ReadableStream 手工解析 SSE。
 * 事件：start / tool_call / tool_result / token / done / error
 *
 * @param {object} payload   { message, conversationId, userId }
 * @param {(event: string, data: any) => void} onEvent 每收到一个事件回调一次
 * @param {AbortSignal} [signal] 用于中断生成
 */
export async function streamChat(payload, onEvent, signal) {
  const res = await fetch(BASE + '/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  })
  if (!res.ok || !res.body) throw new Error(`HTTP ${res.status} ${res.statusText}`)

  const reader = res.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    // SSE 以"空行"分隔事件块（兼容 \n 与 \r\n）
    const blocks = buffer.split(/\r?\n\r?\n/)
    buffer = blocks.pop() ?? ''

    for (const block of blocks) {
      let eventName = 'message'
      const dataLines = []
      for (const line of block.split(/\r?\n/)) {
        if (line.startsWith('event:')) eventName = line.slice('event:'.length).trim()
        else if (line.startsWith('data:')) dataLines.push(line.slice('data:'.length).trim())
      }
      if (!dataLines.length) continue
      let data = null
      try {
        data = JSON.parse(dataLines.join('\n'))
      } catch {
        data = null
      }
      onEvent(eventName, data)
    }
  }
}
