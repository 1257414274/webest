import { createOpencodeClient } from "@opencode-ai/sdk/v2/client"

const action = process.argv[2] || ""

function nowMs() {
  return Date.now()
}

async function readStdinJson() {
  const chunks = []
  for await (const chunk of process.stdin) {
    chunks.push(chunk)
  }
  const text = chunks.join("").trim()
  if (!text) return {}
  return JSON.parse(text)
}

function toSessionID(value) {
  if (!value) return ""
  return String(value)
}

function unwrapData(result) {
  if (result && typeof result === "object" && "data" in result) {
    return result.data
  }
  return result
}

function buildPromptText(prompt, context) {
  if (!context) return prompt || ""
  return `上下文:\n${context}\n\n任务:\n${prompt || ""}`
}

function eventSessionID(event) {
  const props = event?.properties || {}
  return toSessionID(
    props.sessionID ||
      props.sessionId ||
      props.session_id ||
      event?.sessionID ||
      event?.sessionId ||
      event?.session_id
  )
}

function resolveSessionId(session) {
  const data = unwrapData(session) || {}
  return toSessionID(data.id || data.sessionID || data.sessionId)
}

function collectText(value) {
  const out = []
  const visit = (v) => {
    if (!v) return
    if (typeof v === "string") {
      out.push(v)
      return
    }
    if (Array.isArray(v)) {
      for (const item of v) visit(item)
      return
    }
    if (typeof v === "object") {
      if (typeof v.text === "string") out.push(v.text)
      if (typeof v.content === "string") out.push(v.content)
      if (typeof v.reasoning === "string") out.push(v.reasoning)
      for (const key of Object.keys(v)) visit(v[key])
    }
  }
  visit(value)
  return out.join(" ").trim()
}

function pickText(value) {
  if (!value) return ""
  if (typeof value === "string") return value
  if (typeof value === "object") {
    if (typeof value.text === "string") return value.text
    if (typeof value.content === "string") return value.content
    if (typeof value.delta === "string") return value.delta
  }
  return ""
}

function writeEventLine(event) {
  process.stdout.write(`${JSON.stringify(event)}\n`)
}

async function createClient(baseUrl) {
  return createOpencodeClient({
    baseUrl,
    throwOnError: true,
    responseStyle: "data",
  })
}

async function setProviderAuth(client, providerId, apiKey) {
  if (!apiKey) return
  const id = providerId || "anthropic"
  try {
    await client.auth.set({
      path: { id },
      body: { type: "api", key: apiKey },
    })
  } catch (_e) {
    // 忽略认证写入失败，避免阻断已有服务器配置
  }
}

async function ensureSession(client, payload) {
  const existingId = toSessionID(payload.sessionId)
  if (existingId) return existingId
  const session = await client.session.create({
    title: payload.taskName || "OpenCode会话",
  })
  const sessionId = resolveSessionId(session)
  if (!sessionId) throw new Error("OpenCode SDK 未返回 session_id")
  return sessionId
}

async function actionHealth(payload) {
  const t0 = nowMs()
  const client = await createClient(payload.baseUrl)
  await setProviderAuth(client, payload.providerId, payload.apiKey)
  try {
    const data = unwrapData(await client.global.health())
    return { latency_ms: nowMs() - t0, response: data }
  } catch (_e) {
    const fallback = unwrapData(await client.session.list({ limit: 1, roots: true }))
    return { latency_ms: nowMs() - t0, response: { status: "ok", fallback: "session.list", data: fallback } }
  }
}

async function actionExecute(payload) {
  const t0 = nowMs()
  const client = await createClient(payload.baseUrl)
  await setProviderAuth(client, payload.providerId, payload.apiKey)
  const sessionId = await ensureSession(client, payload)
  const response = unwrapData(
    await client.session.prompt({
      sessionID: sessionId,
      model: { providerID: payload.providerId || "anthropic", modelID: payload.model || "glm-5-turbo" },
      parts: [{ type: "text", text: buildPromptText(payload.prompt, payload.context) }],
    })
  )
  return {
    latency_ms: nowMs() - t0,
    session_id: sessionId,
    text: collectText(response),
    response,
  }
}

async function actionSessionList(payload) {
  const t0 = nowMs()
  const client = await createClient(payload.baseUrl)
  await setProviderAuth(client, payload.providerId, payload.apiKey)
  const response = unwrapData(
    await client.session.list({
      limit: Number(payload.limit || 50),
      roots: true,
      search: payload.search || undefined,
    })
  )
  return { latency_ms: nowMs() - t0, response }
}

