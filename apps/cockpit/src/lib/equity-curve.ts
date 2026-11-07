import { decimal } from "./backtest-contracts.ts";
import type { BacktestResult } from "./backtest-contracts.ts";

/** Pure deterministic geometry; no raw numeric strings enter SVG attributes. */
export function equityGeometry(points: BacktestResult["equity_curve"]) {
  if (points.length < 1 || points.length > 2000) throw new Error("CURVE_REJECTED");
  const values = points.map(point => decimal(point.equity, 0));
  const times = points.map(point => Date.parse(point.at));
  if (times.some((time, index) => !Number.isFinite(time) || (index > 0 && time < times[index - 1]))) throw new Error("CURVE_REJECTED");
  const low = Math.min(...values), high = Math.max(...values), span = high - low;
  // A flat series remains flat in the centre, never amplified into a gain.
  const padding = span ? span * 0.08 : Math.max(1, high * 0.01);
  const minimum = Math.max(0, low - padding), maximum = high + padding;
  const range = maximum - minimum;
  const duration = times[times.length - 1] - times[0];
  const coordinates = values.map((value, index) => {
    const x = duration > 0 ? 70 + (times[index] - times[0]) / duration * 650 : 395;
    const y = 260 - (value - minimum) / range * 220;
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  });
  return { points: coordinates.join(" "), minimum, maximum, first: values[0], last: values[values.length - 1] };
}
