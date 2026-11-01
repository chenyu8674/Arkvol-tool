import { Game, MIN_SIZE, MAX_SIZE, coordName } from '../core/game.js'
import { BLACK, WHITE } from '../core/board.js'
import { LEVELS } from '../ai/levels.js'
import { winProb } from '../ai/analysis.js'

const $ = (id) => document.getElementById(id)
const canvas = $('board')
const ctx = canvas.getContext('2d')

const state = {
    game: null,
    human: BLACK,
    level: 4,
    thinking: false,
    requestId: 0,
    worker: null,
    hover: null,
    hint: null,
    forbiddenList: [],
    viewIndex: null,
    overlay: null,
    analysis: null,
    analyzing: false
}

function fillSelect(el, items, selected) {
    el.innerHTML = ''
    for (const [value, label] of items) {
        const option = document.createElement('option')
        option.value = value
        option.textContent = label
        if (String(value) === String(selected)) option.selected = true
        el.appendChild(option)
    }
}

function initControls() {
    const sizes = []
    for (let s = MIN_SIZE; s <= MAX_SIZE; s++) sizes.push([s, `${s} × ${s}`])
    fillSelect($('size'), sizes, 15)
    fillSelect($('level'), LEVELS.map(l => [l.id, `${l.id} · ${l.name}`]), state.level)
    const handicaps = [[0, '不让子']]
    for (let i = 1; i <= 9; i++) handicaps.push([i, `让 ${i} 子（黑棋开局 ${i} 子，白先）`])
    fillSelect($('handicap'), handicaps, 0)
}

function createWorker() {
    if (state.worker) state.worker.terminate()
    state.worker = new Worker(new URL('../ai/worker.js', import.meta.url), { type: 'module' })
    state.worker.onmessage = onWorkerMessage
    state.worker.onerror = (e) => {
        state.thinking = false
        state.analyzing = false
        setStatus(`AI 出错：${e.message}`)
    }
}

function cancelWorker() {
    state.requestId++
    state.thinking = false
    state.analyzing = false
    $('progress').hidden = true
    createWorker()
}

function startGame() {
    cancelWorker()
    const size = Number($('size').value)
    state.human = Number($('color').value)
    state.level = Number($('level').value)
    state.game = new Game({
        size,
        forbidden: $('forbidden').checked,
        handicap: Number($('handicap').value)
    })
    state.hint = null
    state.viewIndex = null
    state.overlay = null
    state.analysis = null
    $('report').hidden = true
    $('aiInfo').textContent = ''
    refresh()
    maybeAiMove()
}

function setStatus(text) {
    $('status').textContent = text
}

function colorName(c) {
    return c === BLACK ? '黑棋' : '白棋'
}

function refresh() {
    const game = state.game
    state.forbiddenList = []
    if ($('showForbidden').checked && game.forbidden && game.turn === BLACK && !game.over && game.turn === state.human) {
        state.forbiddenList = game.forbiddenList()
    }
    if (game.winner) {
        const who = game.winner === state.human ? '你赢了' : 'AI 获胜'
        setStatus(`${colorName(game.winner)}获胜 · ${who}`)
    } else if (game.draw) {
        setStatus('平局')
    } else if (state.thinking) {
        setStatus(`AI（${colorName(game.turn)}）思考中…`)
    } else if (game.turn === state.human) {
        setStatus(`轮到你（${colorName(game.turn)}）`)
    } else {
        setStatus(`轮到 AI（${colorName(game.turn)}）`)
    }
    $('undo').disabled = game.moves.length === 0
    $('analyze').disabled = game.moves.length < 2 || state.analyzing
    $('hint').disabled = game.over || game.turn !== state.human || state.thinking
    draw()
}

function maybeAiMove() {
    const game = state.game
    if (game.over || game.turn === state.human || state.thinking) return
    state.thinking = true
    const id = ++state.requestId
    state.worker.postMessage({ type: 'think', id, setup: game.setup(), color: game.turn, level: state.level })
    refresh()
}

function onWorkerMessage(e) {
    const msg = e.data
    if (msg.id !== state.requestId) return
    if (msg.type === 'move') onMove(msg)
    else if (msg.type === 'progress') onProgress(msg)
    else if (msg.type === 'analysis') onAnalysis(msg)
}

