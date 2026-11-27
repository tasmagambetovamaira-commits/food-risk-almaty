/* Общий код сайта: загрузка артефакта, форматирование, графики, сценарий.
   Сайт ничего не оценивает: все числа — из model/artifact.json (или window.ARTIFACT из artifact.js). */

const C = { carrot: "#F26B1D", steppe: "#5AAEE8", grey: "#3A4856", ink: "#E9EDF1", line: "#243241", grid: "#18232F", axis: "#4A5A6A", band: "#132536", bandText: "#8CC8F0" };
const NS = "http://www.w3.org/2000/svg";
const MONTHS = ["январь","февраль","март","апрель","май","июнь","июль","август","сентябрь","октябрь","ноябрь","декабрь"];
const MON3 = ["янв","фев","мар","апр","май","июн","июл","авг","сен","окт","ноя","дек"];

function num(x, d = 1) { return (x < 0 ? "−" : "") + Math.abs(x).toFixed(d).replace(".", ","); }
function pct(x, d = 1) { return num(x, d) + "%"; }
function pp(x, d = 1) { return (x > 0 ? "+" : "") + num(x, d) + " п.п."; }
function $(id) { return document.getElementById(id); }
function put(id, text) { const e = $(id); if (e) e.textContent = text; }
function putAll(cls, text) { document.querySelectorAll("." + cls).forEach(e => e.textContent = text); }

function loadArtifact() {
  if (window.ARTIFACT) return Promise.resolve(window.ARTIFACT);
  return fetch("../model/artifact.json").then(r => { if (!r.ok) throw new Error(r.status); return r.json(); });
}
function showLoadError() {
  const m = document.querySelector("main");
  if (m) m.insertAdjacentHTML("afterbegin",
    '<p class="loading-error wrap">Данные не загрузились. Откройте сайт по ссылке из README или запустите <code>make serve</code> в папке проекта.</p>');
}

