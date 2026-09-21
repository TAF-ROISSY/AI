/**
 * Contrat minimal d'un fournisseur de données.
 * La V1 fonctionne avec le provider de démonstration ; une API réelle
 * pourra être ajoutée sans modifier l'interface ni le moteur d'analyse.
 */
export class MarketDataProvider {
  async getQuote(symbol) { throw new Error(`getQuote non implémenté pour ${symbol}`); }
  async getHistory(symbol, interval = '1d', range = '3mo') {
    throw new Error(`getHistory non implémenté pour ${symbol}`);
  }
  async getMarketStatus(market) { throw new Error(`getMarketStatus non implémenté pour ${market}`); }
}