function onMove(msg) {
    const game = state.game
    state.thinking = false
    if (msg.kind === 'hint') {
        state.hint = [msg.x, msg.y]
        refresh()
        return
    }
    if (msg.x < 0) {
        setStatus('AI 无子可下')
        return
    }
    const res = game.play(msg.x, msg.y)
    if (!res.ok) {
        setStatus(`AI 给出了非法着法（${res.reason}）`)
        return
    }
    const rate = Math.round(winProb(msg.score) * 100)
    $('aiInfo').textContent =
        `AI 落子 ${coordName(game.size, msg.x, msg.y)} · 搜索深度 ${msg.depth} · ` +
        `${msg.nodes.toLocaleString()} 节点 · ${(msg.time / 1000).toFixed(2)}s · AI 胜率估计 ${rate}%` +
        (msg.proven ? ' · 已找到必胜' : '')
    state.viewIndex = null
    state.overlay = null
    refresh()
}

function requestHint() {
    const game = state.game
    if (game.over || game.turn !== state.human || state.thinking) return
    state.thinking = true
    const id = ++state.requestId
    state.worker.postMessage({ type: 'think', id, kind: 'hint', setup: game.setup(), color: game.turn, level: 5, override: { time: 1500 } })
    refresh()
}

function undo() {
    const game = state.game
    if (!game.moves.length) return
    cancelWorker()
    do {
        game.undo()
    } while (game.moves.length && game.turn !== state.human)
    state.hint = null
    state.viewIndex = null
    state.overlay = null
    refresh()
    maybeAiMove()
}

function onCanvasClick(e) {
    const game = state.game
    if (state.viewIndex !== null) {
        state.viewIndex = null
        state.overlay = null
        refresh()
        return
    }
    if (game.over || state.thinking || game.turn !== state.human) return
    const cell = cellAt(e)
    if (!cell) return
    const res = game.play(cell[0], cell[1])
    if (!res.ok) {
        if (res.reason === 'forbidden') setStatus('禁手点，黑棋不能落子')
        return
    }
    state.hint = null
    refresh()
    maybeAiMove()
}

function cellAt(e) {
    const rect = canvas.getBoundingClientRect()
    const size = state.game.size
    const unit = rect.width / (size + 1)
    const x = Math.round((e.clientX - rect.left) / unit - 1)
    const y = Math.round((e.clientY - rect.top) / unit - 1)
    if (x < 0 || y < 0 || x >= size || y >= size) return null
    return [x, y]
}

function onCanvasMove(e) {
    state.hover = cellAt(e)
    draw()
}

function starPoints(size) {
    const edge = size >= 13 ? 3 : 2
    const mid = size >> 1
    const set = new Set([edge, mid, size - 1 - edge])
    const pts = []
    for (const x of set) for (const y of set) pts.push([x, y])
    return pts
}

function visibleStones() {
    const game = state.game
    const limit = state.viewIndex === null ? game.moves.length : state.viewIndex
    const stones = game.preset.map(([x, y, c]) => ({ x, y, c, n: 0 }))
    for (let i = 0; i < limit; i++) {
        stones.push({ x: game.moves[i][0], y: game.moves[i][1], c: game.colorOfMove(i), n: i + 1 })
    }
    return stones
}

