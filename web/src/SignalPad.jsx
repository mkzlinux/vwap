/**
 * The signal pad: one row per instrument, showing live price, VWAP, EMA9,
 * current bias, the most recent signal with its stop and target, and the
 * running hit rate / expectancy for that symbol.
 */

const GROUP_ORDER = { FX: 0, Index: 1, Metals: 2 };

export default function SignalPad({ rows, selected, onSelect, digitsFor }) {
  const sorted = [...rows].sort(
    (a, b) => (GROUP_ORDER[a.group] ?? 9) - (GROUP_ORDER[b.group] ?? 9) || a.symbol.localeCompare(b.symbol),
  );

  return (
    <div className="pad">
      <table>
        <thead>
          <tr>
            <th>Symbol</th>
            <th className="num">Price</th>
            <th className="num">VWAP</th>
            <th className="num">EMA9</th>
            <th>Bias</th>
            <th>Signal</th>
            <th className="num">Entry</th>
            <th className="num">SL</th>
            <th className="num">TP</th>
            <th className="num">RR</th>
            <th>Status</th>
            <th className="num">W/L</th>
            <th className="num">Hit%</th>
            <th className="num">Exp R</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => {
            const d = digitsFor(r.symbol);
            const f = (v) => (v == null ? '—' : v.toFixed(d));
            const last = r.lastSignal;
            const bias = r.bias;

            return (
              <tr
                key={r.symbol}
                className={`${r.symbol === selected ? 'sel' : ''} ${r.fresh ? 'fresh' : ''}`}
                onClick={() => onSelect(r.symbol)}
              >
                <td className="sym">
                  <span className="grp">{r.group}</span>
                  {r.symbol}
                </td>
                <td className="num">{f(r.price)}</td>
                <td className="num vwap">{f(r.vwap)}</td>
                <td className="num ema">{f(r.ema)}</td>
                <td>
                  <span className={`chip ${bias}`}>{bias === 'long' ? 'LONG' : bias === 'short' ? 'SHORT' : '—'}</span>
                </td>
                <td>
                  {last ? (
                    <span className={`chip ${last.dir > 0 ? 'long' : 'short'}`}>
                      {last.dir > 0 ? 'BUY' : 'SELL'}
                    </span>
                  ) : (
                    '—'
                  )}
                </td>
                <td className="num">{last ? f(last.entry) : '—'}</td>
                <td className="num loss">{last ? f(last.sl) : '—'}</td>
                <td className="num profit">{last ? f(last.tp) : '—'}</td>
                <td className="num">1:{r.rewardR}</td>
                <td>
                  {!last ? (
                    <span className="st none">—</span>
                  ) : last.outcome === 1 ? (
                    <span className="st tp">TP</span>
                  ) : last.outcome === -1 ? (
                    <span className="st sl">SL</span>
                  ) : (
                    <span className="st open">OPEN</span>
                  )}
                </td>
                <td className="num">{r.sum.resolved > 0 ? `${r.sum.tp}/${r.sum.sl}` : '—'}</td>
                <td className="num">{r.sum.resolved > 0 ? `${Math.round(r.sum.hitRate * 100)}%` : '—'}</td>
                <td className={`num ${r.sum.expectancy > 0 ? 'profit' : r.sum.expectancy < 0 ? 'loss' : ''}`}>
                  {r.sum.resolved > 0 ? `${r.sum.expectancy >= 0 ? '+' : ''}${r.sum.expectancy.toFixed(2)}` : '—'}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
