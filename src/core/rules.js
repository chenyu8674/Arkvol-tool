import { BLACK, EMPTY, WHITE } from './board.js'

const MAX_NEST = 3

/**
 * 读取 p 点沿方向 d 的 11 格（以 p 为中心，p 视为黑子）。
 * 1 = 黑子，0 = 空，2 = 白子或边界（阻挡）。
 */
function readLine(board, p, d) {
    const a = new Int8Array(11)
    const step = board.dirs[d]
    const cells = board.cells
    a[5] = 1
    for (const sign of [1, -1]) {
        let q = p
        let blocked = false
        for (let i = 1; i <= 5; i++) {
            const j = 5 + sign * i
            if (blocked) {
                a[j] = 2
                continue
            }
            q += sign * step
            const v = cells[q]
            if (v === BLACK) a[j] = 1
            else if (v === EMPTY) a[j] = 0
            else {
                a[j] = 2
                blocked = true
            }
        }
    }
    return a
}

function runLength(a) {
    let lo = 5
    let hi = 5
    while (lo > 0 && a[lo - 1] === 1) lo--
    while (hi < 10 && a[hi + 1] === 1) hi++
    return hi - lo + 1
}

/**
 * 统计该线上包含中心点的“冲四”数量：补一子即成恰好五连的不同四子组合数。
 * 活四（两端都能成五）只算一个四；形如 ●●○●●○●● 的同线双四算两个。
 */
function fourInfo(a) {
    const masks = []
    const hits = []
    for (let j = 0; j < 11; j++) {
        if (a[j] !== 0) continue
        a[j] = 1
        let lo = j
        let hi = j
        while (lo > 0 && a[lo - 1] === 1) lo--
        while (hi < 10 && a[hi + 1] === 1) hi++
        a[j] = 0
        if (hi - lo + 1 !== 5 || lo > 5 || hi < 5) continue
        let mask = 0
        for (let i = lo; i <= hi; i++) if (i !== j) mask |= 1 << i
        const k = masks.indexOf(mask)
        if (k < 0) {
            masks.push(mask)
            hits.push(1)
        } else {
            hits[k]++
        }
    }
    return { count: masks.length, straight: hits.some(h => h >= 2) }
}

function hasTrueThree(board, p, d, a, nest) {
    const step = board.dirs[d]
    for (let j = 0; j < 11; j++) {
        if (a[j] !== 0) continue
        a[j] = 1
        const info = fourInfo(a)
        a[j] = 0
        if (!info.straight) continue
        const q = p + (j - 5) * step
        if (forbiddenAt(board, q, nest + 1)) continue
        return true
    }
    return false
}

function analyze(board, p, nest) {
    const lines = []
    let overline = false
    for (let d = 0; d < 4; d++) {
        const a = readLine(board, p, d)
        const run = runLength(a)
        if (run === 5) return false
        if (run > 5) overline = true
        lines.push(a)
    }
    if (overline) return true
    let fours = 0
    let threes = 0
    for (let d = 0; d < 4; d++) {
        const info = fourInfo(lines[d])
        if (info.count > 0) {
            fours += info.count
        } else if (nest < MAX_NEST && hasTrueThree(board, p, d, lines[d], nest)) {
            threes++
        }
    }
    return fours >= 2 || threes >= 2
}

function forbiddenAt(board, p, nest) {
    const cells = board.cells
    cells[p] = BLACK
    const result = analyze(board, p, nest)
    cells[p] = EMPTY
    return result
}

/**
 * 判断黑棋落在空点 p 是否为禁手（长连、四四、三三）。
 * 恰好五连优先于禁手；真活三需要其成活四的点本身不是禁手。
 * 调用方应保证只在启用禁手规则时对黑棋调用。
 */
export function isForbidden(board, p) {
    if (board.cells[p] !== EMPTY) return false
    const own = board.cnt[BLACK]
    const oth = board.cnt[WHITE]
    let dirs2 = 0
    let big = false
    for (let d = 0; d < 4; d++) {
        const step = board.dirs[d]
        const valid = board.valid[d]
        let max = 0
        for (let k = 0, s = p; k < 5 && s >= 0; k++, s -= step) {
            if (valid[s] && oth[d][s] === 0 && own[d][s] > max) max = own[d][s]
        }
        if (max >= 3) big = true
        if (max >= 2) dirs2++
    }
    if (!big && dirs2 < 2) return false
    return forbiddenAt(board, p, 0)
}

export function forbiddenPoints(board) {
    const out = []
    for (const p of board.candidates()) {
        if (isForbidden(board, p)) out.push(p)
    }
    return out
}
