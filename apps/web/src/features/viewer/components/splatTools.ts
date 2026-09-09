/**
 * Tipos compartilhados entre a barra de edição de splats e o overlay de seleção.
 * Ficam em arquivo próprio para evitar import circular entre os dois.
 */

/** Ferramenta de seleção de splats ativa. */
export type SplatTool = 'rect' | 'lasso' | 'none';

/** Modo de composição da seleção (shift/alt ao arrastar). */
export type SplatSelectMode = 'replace' | 'add' | 'subtract' | 'intersect';