function el(tag, attrs, parent, text) {
  const e = document.createElementNS(NS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (text !== undefined) e.textContent = text;
  parent.appendChild(e); return e;
}
function widthOf(svg) { const p = svg.parentNode; return Math.max(280, Math.round((p && p.clientWidth) || svg.getBoundingClientRect().width) || 700); }
function niceStep(range) { return range > 8 ? 2 : range > 3 ? 1 : 0.5; }

/* Вертикальные столбцы. opts: colors, ref (линия порога), refLabel, band [i0,i1] (подсветка окна), height */
function columns(svg, labels, values, opts = {}) {
  svg.innerHTML = "";
  const W = widthOf(svg), H = opts.height || (W < 520 ? 210 : 250);
  const L = 32, R = 6, T = 16, B = 28;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const lo = Math.min(0, ...values), hi = Math.max(...values, opts.ref || 0) * 1.1;
  const y = v => T + (hi - v) / (hi - lo) * (H - T - B);
  const bw = (W - L - R) / values.length;
  if (opts.band) {
    const [a, b] = opts.band;
    el("rect", { x: L + a * bw, y: T - 10, width: (b - a + 1) * bw, height: H - T - B + 10, fill: C.band, rx: 6 }, svg);
    el("text", { x: L + a * bw + 6, y: T + 2, style: "font-size:12px;font-weight:600;fill:" + C.bandText }, svg, opts.bandLabel || "");
  }
  const step = niceStep(hi - lo);
  for (let t = Math.ceil(lo / step) * step; t <= hi; t += step) {
    el("line", { x1: L, x2: W - R, y1: y(t), y2: y(t), stroke: C.grid }, svg);
    el("text", { x: L - 6, y: y(t) + 4, "text-anchor": "end", style: "font-size:11px" }, svg, num(t, step < 1 ? 1 : 0));
  }
  values.forEach((v, i) => {
    el("rect", { x: L + i * bw + bw * 0.16, y: Math.min(y(v), y(0)), width: bw * 0.68,
                 height: Math.max(1, Math.abs(y(v) - y(0))), fill: opts.colors ? opts.colors[i] : C.steppe }, svg);
    const every = bw < 22 ? 2 : 1;
    if (i % every === 0) el("text", { x: L + i * bw + bw / 2, y: H - B + 16, "text-anchor": "middle", style: "font-size:11px" }, svg, labels[i]);
  });
  el("line", { x1: L, x2: W - R, y1: y(0), y2: y(0), stroke: C.axis }, svg);
  if (opts.ref) {
    el("line", { x1: L, x2: W - R, y1: y(opts.ref), y2: y(opts.ref), stroke: C.carrot, "stroke-dasharray": "6 4", "stroke-width": 1.6 }, svg);
    el("text", { x: W - R, y: y(opts.ref) - 6, "text-anchor": "end", style: "font-size:12px;font-weight:600;fill:" + C.carrot }, svg, opts.refLabel || "");
  }
}

/* Горизонтальные столбцы с подписью значения */
function rows(svg, labels, values, colors) {
  svg.innerHTML = "";
  const W = widthOf(svg), rh = 26, L = W < 520 ? 112 : 150, R = 44, T = 4;
  const H = T + rh * values.length + 4;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const lo = Math.min(0, ...values), hi = Math.max(...values);
  const x = v => L + (v - lo) / (hi - lo) * (W - L - R);
  values.forEach((v, i) => {
    const yy = T + i * rh;
    el("text", { x: L - 8, y: yy + 17, "text-anchor": "end", style: "font-size:13px;fill:" + C.ink }, svg, labels[i]);
    el("rect", { x: Math.min(x(v), x(0)), y: yy + 5, width: Math.max(1.5, Math.abs(x(v) - x(0))), height: rh - 10, fill: colors[i] }, svg);
    el("text", { x: Math.max(x(v), x(0)) + 6, y: yy + 17, style: "font-size:12px" }, svg, num(v));
  });
}

/* Сценарий: та же формула, что ar1_seasonal в src/models.py.
   nov — рост в ноябре; shock — добавка к каждому месяцу январь–апрель. Возвращает накопленный рост янв–апр, %. */
function simulate(A, nov, shock) {
  const M = A.model; let y = nov, cum = 1;
  for (const m of [12, 1, 2, 3, 4]) {
    y = M.m[m - 1] + M.phi * y + (m <= 4 ? shock : 0);
    if (m <= 4) cum *= 1 + y / 100;
  }
  return (cum - 1) * 100;
}
/* Какой шок в месяц переводит центральный прогноз за порог (бисекция) */
function shockToThreshold(A) {
  const nov = A.forecast[0].point, thr = A.decision.threshold;
  let a = -3, b = 5;
  for (let k = 0; k < 50; k++) { const c = (a + b) / 2; if (simulate(A, nov, c) > thr) b = c; else a = c; }
  return (a + b) / 2;
}

function redraw(fn) { let t; addEventListener("resize", () => { clearTimeout(t); t = setTimeout(fn, 150); }); }

/* ---------- Липкий сюжет: один график сезонов, меняется по шагам ---------- */
function Stage(svg, A) {
  const S = A.seasons, D = A.decision;
  const items = S.map(s => ({ key: s.year, label: "’" + String(s.year).slice(2), v: s.growth }))
    .concat([{ key: 2027, label: "’27", v: 0 }]);
  const W = () => widthOf(svg);
  let nodes = null, ref, refT, ann, H, L = 30, R = 8, T = 22, B = 28, hi = Math.max(...S.map(s => s.growth)) * 1.1;
  function build() {
    svg.innerHTML = "";
    const w = W(); H = w < 520 ? 240 : 360;
    svg.setAttribute("viewBox", `0 0 ${w} ${H}`);
    const y = v => T + (hi - v) / hi * (H - T - B);
    for (let t = 0; t <= hi; t += 2) {
      el("line", { x1: L, x2: w - R, y1: y(t), y2: y(t), stroke: C.grid }, svg);
      el("text", { x: L - 6, y: y(t) + 4, "text-anchor": "end", style: "font-size:11px" }, svg, num(t, 0));
    }
    const bw = (w - L - R) / items.length;
    nodes = items.map((it, i) => {
      const r = el("rect", { x: L + i * bw + bw * .16, width: bw * .68, rx: 2 }, svg);
      r.style.y = y(0) + "px"; r.style.height = "0px"; r.style.fill = C.steppe;
      if (bw >= 22 || i % 2 === 0 || it.key === 2027)
        el("text", { x: L + i * bw + bw / 2, y: H - B + 16, "text-anchor": "middle", style: "font-size:11px" + (it.key === 2027 ? ";fill:#fff;font-weight:600" : "") }, svg, it.label);
      return { r, it, y };
    });
    el("line", { x1: L, x2: w - R, y1: y(0), y2: y(0), stroke: C.axis }, svg);
    ref = el("line", { x1: L, x2: w - R, y1: y(D.threshold), y2: y(D.threshold), stroke: C.carrot, "stroke-dasharray": "6 5", "stroke-width": 1.6, opacity: 0 }, svg);
    refT = el("text", { x: L + 6, y: y(D.threshold) - 7, "text-anchor": "start", opacity: 0, style: "font-size:12px;font-weight:600;fill:" + C.carrot }, svg, "порог " + pct(D.threshold, 2));
    ann = el("text", { x: 0, y: 0, opacity: 0, "text-anchor": "middle", style: "font-size:12px;font-weight:700;fill:#fff" }, svg, "");
  }
  function set(step) {
    if (!nodes) build();
    const y = nodes[0].y;
    nodes.forEach(({ r, it }) => {
      let v = it.v, fill = C.steppe, op = 1;
      if (it.key === 2027) { v = step >= 5 ? D.janapr_q75 : step >= 4 ? D.janapr_forecast : 0; fill = step >= 5 ? C.carrot : "#fff"; }
      else if (step >= 2 && v > D.threshold) fill = C.carrot;
      if (step === 3 && it.key !== 2022) op = .25;
      if (step >= 4 && it.key !== 2027) op = .35;
      r.style.y = Math.min(y(v), y(0)) + "px";
      r.style.height = Math.abs(y(v) - y(0)) + "px";
      r.style.fill = fill; r.style.opacity = op;
    });
    const showRef = step >= 2;
    ref.setAttribute("opacity", showRef ? 1 : 0); refT.setAttribute("opacity", showRef ? 1 : 0);
    const target = step === 3 ? 2022 : step >= 4 ? 2027 : null;
    if (target) {
      const n = nodes.find(n => n.it.key === target), x = +n.r.getAttribute("x") + +n.r.getAttribute("width") / 2;
      const v = target === 2022 ? n.it.v : step >= 5 ? D.janapr_q75 : D.janapr_forecast;
      ann.setAttribute("x", Math.min(x, W() - 30)); ann.setAttribute("y", y(v) - 8); ann.textContent = pct(v, target === 2022 ? 1 : 2);
      ann.setAttribute("opacity", 1);
    } else ann.setAttribute("opacity", 0);
  }
  return { set, rebuild: () => { nodes = null; } };
}

/* Число, которое «досчитывается» один раз при загрузке */
function countUp(elm, to, d = 2, ms = 1400) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) { elm.textContent = num(to, d); return; }
  const t0 = performance.now();
  (function tick(t) {
    const k = Math.min(1, (t - t0) / ms), e = 1 - Math.pow(1 - k, 3);
    elm.textContent = num(to * e, d);
    if (k < 1) requestAnimationFrame(tick);
  })(t0);
}