function draw() {
    const game = state.game
    if (!game) return
    const dpr = window.devicePixelRatio || 1
    const rect = canvas.getBoundingClientRect()
    const px = Math.max(200, Math.round(rect.width * dpr))
    if (canvas.width !== px) {
        canvas.width = px
        canvas.height = px
    }
    const size = game.size
    const unit = px / (size + 1)
    const pos = (v) => (v + 1) * unit

    ctx.clearRect(0, 0, px, px)
    ctx.fillStyle = '#dcb166'
    ctx.fillRect(0, 0, px, px)

    ctx.strokeStyle = '#5a4524'
    ctx.lineWidth = Math.max(1, unit * 0.04)
    ctx.beginPath()
    for (let i = 0; i < size; i++) {
        ctx.moveTo(pos(0), pos(i))
        ctx.lineTo(pos(size - 1), pos(i))
        ctx.moveTo(pos(i), pos(0))
        ctx.lineTo(pos(i), pos(size - 1))
    }
    ctx.stroke()

    ctx.fillStyle = '#5a4524'
    for (const [x, y] of starPoints(size)) {
        ctx.beginPath()
        ctx.arc(pos(x), pos(y), unit * 0.09, 0, Math.PI * 2)
        ctx.fill()
    }

    ctx.fillStyle = '#6b5530'
    ctx.font = `${Math.round(unit * 0.32)}px sans-serif`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    for (let i = 0; i < size; i++) {
        const letter = String.fromCharCode(65 + i)
        ctx.fillText(letter, pos(i), unit * 0.4)
        ctx.fillText(letter, pos(i), px - unit * 0.4)
        ctx.fillText(String(size - i), unit * 0.4, pos(i))
        ctx.fillText(String(size - i), px - unit * 0.4, pos(i))
    }

    const stones = visibleStones()
    for (const s of stones) drawStone(pos(s.x), pos(s.y), unit * 0.46, s.c, 1)

    if (state.viewIndex === null && game.moves.length) {
        const [lx, ly] = game.moves[game.moves.length - 1]
        const last = stones[stones.length - 1]
        ctx.fillStyle = last.c === BLACK ? '#ffffff' : '#d33'
        ctx.beginPath()
        ctx.arc(pos(lx), pos(ly), unit * 0.1, 0, Math.PI * 2)
        ctx.fill()
    }

    if (state.viewIndex === null && game.winLine) {
        ctx.strokeStyle = '#e5534b'
        ctx.lineWidth = unit * 0.1
        ctx.beginPath()
        game.winLine.forEach(([x, y], i) => (i ? ctx.lineTo(pos(x), pos(y)) : ctx.moveTo(pos(x), pos(y))))
        ctx.stroke()
    }

    ctx.strokeStyle = '#d02020'
    ctx.lineWidth = unit * 0.08
    for (const [x, y] of state.forbiddenList) {
        const r = unit * 0.2
        ctx.beginPath()
        ctx.moveTo(pos(x) - r, pos(y) - r)
        ctx.lineTo(pos(x) + r, pos(y) + r)
        ctx.moveTo(pos(x) + r, pos(y) - r)
        ctx.lineTo(pos(x) - r, pos(y) + r)
        ctx.stroke()
    }

    if (state.hint) ring(pos(state.hint[0]), pos(state.hint[1]), unit * 0.4, '#2fb36b', unit * 0.08)
    if (state.overlay) {
        ring(pos(state.overlay.best[0]), pos(state.overlay.best[1]), unit * 0.42, '#2fb36b', unit * 0.09)
        ring(pos(state.overlay.played[0]), pos(state.overlay.played[1]), unit * 0.42, '#e5534b', unit * 0.09)
    }

    const h = state.hover
    if (h && state.viewIndex === null && !game.over && !state.thinking && game.turn === state.human
        && game.board.get(h[0], h[1]) === 0 && !state.forbiddenList.some(([x, y]) => x === h[0] && y === h[1])) {
        drawStone(pos(h[0]), pos(h[1]), unit * 0.46, state.human, 0.4)
    }
}

function ring(x, y, r, color, width) {
    ctx.strokeStyle = color
    ctx.lineWidth = width
    ctx.beginPath()
    ctx.arc(x, y, r, 0, Math.PI * 2)
    ctx.stroke()
}

function drawStone(x, y, r, color, alpha) {
    ctx.globalAlpha = alpha
    const g = ctx.createRadialGradient(x - r * 0.35, y - r * 0.35, r * 0.1, x, y, r)
    if (color === BLACK) {
        g.addColorStop(0, '#666')
        g.addColorStop(1, '#0a0a0a')
    } else {
        g.addColorStop(0, '#ffffff')
        g.addColorStop(1, '#c9c9c9')
    }
    ctx.fillStyle = g
    ctx.shadowColor = 'rgba(0, 0, 0, 0.4)'
    ctx.shadowBlur = r * 0.3
    ctx.shadowOffsetY = r * 0.08
    ctx.beginPath()
    ctx.arc(x, y, r, 0, Math.PI * 2)
    ctx.fill()
    ctx.shadowColor = 'transparent'
    ctx.globalAlpha = 1
}

