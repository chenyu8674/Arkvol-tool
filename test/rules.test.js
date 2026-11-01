import test from 'node:test'
import assert from 'node:assert/strict'
import { isForbidden, forbiddenPoints } from '../src/core/rules.js'
import { fromRows, withStones } from './helpers.js'

const X = 'X'
const O = 'O'
const at = (board, x, y) => isForbidden(board, board.idx(x, y))

test('double three is forbidden', () => {
    const board = fromRows(withStones(15, [[6, 7, X], [8, 7, X], [7, 6, X], [7, 8, X]]), true)
    assert.equal(at(board, 7, 7), true)
})

test('double three on diagonals is forbidden', () => {
    const board = fromRows(withStones(15, [[5, 5, X], [6, 6, X], [9, 5, X], [8, 6, X]]), true)
    assert.equal(at(board, 7, 7), true)
})

test('single three is allowed', () => {
    const board = fromRows(withStones(15, [[6, 7, X], [8, 7, X]]), true)
    assert.equal(at(board, 7, 7), false)
})

test('double four is forbidden', () => {
    const board = fromRows(withStones(15, [
        [4, 7, X], [5, 7, X], [6, 7, X],
        [7, 4, X], [7, 5, X], [7, 6, X]
    ]), true)
    assert.equal(at(board, 7, 7), true)
})

test('double four within one line is forbidden', () => {
    const board = fromRows(withStones(15, [
        [3, 7, X], [4, 7, X], [7, 7, X], [9, 7, X], [10, 7, X]
    ]), true)
    assert.equal(at(board, 6, 7), true)
})

test('straight four counts as a single four', () => {
    const board = fromRows(withStones(15, [[5, 7, X], [6, 7, X], [7, 7, X]]), true)
    assert.equal(at(board, 8, 7), false)
})

test('overline is forbidden', () => {
    const board = fromRows(withStones(15, [
        [2, 7, X], [3, 7, X], [4, 7, X], [6, 7, X], [7, 7, X]
    ]), true)
    assert.equal(at(board, 5, 7), true)
})

test('exact five on a would-be forbidden point is legal', () => {
    const board = fromRows(withStones(15, [
        [3, 7, X], [4, 7, X], [5, 7, X], [6, 7, X],
        [7, 4, X], [7, 5, X], [7, 6, X]
    ]), true)
    assert.equal(at(board, 7, 7), false)
})

test('four-three is allowed', () => {
    const board = fromRows(withStones(15, [
        [4, 7, X], [5, 7, X], [6, 7, X],
        [7, 5, X], [7, 6, X]
    ]), true)
    assert.equal(at(board, 7, 7), false)
})

test('blocked three does not count', () => {
    const board = fromRows(withStones(15, [
        [6, 7, X], [8, 7, X], [5, 7, O], [9, 7, O],
        [7, 6, X], [7, 8, X]
    ]), true)
    assert.equal(at(board, 7, 7), false)
})

test('three whose only open-four point is forbidden is not a three', () => {
    const base = [
        [5, 7, X], [6, 7, X],
        [7, 5, X], [7, 6, X],
        [8, 4, X], [8, 5, X], [8, 6, X]
    ]
    const fake = fromRows(withStones(15, [...base, [3, 7, O]]), true)
    const placed = fromRows(withStones(15, [...base, [3, 7, O], [7, 7, X]]), true)
    assert.equal(at(placed, 8, 7), true)
    assert.equal(at(fake, 7, 7), false)
    const real = fromRows(withStones(15, base), true)
    assert.equal(at(real, 7, 7), true)
})

test('forbiddenPoints lists forbidden cells', () => {
    const board = fromRows(withStones(15, [[6, 7, X], [8, 7, X], [7, 6, X], [7, 8, X]]), true)
    const pts = forbiddenPoints(board).map(p => [board.xOf(p), board.yOf(p)])
    assert.ok(pts.some(([x, y]) => x === 7 && y === 7))
})
