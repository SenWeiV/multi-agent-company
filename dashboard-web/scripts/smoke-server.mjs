import http from "node:http"
import { readFile } from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const distDir = path.resolve(__dirname, "../../app/ui/dist")
const port = 4173

const mimeTypes = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
}

function contentType(filePath) {
  return mimeTypes[path.extname(filePath)] || "application/octet-stream"
}

async function sendFile(response, filePath) {
  const data = await readFile(filePath)
  response.writeHead(200, { "Content-Type": contentType(filePath) })
  response.end(data)
}

const server = http.createServer(async (request, response) => {
  const url = new URL(request.url || "/", `http://${request.headers.host || "127.0.0.1"}`)
  const pathname = decodeURIComponent(url.pathname)

  try {
    if (pathname === "/") {
      response.writeHead(307, { Location: "/dashboard" })
      response.end()
      return
    }

    if (pathname === "/dashboard" || pathname.startsWith("/dashboard/")) {
      await sendFile(response, path.join(distDir, "index.html"))
      return
    }

    if (pathname.startsWith("/dashboard-static/")) {
      const relativePath = pathname.replace("/dashboard-static/", "")
      await sendFile(response, path.join(distDir, relativePath))
      return
    }

    if (pathname === "/openclaw-control-ui/launch") {
      response.writeHead(307, { Location: "http://127.0.0.1:18789/#token=dev-openclaw-token" })
      response.end()
      return
    }

    response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" })
    response.end("Not Found")
  } catch {
    response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" })
    response.end("Not Found")
  }
})

server.listen(port, "127.0.0.1", () => {
  process.stdout.write(`Smoke server listening on http://127.0.0.1:${port}\n`)
})
