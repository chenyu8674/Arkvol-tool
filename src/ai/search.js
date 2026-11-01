import { BLACK, EMPTY, SIDE_HASH } from '../core/board.js'
import { isForbidden } from '../core/rules.js'

export const WIN = 1000000
const INF = 10000000
const TT_BITS = 18
const TT_SIZE = 1 << TT_BITS
const TT_MASK = TT_SIZE - 1
const FLAG_EXACT = 0
const FLAG_LOWER = 1
const FLAG_UPPER = 2
const MATE_BOUND = WIN - 1000

export class Engine {
    constructor() {
        this.ttHi = new Int32Array(TT_SIZE)
        this.ttDepth = new Int8Array(TT_SIZE)
        this.ttFlag = new Uint8Array(TT_SIZE)
        this.ttScore = new Int32Array(TT_SIZE)
        this.ttMove = new Int16Array(TT_SIZE)
        this.nodes = 0
        this.aborted = false
    }

    legal(p, color) {
        const board = this.board
        return !(board.forbidden && color === BLACK && isForbidden(board, p))
    }

    scanThreats(color) {
        const board = this.board
        const opp = 3 - color
        const cands = board.candidates()
        const blocks = []
        for (let i = 0; i < cands.length; i++) {
            const p = cands[i]
            if (board.maxWindow(p, color) >= 4 && board.winAt(p, color)) return { win: p, blocks, cands }
        }
        for (let i = 0; i < cands.length; i++) {
            const p = cands[i]
            if (board.maxWindow(p, opp) >= 4 && board.winAt(p, opp)) blocks.push(p)
        }
        return { win: -1, blocks, cands }
    }

    genMoves(color, ply, quiet, ttMove = -1) {
        const board = this.board
        const th = this.scanThreats(color)
        if (th.win >= 0) return { moves: [th.win], forced: true, win: true }
        if (th.blocks.length) {
            return { moves: th.blocks.filter(p => this.legal(p, color)), forced: true, win: false }
        }
        if (quiet) return null
        const opp = 3 - color
        const cands = th.cands
        const scored = new Array(cands.length)
        for (let i = 0; i < cands.length; i++) {
            const p = cands[i]
            scored[i] = { p, s: board.pointScore(p, color) + 0.9 * board.pointScore(p, opp) }
        }
        scored.sort((a, b) => b.s - a.s)
        const limit = Math.max(5, this.params.width - 2 * ply)
        const moves = []
        for (let i = 0; i < scored.length && moves.length < limit; i++) {
            const p = scored[i].p
            if (this.legal(p, color)) moves.push(p)
        }
        if (ttMove >= 0) {
            const k = moves.indexOf(ttMove)
            if (k > 0) {
                moves.splice(k, 1)
                moves.unshift(ttMove)
            } else if (k < 0 && board.cells[ttMove] === EMPTY && this.legal(ttMove, color)) {
                moves.unshift(ttMove)
            }
        }
        return { moves, forced: false, win: false }
    }

    completions(p, att) {
        const board = this.board
        const own = board.cnt[att]
        const oth = board.cnt[3 - att]
        const out = []
        for (let d = 0; d < 4; d++) {
            const step = board.dirs[d]
            const valid = board.valid[d]
            for (let k = 0, s = p; k < 5 && s >= 0; k++, s -= step) {
                if (!valid[s] || own[d][s] !== 4 || oth[d][s] !== 0) continue
                for (let i = 0; i < 5; i++) {
                    const q = s + i * step
                    if (board.cells[q] === EMPTY) {
                        if (!out.includes(q) && board.winAt(q, att)) out.push(q)
                        break
                    }
                }
            }
        }
        return out
    }

    /** VCF：只用“冲四”连续进攻的必胜搜索。返回第一步必胜着法，没有则返回 -1。 */
    vcf(att, depth, limit) {
        this.vcfNodes = 0
        this.vcfLimit = limit
        return this.vcfRec(att, depth)
    }

    vcfRec(att, depth) {
        if (++this.vcfNodes > this.vcfLimit) return -1
        const board = this.board
        const opp = 3 - att
        const cands = board.candidates()
        const makers = []
        for (let i = 0; i < cands.length; i++) {
            const p = cands[i]
            const m = board.maxWindow(p, att)
            if (m >= 4 && board.winAt(p, att)) return p
            if (m >= 3) makers.push(p)
        }
        for (let i = 0; i < cands.length; i++) {
            const p = cands[i]
            if (board.maxWindow(p, opp) >= 4 && board.winAt(p, opp)) return -1
        }
        if (depth <= 0) return -1
        for (let i = 0; i < makers.length; i++) {
            const p = makers[i]
            if (board.forbidden && att === BLACK && isForbidden(board, p)) continue
            board.place(p, att)
            const comp = this.completions(p, att)
            let win = false
            if (comp.length >= 2) {
                win = true
            } else if (comp.length === 1) {
                const e = comp[0]
                if (board.forbidden && opp === BLACK && isForbidden(board, e)) {
                    win = true
                } else {
                    board.place(e, opp)
                    if (!board.winAt(e, opp)) win = this.vcfRec(att, depth - 1) >= 0
                    board.undo()
                }
            }
            board.undo()
            if (win) return p
        }
        return -1
    }

    leaf(color, ply) {
        if (this.params.leafVcf > 0 && this.vcf(color, this.params.leafVcf, 120) >= 0) return WIN - ply - 100
        return color === BLACK ? this.board.score : -this.board.score
    }

