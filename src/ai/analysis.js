import { buildBoard } from '../core/game.js'
import { WIN } from './search.js'

const WINPROB_SCALE = 500

export function winProb(score) {
    if (score > WIN / 2) return 1
    if (score < -WIN / 2) return 0
    return 1 / (1 + Math.exp(-score / WINPROB_SCALE))
}

/**
 * 复盘：对每一步用同一深度搜索最佳着法与实战着法，
 * 以胜率损失衡量失误大小。返回逐步结果（分数均相对走子方）。
 */
export function analyzeGame(engine, setup, options = {}, onProgress = () => {}) {
    const { depth = 6, time = 1500, cancelled = () => false } = options
    const board = buildBoard({ ...setup, moves: [] })
    const results = []
    let color = setup.first
    for (let i = 0; i < setup.moves.length; i++) {
        if (cancelled()) break
        const [x, y] = setup.moves[i]
        const played = board.idx(x, y)
        const best = engine.search(board, color, { depth, width: 14, time, vcf: 8, leafVcf: 4, noise: 0 })
        let playedScore = best.score
        if (best.move !== played) {
            const s = engine.scoreMove(board, color, played, Math.max(1, best.depth), time)
            playedScore = s === null ? best.score : s
        }
        playedScore = Math.min(playedScore, best.score)
        const wpBest = winProb(best.score)
        const wpPlayed = winProb(playedScore)
        results.push({
            index: i,
            color,
            x,
            y,
            best: [board.xOf(best.move), board.yOf(best.move)],
            bestScore: best.score,
            playedScore,
            loss: Math.max(0, wpBest - wpPlayed),
            wpMover: wpBest,
            depth: best.depth
        })
        onProgress(i + 1, setup.moves.length)
        board.place(played, color)
        color = 3 - color
    }
    return results
}

export function summarize(results) {
    const sides = {}
    for (const r of results) {
        const s = sides[r.color] || (sides[r.color] = { moves: 0, loss: 0, blunders: 0, mistakes: 0, inaccuracies: 0 })
        s.moves++
        s.loss += r.loss
        if (r.loss >= 0.3) s.blunders++
        else if (r.loss >= 0.15) s.mistakes++
        else if (r.loss >= 0.05) s.inaccuracies++
    }
    for (const c of Object.keys(sides)) {
        const s = sides[c]
        s.avgLoss = s.moves ? s.loss / s.moves : 0
        s.accuracy = Math.max(0, 100 * (1 - s.avgLoss * 3))
        s.rating = estimateRating(s.avgLoss)
    }
    return sides
}

/** 平均胜率损失到棋力档位的粗略映射，应以 scripts/calibrate.js 的结果为准。 */
export const RATING_TABLE = [
    { maxLoss: 0.01, name: '大师' },
    { maxLoss: 0.025, name: '专家' },
    { maxLoss: 0.05, name: '高级' },
    { maxLoss: 0.09, name: '中级' },
    { maxLoss: 0.14, name: '初级' },
    { maxLoss: Infinity, name: '入门' }
]

export function estimateRating(avgLoss) {
    return RATING_TABLE.find(r => avgLoss <= r.maxLoss).name
}
