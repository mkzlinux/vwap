/**
 * TradingView-position-tool style boxes, drawn as a lightweight-charts pane
 * primitive. lightweight-charts ships no box primitive, so this is the piece
 * that has to be written by hand.
 *
 * For each signal: a green rectangle from entry to target, a red rectangle
 * from entry to stop, thin rails on the three levels, and R-multiple guides
 * inside the profit zone.
 */

const PROFIT_FILL = 'rgba(46,160,67,0.18)';
const LOSS_FILL = 'rgba(248,81,73,0.18)';
const PROFIT_LINE = 'rgba(63,185,80,0.85)';
const LOSS_LINE = 'rgba(248,81,73,0.85)';
const GUIDE_LINE = 'rgba(139,148,158,0.35)';
const TEXT_COLOR = 'rgba(201,209,217,0.9)';

export class BoxesPrimitive {
  constructor(boxes = []) {
    this._boxes = boxes;
    this._series = null;
    this._chart = null;
  }

  attached(param) {
    this._series = param.series;
    this._chart = param.chart;
    // requestUpdate lives on the attached param, NOT on the series.
    this._requestUpdate = param.requestUpdate?.bind(param) ?? null;
  }

  detached() {
    this._series = null;
    this._chart = null;
    this._requestUpdate = null;
  }

  update(boxes) {
    this._boxes = boxes;
    // without this the new boxes sit in memory and the canvas keeps the old frame
    this._requestUpdate?.();
  }

  paneViews() {
    return [
      {
        renderer: {
          draw: (target) => this._draw(target),
        },
        zIndex: 0,
      },
    ];
  }

  _draw(target) {
    const series = this._series;
    const chart = this._chart;
    if (!series || !chart) return;

    const boxes = this._boxes;
    if (!boxes || boxes.length === 0) return;

    const ts = chart.timeScale();

    target.useMediaCoordinateSpace((scope) => {
      const ctx = scope.context;
      ctx.save();

      for (const b of boxes) {
        const x1 = ts.timeToCoordinate(b.startTime);
        const x2 = ts.timeToCoordinate(b.endTime);
        if (x1 == null || x2 == null) continue; // off-screen

        const left = Math.min(x1, x2);
        const width = Math.max(2, Math.abs(x2 - x1));

        const yEntry = series.priceToCoordinate(b.entry);
        const yTp = series.priceToCoordinate(b.tp);
        const ySl = series.priceToCoordinate(b.sl);
        if (yEntry == null || yTp == null || ySl == null) continue;

        const alpha = b.resolved ? 0.45 : 1;
        ctx.globalAlpha = alpha;

        // --- profit zone: entry -> target ---
        ctx.fillStyle = PROFIT_FILL;
        const pTop = Math.min(yEntry, yTp);
        const pH = Math.abs(yTp - yEntry);
        ctx.fillRect(left, pTop, width, pH);

        // --- loss zone: entry -> stop ---
        ctx.fillStyle = LOSS_FILL;
        const lTop = Math.min(yEntry, ySl);
        const lH = Math.abs(ySl - yEntry);
        ctx.fillRect(left, lTop, width, lH);

        // --- rails ---
        ctx.lineWidth = 1;
        ctx.strokeStyle = PROFIT_LINE;
        ctx.beginPath();
        ctx.moveTo(left, yTp);
        ctx.lineTo(left + width, yTp);
        ctx.stroke();

        ctx.strokeStyle = LOSS_LINE;
        ctx.beginPath();
        ctx.moveTo(left, ySl);
        ctx.lineTo(left + width, ySl);
        ctx.stroke();

        ctx.strokeStyle = b.dir > 0 ? PROFIT_LINE : LOSS_LINE;
        ctx.beginPath();
        ctx.moveTo(left, yEntry);
        ctx.lineTo(left + width, yEntry);
        ctx.stroke();

        // --- R-multiple guides inside the profit zone ---
        const risk = Math.abs(ySl - yEntry);
        const sign = b.dir > 0 ? -1 : 1; // +1R is up for a long
        if (risk > 6) {
          ctx.strokeStyle = GUIDE_LINE;
          ctx.setLineDash([3, 3]);
          for (const r of [1, 2]) {
            const y = yEntry + sign * risk * r;
            if (y < -50 || y > scope.mediaSize.height + 50) continue;
            ctx.beginPath();
            ctx.moveTo(left, y);
            ctx.lineTo(left + width, y);
            ctx.stroke();
            ctx.fillStyle = TEXT_COLOR;
            ctx.font = '10px system-ui, sans-serif';
            ctx.fillText(`${r}R`, left + width + 4, y + 3);
          }
          ctx.setLineDash([]);
        }

        // --- TP / SL labels at the right edge ---
        ctx.fillStyle = TEXT_COLOR;
        ctx.font = '10px system-ui, sans-serif';
        ctx.fillText('TP', left + width + 4, yTp + 3);
        ctx.fillText('SL', left + width + 4, ySl + 3);
      }

      ctx.restore();
    });
  }
}
