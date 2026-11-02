import { Game } from '../src/core/game.js'
import { Engine } from '../src/ai/search.js'
import { levelParams } from '../src/ai/levels.js'
import { analyzeGame } from '../src/ai/analysis.js'

const level = Number(process.argv[2] || 3)
const games = Number(process.argv[3] || 3)
const size = 15
const engine = new Engine()
let seed = 777 + level
const rng = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0
    return seed / 4294967296
}

let totalLoss = 0
let totalMoves = 0
for (let g = 0; g < games; g++) {
    const game = new Game({ size })
    const c = size >> 1
    const used = new Set()
    while (used.size < 2) {
        const x = c + Math.floor(rng() * 5) - 2
        const y = c + Math.floor(rng() * 5) - 2
        if (used.has(x * 100 + y)) continue
        used.add(x * 100 + y)
        game.play(x, y)
    }
    const opening = game.moves.length
    while (!game.over && game.moves.length < 60) {
        const r = engine.search(game.board, game.turn, levelParams(level))
        game.play(game.board.xOf(r.move), game.board.yOf(r.move))
    }
    const results = analyzeGame(engine, game.setup(), { depth: 6, time: 1200 }).slice(opening)
    const loss = results.reduce((a, r) => a + r.loss, 0)
    totalLoss += loss
    totalMoves += results.length
    console.log(`level ${level} game ${g + 1}: ${results.length} moves, avg loss ${(loss / results.length * 100).toFixed(2)}%`)
}
console.log(`level ${level} AVG_LOSS ${(totalLoss / totalMoves * 100).toFixed(2)}% over ${totalMoves} moves`)
