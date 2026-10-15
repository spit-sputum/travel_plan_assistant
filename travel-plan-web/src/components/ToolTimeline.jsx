/** 工具名 → 中文说明，让用户看懂"正在做什么" */
const TOOL_LABELS = {
  get_guide: '检索旅游攻略',
  get_attraction: '查询景点信息',
  get_restaurant: '推荐周边餐厅',
  get_hotel: '查找酒店',
  get_traffic: '规划交通路线',
  get_weather: '查询天气',
  currency_exchange: '查询汇率',
  get_chat_memory: '读取本次会话记忆',
  get_longterm_memory: '检索长期偏好',
  save_chat_memory: '记录会话信息',
  save_longterm_memory: '记住长期偏好',
}

/** 把参数压成一行简短摘要，例如 city=北京, days=3 */
function formatArgs(args) {
  if (!args || typeof args !== 'object') return ''
  const parts = Object.entries(args)
    .slice(0, 3)
    .map(([k, v]) => `${k}=${typeof v === 'object' ? JSON.stringify(v) : v}`)
  return parts.join(', ')
}

export default function ToolTimeline({ tools }) {
  return (
    <div className="tools">
      {tools.map((tool) => (
        <div key={tool.key} className={`tool tool--${tool.status}`}>
          <span className="tool__dot" aria-hidden="true" />
          <div className="tool__main">
            <div className="tool__line">
              <span className="tool__name">{TOOL_LABELS[tool.name] || tool.name}</span>
              {formatArgs(tool.args) && (
                <span className="tool__args">{formatArgs(tool.args)}</span>
              )}
              <span className="tool__status">
                {tool.status === 'running' ? '查询中…' : '已完成'}
              </span>
            </div>
            {tool.preview && (
              <details className="tool__preview">
                <summary>查看工具返回</summary>
                <pre>{tool.preview}</pre>
              </details>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
