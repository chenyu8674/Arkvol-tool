export const EMPTY = 0
export const BLACK = 1
export const WHITE = 2
export const WALL = 3

export const WINDOW_WEIGHTS = [0, 1, 10, 100, 1000, 100000]

const WT = WINDOW_WEIGHTS
const MAX_CELLS = 21 * 21
const DIR_XY = [[1, 0], [0, 1], [1, 1], [-1, 1]]

function makeRandom(seed) {
    return function () {
        seed = (seed + 0x6D2B79F5) | 0
        let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
        return (t ^ (t >>> 14)) | 0
    }
}

const rand = makeRandom(20240601)
const Z_LO = [null, new Int32Array(MAX_CELLS), new Int32Array(MAX_CELLS)]
const Z_HI = [null, new Int32Array(MAX_CELLS), new Int32Array(MAX_CELLS)]
for (let c = 1; c <= 2; c++) {
    for (let i = 0; i < MAX_CELLS; i++) {
        Z_LO[c][i] = rand()
        Z_HI[c][i] = rand()
    }
}
export const SIDE_HASH = rand()

export function opponent(color) {
    return 3 - color
}

/**
 * 棋盘：一维数组 + 1 格边界哨兵。
 * 以所有长度为 5 的窗口（四个方向）为单位增量维护双方棋子计数与估值，
 * 落子 / 撤子只需更新经过该点的至多 20 个窗口。
 */
export class Board {
    constructor(size = 15, forbidden = false) {
        this.size = size
        this.width = size + 2
        this.forbidden = forbidden
        this.total = size * size
        const w = this.width
        this.dirs = DIR_XY.map(([dx, dy]) => dy * w + dx)

        this.cells = new Uint8Array(w * w)
        this.valid = DIR_XY.map(() => new Uint8Array(w * w))
        this.cnt = [null, DIR_XY.map(() => new Int8Array(w * w)), DIR_XY.map(() => new Int8Array(w * w))]
        this.near = new Uint8Array(w * w)
        this.inner = []
        this.neighbors = new Array(w * w)

        for (let y = 0; y < w; y++) {
            for (let x = 0; x < w; x++) {
                const p = y * w + x
                const edge = x === 0 || y === 0 || x === w - 1 || y === w - 1
                this.cells[p] = edge ? WALL : EMPTY
                if (edge) continue
                this.inner.push(p)
                for (let d = 0; d < 4; d++) {
                    const ex = x + 4 * DIR_XY[d][0]
                    const ey = y + 4 * DIR_XY[d][1]
                    if (ex >= 1 && ex <= size && ey >= 1 && ey <= size) this.valid[d][p] = 1
                }
                const list = []
                for (let dy = -2; dy <= 2; dy++) {
                    for (let dx = -2; dx <= 2; dx++) {
                        const nx = x + dx
                        const ny = y + dy
                        if ((dx || dy) && nx >= 1 && nx <= size && ny >= 1 && ny <= size) list.push(ny * w + nx)
                    }
                }
                this.neighbors[p] = Int16Array.from(list)
            }
        }
        this.inner = Int16Array.from(this.inner)

        this.center = this.idx(size >> 1, size >> 1)
        this.score = 0
        this.count = 0
        this.hashLo = 0
        this.hashHi = 0
        this.hist = []
        this.histColor = []
        this.lastMax = 0
    }

    idx(x, y) {
        return (y + 1) * this.width + x + 1
    }

    xOf(p) {
        return (p % this.width) - 1
    }

    yOf(p) {
        return Math.floor(p / this.width) - 1
    }

    get(x, y) {
        return this.cells[this.idx(x, y)]
    }

    place(p, color) {
        this.cells[p] = color
        this.hashLo ^= Z_LO[color][p]
        this.hashHi ^= Z_HI[color][p]
        const own = this.cnt[color]
        const oth = this.cnt[3 - color]
        let delta = 0
        for (let d = 0; d < 4; d++) {
            const step = this.dirs[d]
            const valid = this.valid[d]
            const oc = own[d]
            const tc = oth[d]
            for (let k = 0, s = p; k < 5 && s >= 0; k++, s -= step) {
                if (!valid[s]) continue
                const n = oc[s]
                const t = tc[s]
                if (t === 0) delta += WT[n + 1] - WT[n]
                else if (n === 0) delta += WT[t]
                oc[s] = n + 1
            }
        }
        this.score += color === BLACK ? delta : -delta
        const nb = this.neighbors[p]
        for (let i = 0; i < nb.length; i++) this.near[nb[i]]++
        this.hist.push(p)
        this.histColor.push(color)
        this.count++
    }

