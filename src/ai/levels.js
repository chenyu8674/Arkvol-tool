export const LEVELS = [
    { id: 1, name: '入门', depth: 1, width: 8, time: 300, vcf: 0, leafVcf: 0, noise: 260 },
    { id: 2, name: '初级', depth: 2, width: 10, time: 500, vcf: 4, leafVcf: 0, noise: 110 },
    { id: 3, name: '中级', depth: 4, width: 12, time: 1000, vcf: 6, leafVcf: 0, noise: 30 },
    { id: 4, name: '高级', depth: 6, width: 14, time: 2000, vcf: 10, leafVcf: 4, noise: 0 },
    { id: 5, name: '专家', depth: 8, width: 16, time: 4000, vcf: 14, leafVcf: 6, noise: 0 },
    { id: 6, name: '大师', depth: 12, width: 18, time: 8000, vcf: 18, leafVcf: 8, noise: 0 }
]

export function levelParams(id) {
    return LEVELS[Math.max(1, Math.min(LEVELS.length, id)) - 1]
}
