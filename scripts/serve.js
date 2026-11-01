import http from 'node:http'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const port = Number(process.env.PORT) || 8080
const types = {
    '.html': 'text/html; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.svg': 'image/svg+xml',
    '.json': 'application/json; charset=utf-8'
}

const server = http.createServer((req, res) => {
    const url = new URL(req.url, 'http://localhost')
    let file = path.normalize(path.join(root, decodeURIComponent(url.pathname)))
    if (!file.startsWith(root)) {
        res.writeHead(403).end('forbidden')
        return
    }
    if (url.pathname.endsWith('/')) file = path.join(file, 'index.html')
    fs.readFile(file, (err, data) => {
        if (err) {
            res.writeHead(404).end('not found')
            return
        }
        res.writeHead(200, { 'Content-Type': types[path.extname(file)] || 'application/octet-stream', 'Cache-Control': 'no-cache' })
        res.end(data)
    })
})

server.listen(port, () => console.log(`http://localhost:${port}/`))
