import { buildBoard } from '../core/game.js'
import { Engine } from './search.js'
import { levelParams } from './levels.js'
import { analyzeGame, summarize } from './analysis.js'

const engine = new Engine()
let analysisToken = 0

function think(msg) {
    const board = buildBoard(msg.setup)
    const color = msg.color
    const params = { ...levelParams(msg.level), ...(msg.override || {}) }
    const r = engine.search(board, color, params)
    return {
        type: 'move',
        id: msg.id,
        kind: msg.kind,
        x: r.move >= 0 ? board.xOf(r.move) : -1,
        y: r.move >= 0 ? board.yOf(r.move) : -1,
        score: r.score,
        depth: r.depth,
        nodes: r.nodes,
        time: r.time,
        proven: !!r.proven
    }
}

function analyze(msg) {
    const token = ++analysisToken
    const results = analyzeGame(
        engine,
        msg.setup,
        { depth: msg.depth, time: msg.time, cancelled: () => token !== analysisToken },
        (done, total) => self.postMessage({ type: 'progress', id: msg.id, done, total })
    )
    return { type: 'analysis', id: msg.id, results, summary: summarize(results), size: msg.setup.size }
}

self.onmessage = (e) => {
    const msg = e.data
    if (msg.type === 'think') self.postMessage(think(msg))
    else if (msg.type === 'analyze') self.postMessage(analyze(msg))
}
