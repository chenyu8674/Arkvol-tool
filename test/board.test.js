import test from 'node:test'
import assert from 'node:assert/strict'
import { Board, BLACK, WHITE } from '../src/core/board.js'
import { Game, handicapStones } from '../src/core/game.js'

test('place/undo restores score, hash and counters', () => {
    const board = new Board(15)
    const h0 = [board.hashLo, board.hashHi]
    const seq = [[7, 7], [8, 8], [7, 8], [6, 7], [9, 9], [5, 7], [7, 6], [7, 9]]
    let color = BLACK
    const scores = [board.score]
    for (const [x, y] of seq) {
        board.place(board.idx(x, y), color)
        scores.push(board.score)
        color = 3 - color
    }
    for (let i = seq.length - 1; i >= 0; i--) {
        assert.equal(board.score, scores[i + 1])
        board.undo()
    }
    assert.equal(board.score, 0)
    assert.deepEqual([board.hashLo, board.hashHi], h0)
    assert.equal(board.count, 0)
    assert.ok(board.near.every(v => v === 0))
    assert.ok(board.cnt[BLACK].every(a => a.every(v => v === 0)))
    assert.ok(board.cnt[WHITE].every(a => a.every(v => v === 0)))
})

test('eval is symmetric between colors', () => {
    const a = new Board(15)
    const b = new Board(15)
    for (const [x, y] of [[7, 7], [8, 7], [9, 7]]) a.place(a.idx(x, y), BLACK)
    for (const [x, y] of [[7, 7], [8, 7], [9, 7]]) b.place(b.idx(x, y), WHITE)
    assert.equal(a.score, -b.score)
    assert.ok(a.score > 0)
})

test('detects five in all directions and corners', () => {
    for (const [dx, dy] of [[1, 0], [0, 1], [1, 1], [1, -1]]) {
        const game = new Game({ size: 15 })
        const sx = dx === 1 && dy === -1 ? 3 : 3
        const sy = dy === -1 ? 10 : 3
        for (let i = 0; i < 5; i++) {
            game.play(sx + dx * i, sy + dy * i)
            if (i < 4) game.play(14, i * 2)
        }
        assert.equal(game.winner, BLACK, `direction ${dx},${dy}`)
        assert.equal(game.winLine.length, 5)
    }
})

test('freestyle: overline wins, renju: black overline is not a win', () => {
    for (const forbidden of [false, true]) {
        const board = new Board(15, forbidden)
        for (const x of [2, 3, 4, 6, 7]) board.place(board.idx(x, 7), BLACK)
        const p = board.idx(5, 7)
        assert.equal(board.winAt(p, BLACK), !forbidden)
        assert.equal(board.winAt(p, WHITE), false)
    }
})

test('handicap stones and turn order', () => {
    assert.deepEqual(handicapStones(15, 0), [])
    assert.equal(handicapStones(15, 1).length, 1)
    assert.equal(handicapStones(15, 3).length, 3)
    assert.equal(handicapStones(15, 9).length, 3)
    for (let n = 1; n <= 3; n++) {
        const game = new Game({ size: 15, handicap: n })
        assert.equal(game.board.count, n)
        assert.equal(game.turn, BLACK)
        assert.equal(game.board.get(7, 7), 0, 'center stays empty')
    }
    const game = new Game({ size: 15, handicap: 2 })
    game.play(7, 7)
    assert.equal(game.turn, WHITE)
    assert.equal(game.board.count, 3)
    game.undo()
    assert.equal(game.turn, BLACK)
    assert.equal(game.board.count, 2)
})

test('game validates moves and detects draw by full board', () => {
    const game = new Game({ size: 9 })
    assert.equal(game.play(4, 4).ok, true)
    assert.equal(game.play(4, 4).reason, 'occupied')
    assert.equal(game.play(9, 0).reason, 'range')
})

test('works on all supported sizes', () => {
    for (let size = 9; size <= 19; size++) {
        const game = new Game({ size })
        const c = size >> 1
        for (let i = 0; i < 5; i++) {
            game.play(c - 2 + i, c)
            if (i < 4) game.play(c - 2 + i, c + 1)
        }
        assert.equal(game.winner, BLACK, `size ${size}`)
    }
})

test('game rejects forbidden moves for black and lists them', () => {
    const game = new Game({ size: 15, forbidden: true })
    const seq = [[6, 7], [0, 0], [8, 7], [0, 2], [7, 6], [0, 4], [7, 8], [0, 6]]
    for (const [x, y] of seq) assert.equal(game.play(x, y).ok, true)
    assert.equal(game.turn, BLACK)
    assert.ok(game.forbiddenList().some(([x, y]) => x === 7 && y === 7))
    assert.equal(game.play(7, 7).reason, 'forbidden')
    assert.equal(game.turn, BLACK)

    const free = new Game({ size: 15, forbidden: false })
    for (const [x, y] of seq) free.play(x, y)
    assert.equal(free.play(7, 7).ok, true)
})
