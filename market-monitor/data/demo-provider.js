import { MarketDataProvider } from './provider-contract.js';

const quotes = {
  NVDA: { symbol: 'NVDA', market: 'NASDAQ', currency: 'USD', price: 142.36, changePct: 2.14, quality: 'DEMO' },
  MSFT: { symbol: 'MSFT', market: 'NASDAQ', currency: 'USD', price: 510.22, changePct: 0.64, quality: 'DEMO' },
  AAPL: { symbol: 'AAPL', market: 'NASDAQ', currency: 'USD', price: 239.18, changePct: -0.22, quality: 'DEMO' },
  MC: { symbol: 'MC', market: 'EURONEXT_PARIS', currency: 'EUR', price: 402.80, changePct: -0.31, quality: 'DEMO' },
  ASML: { symbol: 'ASML', market: 'EURONEXT_AMSTERDAM', currency: 'EUR', price: 734.50, changePct: 1.08, quality: 'DEMO' }
};

export class DemoMarketDataProvider extends MarketDataProvider {
  async getQuote(symbol) { return quotes[symbol] ?? { symbol, quality: 'NO_DATA' }; }
  async getHistory(symbol, interval = '1d', range = '3mo') {
    const quote = await this.getQuote(symbol);
    return { symbol, interval, range, currency: quote.currency, quality: 'DEMO', candles: [] };
  }
  async getMarketStatus(market) { return { market, state: 'SIMULATION', quality: 'DEMO' }; }
}
