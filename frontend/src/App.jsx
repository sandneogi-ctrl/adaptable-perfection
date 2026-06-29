import React, { useState, useEffect, useCallback } from 'react';
import { stocksApi } from './services/api';
import './App.css';

const fmt = (n) => typeof n === 'number' ? n.toFixed(2) : '—';
const fmtVol = (n) => n >= 1e7 ? (n/1e7).toFixed(2)+'Cr' : n >= 1e5 ? (n/1e5).toFixed(1)+'L' : n?.toLocaleString() ?? '—';

function Badge({ open }) {
  return (
    <span className={`badge ${open ? 'badge-open' : 'badge-closed'}`}>
      <span className={`dot ${open ? 'dot-open' : 'dot-closed'}`} />
      {open ? 'Market Open' : 'Market Closed'}
    </span>
  );
}

function SummaryCard({ label, value, sub, color }) {
  return (
    <div className="summary-card">
      <div className="summary-label">{label}</div>
      <div className="summary-value" style={{ color }}>{value}</div>
      {sub && <div className="summary-sub">{sub}</div>}
    </div>
  );
}

function StockRow({ stock, rank }) {
  const up = stock.change_percent >= 0;
  return (
    <tr>
      <td className="rank">{rank}</td>
      <td>
        <div className="stock-symbol">{stock.symbol}</div>
        <div className="stock-name">{stock.name}</div>
      </td>
      <td className="num">₹{fmt(stock.ltp)}</td>
      <td className={`num ${up ? 'green' : 'red'}`}>
        {up ? '+' : ''}{fmt(stock.change_percent)}%
      </td>
      <td className={`num ${up ? 'green' : 'red'}`}>
        {up ? '+' : ''}₹{fmt(stock.change)}
      </td>
      <td className="num">₹{fmt(stock.open)}</td>
      <td className="num">₹{fmt(stock.high)}</td>
      <td className="num">₹{fmt(stock.low)}</td>
      <td className="num">{fmtVol(stock.volume)}</td>
    </tr>
  );
}

