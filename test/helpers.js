import { Board, BLACK, WHITE } from '../src/core/board.js'

export function fromRows(rows, forbidden = false) {
    const size = rows.length
    const board = new Board(size, forbidden)
    rows.forEach((row, y) => {
        const cells = row.replace(/\s+/g, '')
        if (cells.length !== size) throw new Error(`row ${y} length ${cells.length} != ${size}`)
        for (let x = 0; x < size; x++) {
            if (cells[x] === 'X') board.place(board.idx(x, y), BLACK)
            else if (cells[x] === 'O') board.place(board.idx(x, y), WHITE)
        }
    })
    return board
}

export function emptyRows(size) {
    return Array.from({ length: size }, () => '.'.repeat(size))
}

export function withStones(size, stones) {
    const rows = emptyRows(size).map(r => r.split(''))
    for (const [x, y, c] of stones) rows[y][x] = c
    return rows.map(r => r.join(''))
}
