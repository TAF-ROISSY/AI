/**
 * Signaux à implémenter après branchement des données :
 * tendance, momentum, volatilité, volume, niveaux, calendrier et risque.
 * Chaque sortie doit rester explicable et conserver ses données d'origine.
 */
export const analysisContract = {
  trend: { direction: 'unknown', score: null, evidence: [] },
  momentum: { rsi14: null, score: null, evidence: [] },
  volatility: { atr14: null, regime: 'unknown', evidence: [] },
  volume: { relative: null, score: null, evidence: [] },
  scenarios: [],
  invalidation: null,
  dataQuality: 'unknown'
};
