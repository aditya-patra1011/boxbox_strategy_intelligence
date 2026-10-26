/*
 * Race Live replay, run in the browser so the cars move smoothly.
 *
 * The server sends the session (lap start times, drivers, colours) once, and the car
 * samples one block at a time (rl-chunk). These two functions advance the replay clock
 * and redraw the cars and the speed ticker from that block, 4 times a second.
 */
window.dash_clientside = Object.assign({}, window.dash_clientside, {
  replay: {
    // Clock: play/pause, speed, lap slider and the 250 ms tick all land here.
    clock: function (tick, playClicks, rate, lapValue, clock, meta, chunkIndex) {
      const nu = window.dash_clientside.no_update;
      if (!meta) return [nu, nu, nu, nu, nu, nu];
      const trig = ((window.dash_clientside.callback_context.triggered || [])[0] || {}).prop_id || "";
      clock = Object.assign({ t: meta.t_start, playing: false }, clock || {});
      const lapOf = (t) => { // lap 1 also covers the formation lap before the start
        let lap = 1;
        for (const [l, s] of Object.entries(meta.lap_starts)) if (s <= t && +l > lap) lap = +l;
        return lap;
      };

      if (trig.startsWith("rl-play")) {
        if (clock.t >= meta.t_end) clock.t = meta.t_start; // replay again from the start
        clock.playing = !clock.playing;
      } else if (trig.startsWith("rl-lap") && lapValue != null && lapValue !== lapOf(clock.t)) {
        clock.t = meta.lap_starts[lapValue] ?? clock.t; // the user moved the slider
      } else if (trig.startsWith("rl-tick") && clock.playing) {
        clock.t = Math.min(clock.t + 0.25 * rate, meta.t_end);
      }
      if (clock.t >= meta.t_end) clock.playing = false;

      const lap = lapOf(clock.t);
      const need = Math.floor((clock.t + 30) / meta.chunk); // ask for the next block 30 s early
      return [
        clock,
        clock.playing ? "❚❚ Pause" : "▶ Play",
        !clock.playing,
        lap === lapValue ? nu : lap,
        need === chunkIndex ? nu : need,
        `Lap ${Math.max(lap, 1)} / ${meta.total_laps} · ${fmt(clock.t - meta.t_start)}`,
      ];
    },

    // Draw: cars on the track at the clock time, and the last 60 s of speed.
    draw: function (clock, chunk, chosen, meta, track, speed) {
      const nu = window.dash_clientside.no_update;
      if (!clock || !chunk || !meta || !track) return [nu, nu];
      const t = clock.t;
      const xs = [], ys = [], text = [], colours = [], sizes = [];
      for (const [num, d] of Object.entries(chunk)) {
        const p = at(d, t);
        if (!p) continue;
        const info = meta.drivers[num] || { code: num, colour: "#9A9CA5" };
        xs.push(p.x); ys.push(p.y); text.push(info.code); colours.push(info.colour);
        sizes.push((chosen || []).includes(+num) ? 17 : 12);
      }
      const cars = Object.assign({}, track.data[1], {
        x: xs, y: ys, text: text, hovertext: text,
        marker: Object.assign({}, track.data[1].marker, { color: colours, size: sizes }),
      });
      const newTrack = Object.assign({}, track, { data: [track.data[0], cars] });

      const lines = [];
      for (const num of chosen || []) {
        const d = chunk[num];
        if (!d) continue;
        const info = meta.drivers[num] || { code: num, colour: "#9A9CA5" };
        const x = [], y = [];
        for (let i = 0; i < d.t.length; i++) {
          if (d.t[i] < t - 60 || d.t[i] > t) continue;
          x.push(d.t[i] - meta.t_start); y.push(d.s[i]);
        }
        lines.push({ type: "scatter", mode: "lines", name: info.code, x: x, y: y,
                     line: { color: info.colour, width: 2 }, hovertemplate: "%{y} km/h<extra>" + info.code + "</extra>" });
      }
      const from = t - 60 - meta.t_start, to = t - meta.t_start;
      const laps = Object.entries(meta.lap_starts)
        .map(([l, s]) => [+l, s - meta.t_start]).filter(([, s]) => s >= from && s <= to);
      const layout = Object.assign({}, speed.layout, {
        xaxis: Object.assign({}, speed.layout.xaxis, { range: [from, to], tickvals: ticks(from, to), ticktext: ticks(from, to).map(fmt) }),
        shapes: laps.map(([, s]) => ({ type: "line", x0: s, x1: s, yref: "paper", y0: 0, y1: 1,
                                        line: { color: "#5A5C66", width: 1, dash: "dot" } })),
        annotations: laps.map(([l, s]) => ({ x: s, y: 1, yref: "paper", yanchor: "bottom", showarrow: false,
                                              text: "L" + l, font: { size: 10, color: "#9A9CA5" } })),
      });
      return [newTrack, Object.assign({}, speed, { data: lines, layout: layout })];
    },
  },
});

// Linear interpolation of one car's samples at time t (binary search; null outside the block).
function at(d, t) {
  const n = d.t.length;
  if (!n || t < d.t[0] - 1 || t > d.t[n - 1] + 1) return null;
  let lo = 0, hi = n - 1;
  while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (d.t[mid] <= t) lo = mid; else hi = mid; }
  const span = d.t[hi] - d.t[lo];
  if (span <= 0 || span > 3) return { x: d.x[lo], y: d.y[lo] }; // a gap in the data: hold the last place
  const f = Math.min(Math.max((t - d.t[lo]) / span, 0), 1);
  return { x: d.x[lo] + f * (d.x[hi] - d.x[lo]), y: d.y[lo] + f * (d.y[hi] - d.y[lo]) };
}

function fmt(s) {
  s = Math.max(0, Math.round(s));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  return (h ? h + ":" + String(m).padStart(2, "0") : m) + ":" + String(sec).padStart(2, "0");
}

function ticks(from, to) {
  const out = [];
  for (let v = Math.ceil(from / 15) * 15; v <= to; v += 15) out.push(v);
  return out;
}