export default function App() {
  const [tab, setTab]               = useState('gainers');
  const [gainers, setGainers]       = useState([]);
  const [losers, setLosers]         = useState([]);
  const [summary, setSummary]       = useState(null);
  const [marketStatus, setMarket]   = useState(null);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState(null);
  const [fetchedAt, setFetchedAt]   = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [niftyIndex, setNiftyIndex] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [g, l, s, idx] = await Promise.all([
        stocksApi.getTopGainers(10),
        stocksApi.getTopLosers(10),
        stocksApi.getMarketSummary(),
        stocksApi.getNiftyIndex(),
      ]);
      if (g.success)   setGainers(g.data);
      if (l.success)   setLosers(l.data);
      if (s.success)   setSummary(s.data);
      if (idx.success) setNiftyIndex(idx);
      const ms = g.market_status || s.market_status;
      if (ms) setMarket(ms);
      setFetchedAt(g.fetched_at || s.fetched_at);
    } catch (e) {
      setError('Failed to load data. Check if the backend is running.');
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    try { await stocksApi.refresh(); await load(); }
    catch (e) { console.error(e); }
    finally { setRefreshing(false); }
  };

  useEffect(() => { load(); }, [load]);

  // Auto-refresh every 60s during market hours
  useEffect(() => {
    if (!marketStatus?.is_open) return;
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, [marketStatus, load]);

  const rows = tab === 'gainers' ? gainers : losers;

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div className="header-inner">
          <div className="header-title">
            <span className="header-icon">📈</span>
            <div>
              <h1>Nifty50 Scanner</h1>
              <p>Real-time market analysis</p>
            </div>
          </div>
          <div className="header-right">
            {niftyIndex && niftyIndex.success && (
              <div className="nifty-index">
                <span className="nifty-label">NIFTY 50</span>
                <span className="nifty-value">{niftyIndex.ltp?.toLocaleString('en-IN')}</span>
                <span className={`nifty-change ${niftyIndex.change_percent >= 0 ? 'green' : 'red'}`}>
                  {niftyIndex.change_percent >= 0 ? '▲' : '▼'} {Math.abs(niftyIndex.change_percent)}%
                </span>
              </div>
            )}
            {marketStatus && <Badge open={marketStatus.is_open} />}
            <button className="btn-refresh" onClick={handleRefresh} disabled={refreshing}>
              {refreshing ? 'Refreshing…' : '⟳ Refresh'}
            </button>
          </div>
        </div>
      </header>

      <main className="main">
        {/* Market closed note */}
        {marketStatus && !marketStatus.is_open && (
          <div className="closed-note">
            📌 {marketStatus.note}
          </div>
        )}

        {/* Summary cards */}
        {summary && (
          <div className="summary-grid">
            <SummaryCard label="Total Stocks"  value={summary.total_stocks}  />
            <SummaryCard label="Gainers"       value={summary.gainers_count}   color="#10b981" />
            <SummaryCard label="Losers"        value={summary.losers_count}    color="#ef4444" />
            <SummaryCard label="Avg Change"    value={`${summary.average_change > 0 ? '+' : ''}${fmt(summary.average_change)}%`}
                         color={summary.average_change >= 0 ? '#10b981' : '#ef4444'} />
            <SummaryCard label="Sentiment"     value={summary.market_sentiment}
                         color={summary.market_sentiment === 'Bullish' ? '#10b981' : '#ef4444'} />
            <SummaryCard label="Top Gainer"    value={summary.top_gainer?.symbol}
                         sub={`+${fmt(summary.top_gainer?.change_percent)}%`} color="#10b981" />
            <SummaryCard label="Top Loser"     value={summary.top_loser?.symbol}
                         sub={`${fmt(summary.top_loser?.change_percent)}%`}   color="#ef4444" />
          </div>
        )}

        {/* Tabs */}
        <div className="tabs">
          <button className={`tab ${tab === 'gainers' ? 'tab-active' : ''}`} onClick={() => setTab('gainers')}>
            🚀 Top Gainers
          </button>
          <button className={`tab ${tab === 'losers'  ? 'tab-active' : ''}`} onClick={() => setTab('losers')}>
            📉 Top Losers
          </button>
          {fetchedAt && (
            <span className="fetched-at">
              Last fetched: {new Date(fetchedAt).toLocaleTimeString()}
            </span>
          )}
        </div>

        {/* Table */}
        {loading ? (
          <div className="state-box">⏳ Loading market data…</div>
        ) : error ? (
          <div className="state-box error">
            ⚠️ {error}
            <button className="btn-retry" onClick={load}>Try Again</button>
          </div>
        ) : rows.length === 0 ? (
          <div className="state-box">
            {marketStatus && !marketStatus.is_open ? (
              <>
                <div style={{fontSize:'2rem', marginBottom:'0.75rem'}}>🕐</div>
                <div style={{fontSize:'1.1rem', fontWeight:600, marginBottom:'0.5rem'}}>
                  Market is Currently Closed
                </div>
                <div style={{fontSize:'0.875rem', color:'#94a3b8', marginBottom:'1rem'}}>
                  NSE trading hours: Monday–Friday, 9:15 AM – 3:30 PM IST
                </div>
                <div style={{fontSize:'0.825rem', color:'#64748b'}}>
                  Last session data will appear here once fetched from Angel One.<br/>
                  Click <strong>Refresh</strong> to load the most recent session data.
                </div>
                <button className="btn-retry" onClick={handleRefresh} disabled={refreshing}>
                  {refreshing ? 'Fetching…' : '⟳ Load Last Session Data'}
                </button>
              </>
            ) : (
              <>
                <div style={{fontSize:'2rem', marginBottom:'0.75rem'}}>📭</div>
                <div style={{fontSize:'1.1rem', fontWeight:600, marginBottom:'0.5rem'}}>
                  No Data Available
                </div>
                <div style={{fontSize:'0.875rem', color:'#94a3b8', marginBottom:'1rem'}}>
                  Could not fetch stock data from Angel One API.<br/>
                  This may be due to an expired session or API limit.
                </div>
                <button className="btn-retry" onClick={handleRefresh} disabled={refreshing}>
                  {refreshing ? 'Retrying…' : '⟳ Try Again'}
                </button>
              </>
            )}
          </div>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Stock</th>
                  <th>LTP</th>
                  <th>Change %</th>
                  <th>Change ₹</th>
                  <th>Open</th>
                  <th>High</th>
                  <th>Low</th>
                  <th>Volume</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((s, i) => <StockRow key={s.symbol} stock={s} rank={i + 1} />)}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
