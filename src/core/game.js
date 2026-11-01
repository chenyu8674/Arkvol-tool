import { Board, BLACK, WHITE, EMPTY } from './board.js'
import { isForbidden, forbiddenPoints } from './rules.js'

export const MIN_SIZE = 9
export const MAX_SIZE = 19

export const MAX_HANDICAP = 3

const HANDICAP_OFFSETS = [[2, 2], [-2, -2], [2, -2]]

/**
 * 让子：开局先给黑棋预置 count 颗子（最多 3 子，围绕天元隔一格对称排布，天元留空），
 * 之后仍由黑棋先走。count = 0 表示不让子。
 */
export function handicapStones(size, count) {
    const c = size >> 1
    return HANDICAP_OFFSETS.slice(0, Math.min(count, MAX_HANDICAP)).map(([dx, dy]) => [c + dx, c + dy])
}

export function buildBoard(setup) {
    const board = new Board(setup.size, setup.forbidden)
    for (const [x, y, color] of setup.preset) board.place(board.idx(x, y), color)
    let color = setup.first
    for (const [x, y] of setup.moves) {
        board.place(board.idx(x, y), color)
        color = 3 - color
    }
    return board
}

export class Game {
    constructor({ size = 15, forbidden = false, handicap = 0 } = {}) {
        this.size = size
        this.forbidden = forbidden
        this.handicap = handicap
        this.preset = handicapStones(size, handicap).map(([x, y]) => [x, y, BLACK])
        this.first = BLACK
        this.board = buildBoard({ size, forbidden, preset: this.preset, first: this.first, moves: [] })
        this.moves = []
        this.turn = this.first
        this.winner = 0
        this.draw = false
        this.winLine = null
    }

    get over() {
        return this.winner !== 0 || this.draw
    }

    setup() {
        return {
            size: this.size,
            forbidden: this.forbidden,
            preset: this.preset.map(s => s.slice()),
            first: this.first,
            moves: this.moves.map(m => m.slice())
        }
    }

    isForbiddenAt(x, y) {
        if (!this.forbidden || this.turn !== BLACK) return false
        return isForbidden(this.board, this.board.idx(x, y))
    }

    forbiddenList() {
        if (!this.forbidden || this.turn !== BLACK || this.over) return []
        return forbiddenPoints(this.board).map(p => [this.board.xOf(p), this.board.yOf(p)])
    }

    play(x, y) {
        if (this.over) return { ok: false, reason: 'over' }
        if (x < 0 || y < 0 || x >= this.size || y >= this.size) return { ok: false, reason: 'range' }
        const p = this.board.idx(x, y)
        if (this.board.cells[p] !== EMPTY) return { ok: false, reason: 'occupied' }
        const color = this.turn
        if (this.forbidden && color === BLACK && isForbidden(this.board, p)) {
            return { ok: false, reason: 'forbidden' }
        }
        this.board.place(p, color)
        this.moves.push([x, y])
        if (this.board.winAt(p, color)) {
            this.winner = color
            this.winLine = this.board.winLine(p, color).map(q => [this.board.xOf(q), this.board.yOf(q)])
        } else if (this.board.isFull()) {
            this.draw = true
        }
        this.turn = 3 - color
        return { ok: true, color }
    }

    undo() {
        if (!this.moves.length) return false
        this.board.undo()
        this.moves.pop()
        this.turn = this.first === BLACK
            ? (this.moves.length % 2 === 0 ? BLACK : WHITE)
            : (this.moves.length % 2 === 0 ? WHITE : BLACK)
        this.winner = 0
        this.draw = false
        this.winLine = null
        return true
    }

    colorOfMove(i) {
        return (i % 2 === 0) ? this.first : 3 - this.first
    }
}

export function coordName(size, x, y) {
    return String.fromCharCode(65 + x) + (size - y)
}