async function actionSessionMessages(payload) {
  const t0 = nowMs()
  const client = await createClient(payload.baseUrl)
  await setProviderAuth(client, payload.providerId, payload.apiKey)
  const sessionId = toSessionID(payload.sessionId)
  if (!sessionId) throw new Error("sessionId is required")
  const response = unwrapData(
    await client.session.messages({
      sessionID: sessionId,
      limit: Number(payload.limit || 100),
    })
  )
  return { latency_ms: nowMs() - t0, session_id: sessionId, response }
}

async function actionCreateSession(payload) {
  const t0 = nowMs()
  const client = await createClient(payload.baseUrl)
  await setProviderAuth(client, payload.providerId, payload.apiKey)
  const response = unwrapData(
    await client.session.create({
      title: payload.title || "OpenCode会话",
    })
  )
  return {
    latency_ms: nowMs() - t0,
    session_id: resolveSessionId(response),
    response,
  }
}

async function actionDeleteSession(payload) {
  const t0 = nowMs()
  const client = await createClient(payload.baseUrl)
  await setProviderAuth(client, payload.providerId, payload.apiKey)
  const sessionId = toSessionID(payload.sessionId)
  if (!sessionId) throw new Error("sessionId is required")
  const deleted = unwrapData(await client.session.delete({ sessionID: sessionId }))
  return {
    latency_ms: nowMs() - t0,
    response: { deleted: !!deleted, session_id: sessionId },
  }
}

async function actionRenameSession(payload) {
  const t0 = nowMs()
  const client = await createClient(payload.baseUrl)
  await setProviderAuth(client, payload.providerId, payload.apiKey)
  const sessionId = toSessionID(payload.sessionId)
  if (!sessionId) throw new Error("sessionId is required")
  const response = unwrapData(
    await client.session.update({
      sessionID: sessionId,
      title: payload.title || "OpenCode会话",
    })
  )
  return { latency_ms: nowMs() - t0, response }
}

async function actionStream(payload) {
  const client = await createClient(payload.baseUrl)
  await setProviderAuth(client, payload.providerId, payload.apiKey)
  const sessionId = await ensureSession(client, payload)

  writeEventLine({ event: "meta", session_id: sessionId })
  const events = await client.event.subscribe()
  const promptPromise = client.session.prompt({
    sessionID: sessionId,
    model: { providerID: payload.providerId || "anthropic", modelID: payload.model || "glm-5-turbo" },
    parts: [{ type: "text", text: buildPromptText(payload.prompt, payload.context) }],
  })

  try {
    for await (const event of events.stream) {
      if (eventSessionID(event) !== sessionId) continue
      const type = String(event?.type || "")
      const props = event?.properties || {}

      if (type === "message.part.updated") {
        const part = props.part || {}
        const text = pickText(props.delta) || pickText(part) || collectText(props.delta) || collectText(part)
        if (!text) continue
        const partType = String(part.type || "")
        if (partType === "reasoning" || partType === "thinking") {
          writeEventLine({ event: "thinking", text })
        } else {
          writeEventLine({ event: "delta", text })
        }
      } else if (type === "session.error") {
        writeEventLine({ event: "error", message: collectText(props.error) || "OpenCode session error" })
        break
      } else if (type === "session.idle") {
        writeEventLine({ event: "done", session_id: sessionId })
        break
      }
    }
    await promptPromise
  } catch (error) {
    writeEventLine({ event: "error", message: error?.message || String(error) })
    throw error
  }
}

async function actionCancel(payload) {
  const t0 = nowMs()
  const client = await createClient(payload.baseUrl)
  await setProviderAuth(client, payload.providerId, payload.apiKey)
  const sessionId = toSessionID(payload.sessionId)
  if (!sessionId) throw new Error("sessionId is required")
  let ok = false
  try {
    ok = unwrapData(await client.session.abort({ sessionID: sessionId }))
  } catch (_e) {
    ok = false
  }
  return {
    latency_ms: nowMs() - t0,
    response: { cancelled: !!ok, session_id: sessionId },
  }
}

async function main() {
  const payload = await readStdinJson()
  let result
  if (action === "health") {
    result = await actionHealth(payload)
  } else if (action === "execute") {
    result = await actionExecute(payload)
  } else if (action === "session_list") {
    result = await actionSessionList(payload)
  } else if (action === "session_messages") {
    result = await actionSessionMessages(payload)
  } else if (action === "create_session") {
    result = await actionCreateSession(payload)
  } else if (action === "delete_session") {
    result = await actionDeleteSession(payload)
  } else if (action === "rename_session") {
    result = await actionRenameSession(payload)
  } else if (action === "cancel") {
    result = await actionCancel(payload)
  } else if (action === "stream") {
    await actionStream(payload)
    return
  } else {
    throw new Error(`Unsupported action: ${action}`)
  }
  process.stdout.write(JSON.stringify(result))
}

main().catch((err) => {
  process.stderr.write(err?.stack || String(err))
  process.exit(1)
})