    undo() {
        const p = this.hist.pop()
        const color = this.histColor.pop()
        this.count--
        this.cells[p] = EMPTY
        this.hashLo ^= Z_LO[color][p]
        this.hashHi ^= Z_HI[color][p]
        const own = this.cnt[color]
        const oth = this.cnt[3 - color]
        let delta = 0
        for (let d = 0; d < 4; d++) {
            const step = this.dirs[d]
            const valid = this.valid[d]
            const oc = own[d]
            const tc = oth[d]
            for (let k = 0, s = p; k < 5 && s >= 0; k++, s -= step) {
                if (!valid[s]) continue
                const n = oc[s] - 1
                const t = tc[s]
                oc[s] = n
                if (t === 0) delta -= WT[n + 1] - WT[n]
                else if (n === 0) delta -= WT[t]
            }
        }
        this.score += color === BLACK ? delta : -delta
        const nb = this.neighbors[p]
        for (let i = 0; i < nb.length; i++) this.near[nb[i]]--
        return p
    }

    /** 在 p 落 color 后是否构成胜利（p 可以为空点，只检查邻居）。禁手规则下黑棋必须恰好五连。 */
    winAt(p, color) {
        const cells = this.cells
        const exact = this.forbidden && color === BLACK
        for (let d = 0; d < 4; d++) {
            const step = this.dirs[d]
            let n = 1
            for (let q = p + step; cells[q] === color; q += step) n++
            for (let q = p - step; cells[q] === color; q -= step) n++
            if (n === 5 || (n > 5 && !exact)) return true
        }
        return false
    }

    /** 获取 p 处形成的五连坐标列表，用于界面高亮。 */
    winLine(p, color) {
        const cells = this.cells
        const exact = this.forbidden && color === BLACK
        for (let d = 0; d < 4; d++) {
            const step = this.dirs[d]
            const line = [p]
            for (let q = p + step; cells[q] === color; q += step) line.push(q)
            for (let q = p - step; cells[q] === color; q -= step) line.unshift(q)
            if (line.length === 5 || (line.length > 5 && !exact)) return line
        }
        return null
    }

    /** 经过 p 且不含对方棋子的窗口中，己方棋子数的最大值，同时返回估值增量。 */
    pointScore(p, color) {
        const own = this.cnt[color]
        const oth = this.cnt[3 - color]
        let score = 0
        let max = 0
        for (let d = 0; d < 4; d++) {
            const step = this.dirs[d]
            const valid = this.valid[d]
            const oc = own[d]
            const tc = oth[d]
            for (let k = 0, s = p; k < 5 && s >= 0; k++, s -= step) {
                if (!valid[s] || tc[s] !== 0) continue
                const n = oc[s]
                score += WT[n + 1] - WT[n]
                if (n > max) max = n
            }
        }
        this.lastMax = max
        return score
    }

    maxWindow(p, color) {
        const own = this.cnt[color]
        const oth = this.cnt[3 - color]
        let max = 0
        for (let d = 0; d < 4; d++) {
            const step = this.dirs[d]
            const valid = this.valid[d]
            const oc = own[d]
            const tc = oth[d]
            for (let k = 0, s = p; k < 5 && s >= 0; k++, s -= step) {
                if (valid[s] && tc[s] === 0 && oc[s] > max) max = oc[s]
            }
        }
        return max
    }

    candidates() {
        if (this.count === 0) return [this.center]
        const out = []
        const inner = this.inner
        for (let i = 0; i < inner.length; i++) {
            const p = inner[i]
            if (this.cells[p] === EMPTY && this.near[p] > 0) out.push(p)
        }
        return out
    }

    isFull() {
        return this.count >= this.total
    }
}
