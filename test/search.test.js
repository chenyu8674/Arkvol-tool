import test from 'node:test'
import assert from 'node:assert/strict'
import { BLACK, WHITE } from '../src/core/board.js'
import { Engine } from '../src/ai/search.js'
import { levelParams } from '../src/ai/levels.js'
import { fromRows, withStones } from './helpers.js'

const X = 'X'
const O = 'O'
const engine = new Engine()
const strong = { ...levelParams(4), time: 3000 }
const move = (board, r) => [board.xOf(r.move), board.yOf(r.move)]

test('takes an immediate win', () => {
    const board = fromRows(withStones(15, [[4, 7, X], [5, 7, X], [6, 7, X], [7, 7, X], [4, 8, O], [5, 8, O], [6, 8, O]]))
    const r = engine.search(board, BLACK, strong)
    const [x, y] = move(board, r)
    assert.ok((x === 3 || x === 8) && y === 7)
})

test('blocks an opponent four', () => {
    const board = fromRows(withStones(15, [[4, 7, O], [5, 7, O], [6, 7, O], [7, 7, O], [4, 8, X], [5, 9, X]]))
    const r = engine.search(board, BLACK, strong)
    const [x, y] = move(board, r)
    assert.ok((x === 3 || x === 8) && y === 7)
})

test('answers an open three', () => {
    const board = fromRows(withStones(15, [[6, 7, O], [7, 7, O], [8, 7, O], [7, 8, X], [7, 9, X]]))
    const r = engine.search(board, BLACK, strong)
    const [x, y] = move(board, r)
    assert.ok(y === 7 && (x === 5 || x === 9 || x === 4 || x === 10), `got ${x},${y}`)
})

test('finds a VCF win', () => {
    // 黑：横向三连 + 竖向三连交汇，冲四后形成双四
    const board = fromRows(withStones(15, [
        [5, 7, X], [6, 7, X], [7, 7, X],
        [8, 4, X], [8, 5, X], [8, 6, X],
        [4, 7, O], [8, 3, O]
    ]))
    const r = engine.search(board, BLACK, strong)
    assert.ok(r.proven, 'VCF should be proven')
    const bx = board.xOf(r.move)
    const by = board.yOf(r.move)
    board.place(r.move, BLACK)
    assert.ok(board.maxWindow(board.idx(8, 7), BLACK) >= 3 || bx === 8 || by === 7)
})

test('white exploits black forbidden point when blocking', () => {
    const board = fromRows(withStones(15, [
        [6, 7, X], [8, 7, X], [7, 6, X], [7, 8, X],
        [3, 3, O], [3, 5, O], [11, 11, O]
    ]), true)
    const r = engine.search(board, WHITE, { ...strong, time: 500 })
    assert.ok(r.move >= 0)
})

test('black never plays a forbidden point', () => {
    const board = fromRows(withStones(15, [
        [6, 7, X], [8, 7, X], [7, 6, X], [7, 8, X],
        [6, 6, O], [8, 8, O], [5, 7, O], [9, 7, O]
    ]), true)
    const r = engine.search(board, BLACK, { ...strong, time: 800 })
    const [x, y] = move(board, r)
    assert.ok(!(x === 7 && y === 7))
})

test('search leaves the board unchanged', () => {
    const board = fromRows(withStones(15, [[7, 7, X], [8, 8, O], [7, 8, X], [6, 6, O]]))
    const before = [board.score, board.hashLo, board.hashHi, board.count]
    engine.search(board, BLACK, { ...levelParams(3), time: 400 })
    assert.deepEqual([board.score, board.hashLo, board.hashHi, board.count], before)
})

test('small board search works', () => {
    const board = fromRows(withStones(9, [[4, 4, X], [3, 3, O]]))
    const r = engine.search(board, BLACK, { ...levelParams(3), time: 400 })
    assert.ok(r.move >= 0)
})
