import { Game } from '../src/core/game.js'
import { Engine } from '../src/ai/search.js'
import { levelParams } from '../src/ai/levels.js'
import { BLACK } from '../src/core/board.js'

export function parseArgs(argv) {
    const args = { a: 3, b: 4, games: 10, size: 15, forbidden: false, handicap: 0, opening: 2, timeScale: 1 }
    for (let i = 0; i < argv.length; i++) {
        const k = argv[i].replace(/^--/, '')
        if (k === 'forbidden') args.forbidden = true
        else if (k in args) args[k] = Number(argv[++i])
    }
    return args
}

function randomOpening(size, plies, rng) {
    const c = size >> 1
    const moves = []
    const used = new Set()
    while (moves.length < plies) {
        const x = c + Math.floor(rng() * 5) - 2
        const y = c + Math.floor(rng() * 5) - 2
        const key = x * 100 + y
        if (used.has(key)) continue
        used.add(key)
        moves.push([x, y])
    }
    return moves
}

function seeded(seed) {
    let s = seed
    return () => {
        s = (s * 1664525 + 1013904223) >>> 0
        return s / 4294967296
    }
}

/** 对局：返回 1 表示 levelBlack 方胜，-1 表示 levelWhite 方胜，0 平局。 */
export function playGame(engine, opts, paramsBlack, paramsWhite, opening) {
    const game = new Game({ size: opts.size, forbidden: opts.forbidden, handicap: opts.handicap })
    for (const [x, y] of opening) {
        if (game.over) break
        game.play(x, y)
    }
    let guard = 0
    while (!game.over && guard++ < opts.size * opts.size) {
        const params = game.turn === BLACK ? paramsBlack : paramsWhite
        const r = engine.search(game.board, game.turn, params)
        if (r.move < 0) break
        const res = game.play(game.board.xOf(r.move), game.board.yOf(r.move))
        if (!res.ok) throw new Error(`illegal move chosen: ${res.reason}`)
    }
    if (game.winner === BLACK) return 1
    if (game.winner) return -1
    return 0
}

export function eloFromScore(score) {
    const s = Math.min(0.99, Math.max(0.01, score))
    return -400 * Math.log10(1 / s - 1)
}

export function match(opts, paramsA, paramsB, log = () => {}) {
    const engine = new Engine()
    const rng = seeded(12345)
    let a = 0
    let b = 0
    let d = 0
    const pairs = Math.ceil(opts.games / 2)
    for (let i = 0; i < pairs; i++) {
        const opening = randomOpening(opts.size, opts.opening, rng)
        const r1 = playGame(engine, opts, paramsA, paramsB, opening)
        const r2 = -playGame(engine, opts, paramsB, paramsA, opening)
        for (const r of [r1, r2]) {
            if (r > 0) a++
            else if (r < 0) b++
            else d++
        }
        log(`pair ${i + 1}/${pairs}: A ${a} - B ${b} (draw ${d})`)
    }
    const n = a + b + d
    const score = (a + d / 2) / n
    return { a, b, d, n, score, elo: eloFromScore(score) }
}

if (import.meta.url === `file://${process.argv[1]}`) {
    const opts = parseArgs(process.argv.slice(2))
    const pa = { ...levelParams(opts.a) }
    const pb = { ...levelParams(opts.b) }
    pa.time *= opts.timeScale
    pb.time *= opts.timeScale
    console.log(`Level ${opts.a} (${pa.name}) vs Level ${opts.b} (${pb.name}), ${opts.size}x${opts.size}${opts.forbidden ? ' renju' : ''}`)
    const r = match(opts, pa, pb, console.log)
    console.log(`A ${r.a} / B ${r.b} / draw ${r.d}; score ${(r.score * 100).toFixed(1)}%; Elo(A - B) = ${r.elo.toFixed(0)}`)
}