function requestAnalysis() {
    const game = state.game
    if (game.moves.length < 2) return
    cancelWorker()
    state.analyzing = true
    const id = ++state.requestId
    $('report').hidden = false
    $('progress').hidden = false
    $('progressBar').style.width = '0'
    $('summary').textContent = '正在分析…'
    $('mistakes').innerHTML = ''
    clearCurve()
    state.worker.postMessage({ type: 'analyze', id, setup: game.setup(), depth: 6, time: 1200 })
    refresh()
}

function onProgress(msg) {
    $('progressBar').style.width = `${Math.round((msg.done / msg.total) * 100)}%`
    $('summary').textContent = `正在分析… ${msg.done} / ${msg.total}`
}

function pct(v) {
    return `${(v * 100).toFixed(1)}%`
}

function onAnalysis(msg) {
    state.analyzing = false
    state.analysis = msg
    $('progress').hidden = true
    renderReport(msg)
    refresh()
}

function renderReport(msg) {
    const game = state.game
    const rows = [BLACK, WHITE].filter(c => msg.summary[c]).map(c => {
        const s = msg.summary[c]
        const me = c === state.human ? '（你）' : '（AI）'
        return `<tr><td>${colorName(c)}${me}</td><td>${s.moves}</td><td>${pct(s.avgLoss)}</td>` +
            `<td>${s.accuracy.toFixed(0)}</td><td>${s.blunders}/${s.mistakes}/${s.inaccuracies}</td><td>${s.rating}</td></tr>`
    }).join('')
    $('summary').innerHTML =
        '<table><thead><tr><th>方</th><th>步数</th><th>均损失</th><th>准确度</th><th>大/中/小失误</th><th>估计档位</th></tr></thead>' +
        `<tbody>${rows}</tbody></table>` +
        '<div class="info">均损失 = 每步相对引擎最佳着法的平均胜率损失；档位为粗略估计。点击下方失误可查看最佳着法。</div>'
    drawCurve(msg.results)
    const list = msg.results.filter(r => r.loss >= 0.05).sort((a, b) => b.loss - a.loss).slice(0, 12)
    const ol = $('mistakes')
    ol.innerHTML = ''
    for (const r of list) {
        const li = document.createElement('li')
        li.textContent = `第 ${r.index + 1} 手 ${colorName(r.color)} ${coordName(game.size, r.x, r.y)}，` +
            `最佳 ${coordName(game.size, r.best[0], r.best[1])}，胜率损失 ${pct(r.loss)}`
        li.addEventListener('click', () => {
            state.viewIndex = r.index
            state.overlay = { best: r.best, played: [r.x, r.y] }
            draw()
        })
        ol.appendChild(li)
    }
}

const curve = $('curve')
const cctx = curve.getContext('2d')

function clearCurve() {
    cctx.clearRect(0, 0, curve.width, curve.height)
}

function drawCurve(results) {
    clearCurve()
    const w = curve.width
    const h = curve.height
    cctx.strokeStyle = '#3a414c'
    cctx.beginPath()
    cctx.moveTo(0, h / 2)
    cctx.lineTo(w, h / 2)
    cctx.stroke()
    if (!results.length) return
    cctx.strokeStyle = '#e0a84a'
    cctx.lineWidth = 2
    cctx.beginPath()
    results.forEach((r, i) => {
        const black = r.color === BLACK ? r.wpMover : 1 - r.wpMover
        const x = results.length === 1 ? 0 : (i / (results.length - 1)) * (w - 8) + 4
        const y = h - 4 - black * (h - 8)
        if (i) cctx.lineTo(x, y)
        else cctx.moveTo(x, y)
    })
    cctx.stroke()
    cctx.fillStyle = '#9aa3b0'
    cctx.font = '11px sans-serif'
    cctx.fillText('黑方胜率', 6, 14)
}

function bind() {
    $('newGame').addEventListener('click', startGame)
    $('undo').addEventListener('click', undo)
    $('hint').addEventListener('click', requestHint)
    $('analyze').addEventListener('click', requestAnalysis)
    $('showForbidden').addEventListener('change', () => state.game && refresh())
    canvas.addEventListener('click', onCanvasClick)
    canvas.addEventListener('mousemove', onCanvasMove)
    canvas.addEventListener('mouseleave', () => {
        state.hover = null
        draw()
    })
    window.addEventListener('resize', draw)
}

initControls()
bind()
createWorker()
startGame()