    negamax(color, depth, alpha, beta, ply) {
        this.nodes++
        if ((this.nodes & 2047) === 0 && performance.now() > this.deadline) this.aborted = true
        if (this.aborted) return 0
        const board = this.board
        if (board.isFull()) return 0
        const opp = 3 - color

        let gen
        let ttMove = -1
        const key = (board.hashLo ^ (color === BLACK ? 0 : SIDE_HASH)) & TT_MASK
        const keyHi = board.hashHi
        if (depth <= 0) {
            if (ply >= this.maxPly) return this.leaf(color, ply)
            gen = this.genMoves(color, ply, true)
            if (gen === null) return this.leaf(color, ply)
        } else {
            if (this.ttDepth[key] >= 0 && this.ttHi[key] === keyHi) {
                ttMove = this.ttMove[key]
                if (this.ttDepth[key] >= depth) {
                    let s = this.ttScore[key]
                    if (s > MATE_BOUND) s -= ply
                    else if (s < -MATE_BOUND) s += ply
                    const flag = this.ttFlag[key]
                    if (flag === FLAG_EXACT) return s
                    if (flag === FLAG_LOWER && s > alpha) alpha = s
                    else if (flag === FLAG_UPPER && s < beta) beta = s
                    if (alpha >= beta) return s
                }
            }
            gen = this.genMoves(color, ply, false, ttMove)
        }

        const moves = gen.moves
        if (moves.length === 0) return -(WIN - ply)
        const origAlpha = alpha
        let best = -INF
        let bestMove = -1
        for (let i = 0; i < moves.length; i++) {
            const m = moves[i]
            board.place(m, color)
            let score
            if (board.winAt(m, color)) score = WIN - ply
            else if (board.isFull()) score = 0
            else score = -this.negamax(opp, depth - 1, -beta, -alpha, ply + 1)
            board.undo()
            if (this.aborted) return 0
            if (score > best) {
                best = score
                bestMove = m
                if (score > alpha) alpha = score
                if (alpha >= beta) break
            }
        }

        if (depth > 0) {
            let s = best
            if (s > MATE_BOUND) s += ply
            else if (s < -MATE_BOUND) s -= ply
            this.ttHi[key] = keyHi
            this.ttDepth[key] = depth
            this.ttScore[key] = s
            this.ttMove[key] = bestMove
            this.ttFlag[key] = best <= origAlpha ? FLAG_UPPER : best >= beta ? FLAG_LOWER : FLAG_EXACT
        }
        return best
    }

    begin(board, params) {
        this.board = board
        this.params = params
        this.nodes = 0
        this.aborted = false
        this.maxPly = params.depth + 12
        this.ttDepth.fill(-1)
        this.deadline = performance.now() + params.time
    }

    /**
     * 为 color 方选择着法。params: { depth, width, time, vcf, leafVcf, noise }。
     * 返回 { move, score, depth, nodes, proven, rootScores }。
     */
    search(board, color, params) {
        this.begin(board, params)
        const start = performance.now()
        const done = (r) => {
            r.nodes = this.nodes
            r.time = performance.now() - start
            return r
        }
        const gen = this.genMoves(color, 0, false)
        if (gen.moves.length === 0) return done({ move: -1, score: -WIN, depth: 0 })
        if (gen.win) return done({ move: gen.moves[0], score: WIN, depth: 0, proven: true })
        if (gen.moves.length === 1) return done({ move: gen.moves[0], score: 0, depth: 0 })
        if (board.count === 0) return done({ move: board.center, score: 0, depth: 0 })

        if (params.vcf > 0) {
            const m = this.vcf(color, params.vcf, 6000)
            if (m >= 0) return done({ move: m, score: WIN - 50, depth: 0, proven: true })
        }

        const opp = 3 - color
        const exact = params.noise > 0
        let moves = gen.moves
        let best = { move: moves[0], score: 0, depth: 0 }
        let rootScores = new Map()
        for (let depth = 1; depth <= params.depth; depth++) {
            let alpha = -INF
            let bestScore = -INF
            let bestMove = -1
            const scores = new Map()
            for (const m of moves) {
                board.place(m, color)
                let s
                if (board.winAt(m, color)) s = WIN
                else if (board.isFull()) s = 0
                else s = -this.negamax(opp, depth - 1, -INF, exact ? INF : -alpha, 1)
                board.undo()
                if (this.aborted) break
                scores.set(m, s)
                if (s > bestScore) {
                    bestScore = s
                    bestMove = m
                    if (s > alpha) alpha = s
                }
            }
            if (this.aborted) break
            best = { move: bestMove, score: bestScore, depth }
            rootScores = scores
            moves = moves.slice().sort((a, b) => scores.get(b) - scores.get(a))
            if (Math.abs(bestScore) > MATE_BOUND) break
        }
        const result = { ...best, rootScores }
        if (exact && rootScores.size > 1 && Math.abs(best.score) < MATE_BOUND) {
            result.move = this.sample(rootScores, best.score, params.noise)
            result.score = rootScores.get(result.move)
        }
        return done(result)
    }

    sample(scores, bestScore, temperature) {
        const items = []
        let sum = 0
        for (const [m, s] of scores) {
            const w = Math.exp(Math.max(-30, (s - bestScore) / temperature))
            items.push([m, w])
            sum += w
        }
        let r = Math.random() * sum
        for (const [m, w] of items) {
            r -= w
            if (r <= 0) return m
        }
        return items[0][0]
    }

    /** 以固定深度评估指定着法（相对 color 方的分数），用于复盘。 */
    scoreMove(board, color, move, depth, time) {
        this.begin(board, { depth, width: 14, time, vcf: 0, leafVcf: 4, noise: 0 })
        board.place(move, color)
        let s
        if (board.winAt(move, color)) s = WIN
        else if (board.isFull()) s = 0
        else s = -this.negamax(3 - color, Math.max(0, depth - 1), -INF, INF, 1)
        board.undo()
        return this.aborted ? null : s
    }
}
