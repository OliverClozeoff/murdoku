"use strict";

/* ============================================================
   Murdoku — static web player. Puzzles come from puzzles/*.json
   (built by generator/build.py). Portraits come from avatar.js.
   ============================================================ */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const HOLD_MS = 300;
const SAVE_PREFIX = "murdoku:v2:";

const store = {
  get(key) {
    try { return JSON.parse(localStorage.getItem(SAVE_PREFIX + key)); } catch { return null; }
  },
  set(key, value) {
    try { localStorage.setItem(SAVE_PREFIX + key, JSON.stringify(value)); } catch { /* storage unavailable */ }
  },
};

/* ---------------- settings ---------------- */

const DEFAULTS = {
  theme: "auto", sound: true, haptics: true, anim: true, timer: true, autoX: true, blockX: true,
  token: "portrait", coords: false, plain: false, textures: true, zoomClues: true,
};
const settings = Object.assign({}, DEFAULTS, store.get("settings"));

const OPTIONS = [
  { key: "theme", label: "Theme", type: "select", choices: [["auto", "Match device"], ["light", "Light"], ["dark", "Dark"]] },
  { key: "sound", label: "Sound effects", help: "Sounds when placing characters and marks." },
  { key: "haptics", label: "Haptic feedback", help: "A tiny vibration when placing (phones only)." },
  { key: "anim", label: "Animations", help: "Board opening and placement effects." },
  { key: "timer", label: "Show timer" },
  { key: "autoX", label: "Auto-X on place", help: "Fill X's in the row and column of placed characters." },
  { key: "blockX", label: "No X on furniture", help: "X marks skip tables, plants and other blocking objects." },
  { key: "token", label: "Placed character style", type: "select", choices: [["portrait", "Portrait"], ["letter", "Letter"]] },
  { key: "coords", label: "Always show row & column numbers", help: "R1…Rn / C1…Cn around the grid (always on while a hint is open)." },
  { key: "plain", label: "Plain directions", help: "“north of” becomes “above”, “west of” becomes “to the left of”, and so on." },
  { key: "textures", label: "Floor textures" },
  { key: "zoomClues", label: "Zoom clue on hover", help: "Enlarge a card's text when the mouse is over it." },
];

function saveSettings() {
  store.set("settings", settings);
  applySettings();
}

function applySettings() {
  const root = document.documentElement;
  if (settings.theme === "auto") root.removeAttribute("data-theme");
  else root.dataset.theme = settings.theme;
  document.body.classList.toggle("no-anim", !settings.anim);
  document.body.classList.toggle("no-texture", !settings.textures);
  document.body.classList.toggle("zoom-clues", settings.zoomClues);
  els.timer.hidden = !settings.timer;
  $("#tool-sound").textContent = settings.sound ? "🔊" : "🔇";
  if (puzzle) {
    setCoords();
    buildCards();
    renderAll();
  }
}

/* ---------------- sound ---------------- */

const Sound = (() => {
  let ctx = null;
  function tone(freq, dur, { type = "sine", vol = 0.12, delay = 0, to = null } = {}) {
    if (!settings.sound) return;
    try {
      ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
      const t = ctx.currentTime + delay;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = type;
      osc.frequency.setValueAtTime(freq, t);
      if (to) osc.frequency.exponentialRampToValueAtTime(to, t + dur);
      gain.gain.setValueAtTime(vol, t);
      gain.gain.exponentialRampToValueAtTime(0.001, t + dur);
      osc.connect(gain).connect(ctx.destination);
      osc.start(t);
      osc.stop(t + dur + 0.02);
    } catch { /* audio unavailable */ }
  }
  return {
    place: () => tone(440, 0.12, { to: 880 }),
    lift: () => tone(660, 0.1, { to: 330 }),
    mark: () => tone(180, 0.05, { type: "square", vol: 0.05 }),
    note: () => tone(1200, 0.03, { vol: 0.04 }),
    wrong: () => { tone(300, 0.18, { type: "sawtooth", vol: 0.06 }); tone(220, 0.25, { type: "sawtooth", vol: 0.06, delay: 0.16 }); },
    win: () => [523, 659, 784, 1047].forEach((f, i) => tone(f, 0.22, { delay: i * 0.11, vol: 0.1 })),
  };
})();

function buzz(pattern) {
  if (settings.haptics && navigator.vibrate) navigator.vibrate(pattern);
}

/* ---------------- globals ---------------- */

let index = [];          // case list
let puzzle = null;       // current puzzle json
let secret = null;       // {cells, murderer, motive, hints}
let state = null;        // player progress (see freshState)
let selected = null;     // selected person index
let tool = "note";       // "note" | "x" | "erase"
let history = [];
let timerId = null;
let gesture = null;
let hintIdx = null;      // open hint, or null
let justPlaced = -1;     // cell index to animate

const els = {
  home: $("#home"), game: $("#game"), list: $("#case-list"), board: $("#board"), wrap: $("#board-wrap"),
  cards: $("#cards"), facts: $("#facts"), timer: $("#timer"), title: $("#case-title"), meta: $("#case-meta"),
  toast: $("#toast"), tooltip: $("#tooltip"), result: $("#result"), help: $("#help"), options: $("#options"),
  tutorial: $("#tutorial"), hint: $("#hint-panel"), submit: $("#tool-submit"),
};

/* ---------------- text helpers ---------------- */

const esc = s => s.replace(/[&<>"]/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[ch]);
const PLAIN = { north: "above", south: "below", west: "to the left of", east: "to the right of" };

function fmt(text) {
  let t = esc(text);
  if (settings.plain) {
    t = t.replace(/\b(north|south|west|east) of\b/g, (_, d) => PLAIN[d])
      .replace(/westernmost/g, "leftmost").replace(/easternmost/g, "rightmost");
  }
  return t.replace(/\*([^*]+)\*/g, "<b>$1</b>");
}

// Fingerprint of a case's floor plan. Saves are tied to it, so regenerating the
// puzzles never loads old progress into a different case with the same number.
function sigOf(grid) {
  let h = 2166136261;
  for (const ch of JSON.stringify(grid)) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  return (h >>> 0).toString(36);
}
function loadSave(id, grid) {
  const saved = store.get(id);
  return saved && saved.sig === sigOf(grid) ? saved : null;
}

const fmtTime = s => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

/* ---------------- routing & home ---------------- */

async function boot() {
  applySettings();
  try {
    index = await (await fetch("puzzles/index.json", { cache: "no-cache" })).json();
  } catch {
    els.list.innerHTML = `<p class="muted">Couldn't load puzzles. If you opened this file directly, serve the folder instead (e.g. <code>py -m http.server</code>).</p>`;
    return;
  }
  window.addEventListener("hashchange", route);
  route();
  if (!store.get("seen-tutorial")) openTutorial();
}

function route() {
  closeHint();
  if (els.result.open) els.result.close();
  const id = location.hash.slice(1);
  if (id && index.some(p => p.id === id)) openCase(id);
  else showHome();
}

function showHome() {
  stopTimer();
  puzzle = null;
  els.game.hidden = true;
  els.home.hidden = false;
  document.title = "Murdoku";
  els.list.innerHTML = "";
  for (const p of index) {
    const saved = p.grid ? loadSave(p.id, p.grid) : null;
    const a = document.createElement("a");
    a.className = "case-card";
    a.href = "#" + p.id;
    const mini = p.grid
      ? `<div class="mini" style="grid-template-columns:repeat(${p.size},1fr)">${p.grid.flat().map((room, i) =>
        `<i class="${p.blocked.includes(i) ? "b" : ""}" style="background:${p.colors[room]}"></i>`).join("")}</div>`
      : "";
    a.innerHTML = `
      <h3><span>${esc(p.title)}</span>${saved?.solved ? '<span class="solved">✓ solved</span>' : ""}</h3>
      ${mini}
      <div class="meta"><span class="pill ${p.difficulty}">${p.difficulty}</span>${p.size}×${p.size} · ${p.rooms.length} rooms</div>`;
    els.list.append(a);
  }
}

async function openCase(id) {
  puzzle = await (await fetch(`puzzles/${id}.json`, { cache: "no-cache" })).json();
  secret = JSON.parse(atob(puzzle.secret));
  state = Object.assign(freshState(), loadSave(id, puzzle.grid) || {});
  history = [];
  selected = puzzle.people.findIndex((_, i) => !state.pos[i]);
  if (selected < 0) selected = null;
  setTool("note");

  els.home.hidden = true;
  els.game.hidden = false;
  document.title = `${puzzle.title} · Murdoku`;
  els.title.textContent = puzzle.title;
  els.meta.textContent = `${puzzle.size}×${puzzle.size} · ${puzzle.difficulty}`;
  buildBoard();
  buildCards();
  setCoords();
  setStamp(state.solved);
  renderAll();
  startTimer();
  window.scrollTo(0, 0);
  if (settings.anim) {
    els.board.classList.add("opening");
    setTimeout(() => els.board.classList.remove("opening"), 900);
  }
}

function freshState() {
  const n = puzzle.size;
  return {
    pos: Array(puzzle.people.length).fill(null),   // person -> [r, c]
    notes: Array.from({ length: n * n }, () => []), // cell -> person indices
    x: Array(n * n).fill(false),                    // manual X marks
    struck: [],                                     // crossed-off people
    seconds: 0,
    solved: false,
    revealed: false,
    hintsUsed: 0,
  };
}

/* ---------------- board ---------------- */

let cellEls = [];
let objectAt = [];  // cell -> object index or -1
let roomLabels = [];

const idx = (r, c) => r * puzzle.size + c;
const rcOf = i => [Math.floor(i / puzzle.size), i % puzzle.size];
const roomAt = (r, c) => puzzle.grid[r][c];
const isBlocked = i => objectAt[i] >= 0 && !puzzle.objects[objectAt[i]].occupiable;

function buildBoard() {
  const n = puzzle.size;
  const b = els.board;
  b.innerHTML = "";
  els.wrap.style.setProperty("--n", n);
  cellEls = [];
  objectAt = Array(n * n).fill(-1);
  puzzle.objects.forEach((o, k) => o.cells.forEach(([r, c]) => (objectAt[idx(r, c)] = k)));

  for (let r = 0; r < n; r++) {
    for (let c = 0; c < n; c++) {
      const i = idx(r, c);
      const room = puzzle.rooms[roomAt(r, c)];
      const cell = document.createElement("div");
      cell.className = "cell floor-" + (room.floor || "planks");
      cell.dataset.i = i;
      cell.style.backgroundColor = room.color;
      cell.style.setProperty("--d", r + c);

      // thick walls where the room changes
      const W = "var(--wall)", t = "calc(var(--cell) * .07 + 1px)";
      const shadows = [];
      if (r > 0 && roomAt(r - 1, c) !== roomAt(r, c)) shadows.push(`inset 0 ${t} 0 ${W}`);
      if (r < n - 1 && roomAt(r + 1, c) !== roomAt(r, c)) shadows.push(`inset 0 calc(-1 * ${t}) 0 ${W}`);
      if (c > 0 && roomAt(r, c - 1) !== roomAt(r, c)) shadows.push(`inset ${t} 0 0 ${W}`);
      if (c < n - 1 && roomAt(r, c + 1) !== roomAt(r, c)) shadows.push(`inset calc(-1 * ${t}) 0 0 ${W}`);
      if (shadows.length) cell.insertAdjacentHTML("beforeend", `<div class="walls" style="box-shadow:${shadows.join(",")}"></div>`);

      const k = objectAt[i];
      if (k >= 0) {
        const o = puzzle.objects[k];
        const tile = document.createElement("div");
        tile.className = "obj " + (o.type === "carpet" || o.type === "pond" ? o.type : o.occupiable ? "open" : "block");
        for (const [dr, dc, side] of [[-1, 0, "top"], [1, 0, "bottom"], [0, -1, "left"], [0, 1, "right"]]) {
          const rr = r + dr, cc = c + dc;
          if (rr >= 0 && rr < n && cc >= 0 && cc < n && objectAt[idx(rr, cc)] === k) tile.style[side] = "-1px";
        }
        const first = o.cells[0][0] === r && o.cells[0][1] === c;
        if (first) {
          tile.classList.add("head");
          if (o.cells.length > 1) {
            // stretch the head tile over the whole object so it reads as one piece
            const [r2, c2] = o.cells[o.cells.length - 1];
            tile.style.right = `calc(${-(c2 - c) * 100}% + 8%)`;
            tile.style.bottom = `calc(${-(r2 - r) * 100}% + 8%)`;
          }
          if (o.icon) tile.innerHTML = `<span class="icon">${o.icon}</span>`;
        } else if (o.cells.length > 1) {
          tile.classList.add("tail");  // covered by the head tile
        }
        cell.append(tile);
        if (!o.occupiable) cell.classList.add("blocked");
      }
      b.append(cell);
      cellEls.push(cell);
    }
  }

  // Room names sit along the bottom edge of each room, centered on its longest bottom run.
  roomLabels = puzzle.rooms.map((room, ri) => {
    let best = null;
    for (let r = n - 1; r >= 0 && !best; r--) {
      let c = 0;
      while (c < n) {
        if (roomAt(r, c) !== ri) { c++; continue; }
        let end = c;
        while (end < n && roomAt(r, end) === ri) end++;
        if (!best || end - c > best[2] - best[1]) best = [r, c, end];
        c = end;
      }
    }
    const [r, c0, c1] = best;
    const label = document.createElement("div");
    label.className = "room-label";
    label.textContent = room.name;
    label.style.top = `${((r + 1) / n) * 100}%`;
    label.style.left = `${(c0 / n) * 100}%`;
    label.style.width = `${((c1 - c0) / n) * 100}%`;
    b.append(label);
    return label;
  });

  $("#col-labels").innerHTML = Array.from({ length: n }, (_, c) => `<span>C${c + 1}</span>`).join("");
  $("#row-labels").innerHTML = Array.from({ length: n }, (_, r) => `<span>R${r + 1}</span>`).join("");
}

function setCoords() {
  els.wrap.classList.toggle("coords", settings.coords || hintIdx !== null);
}

/* ---------------- cards ---------------- */

function buildCards() {
  buildPicker();
  els.facts.innerHTML = (puzzle.facts || []).map(f => `<div class="fact">${fmt(f.text)}</div>`).join("");
  els.cards.innerHTML = "";
  puzzle.people.forEach((p, k) => {
    const card = document.createElement("div");
    card.className = "card" + (p.victim ? " victim" : "");
    card.dataset.k = k;
    const lines = p.victim
      ? [`<p><b>The victim.</b> ${p.gender === "f" ? "She" : "He"} was <b>alone with</b> the murderer.</p>`]
      : [];
    for (const cl of p.clues) lines.push(`<p>${fmt(cl.text)}</p>`);
    if (!lines.length) lines.push(`<p class="none">No statement.</p>`);
    card.innerHTML = `
      <span class="badge">${p.letter}</span>
      <div class="portrait">${Avatar.svg(p)}<span class="nameplate">${esc(p.name)}</span></div>
      <div class="clue-box">${lines.join("")}</div>`;
    els.cards.append(card);

    // tap = select, press & hold = cross off
    let t = 0, held = false;
    card.addEventListener("pointerdown", () => {
      held = false;
      t = setTimeout(() => {
        held = true;
        const s = state.struck;
        s.includes(k) ? s.splice(s.indexOf(k), 1) : s.push(k);
        buzz(10);
        save();
        renderCards();
      }, 550);
    });
    const cancel = () => clearTimeout(t);
    card.addEventListener("pointerup", cancel);
    card.addEventListener("pointerleave", () => { cancel(); clearRefs(); });
    card.addEventListener("click", () => { if (!held) select(k); });
    card.addEventListener("pointerenter", e => { if (e.pointerType === "mouse") showRefs(k); });
    card.addEventListener("contextmenu", e => e.preventDefault());
  });
}

function buildPicker() {
  const picker = $("#picker");
  picker.innerHTML = "";
  puzzle.people.forEach((p, k) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "pick" + (p.victim ? " victim" : "");
    b.title = p.name;
    b.innerHTML = `${Avatar.svg(p, { crop: true })}<b>${p.letter}</b>`;
    b.addEventListener("click", () => select(k));
    picker.append(b);
  });
}

function renderCards() {
  $$(".pick").forEach((b, k) => {
    b.setAttribute("aria-pressed", k === selected);
    b.classList.toggle("placed", !!state.pos[k]);
  });
  $$(".card", els.cards).forEach((card, k) => {
    card.classList.toggle("selected", k === selected);
    card.classList.toggle("placed", !!state.pos[k]);
    card.classList.toggle("struck", state.struck.includes(k));
  });
}

function select(k) {
  selected = k;  // clicking the selected card again keeps it selected, like the original
  renderCards();
  renderBoard();
  if (selected !== null) $("#hint-line").innerHTML = `<b>${esc(puzzle.people[selected].name)}</b> selected: tap a square for a note, <b>press &amp; hold</b> to place.`;
}

/* ---------------- highlighting what a clue mentions ---------------- */

function showRefs(k) {
  clearRefs();
  const refs = { rooms: new Set(), objects: new Set(), people: new Set(), rows: new Set(), cols: new Set() };
  for (const cl of puzzle.people[k].clues) {
    for (const key of Object.keys(refs)) (cl.refs?.[key] || []).forEach(v => refs[key].add(v));
  }
  cellEls.forEach((cell, i) => {
    const [r, c] = rcOf(i);
    if (refs.rooms.has(roomAt(r, c))) cell.classList.add("ref-room");
    if (objectAt[i] >= 0 && refs.objects.has(puzzle.objects[objectAt[i]].type)) cell.classList.add("ref-obj");
    if (refs.rows.has(r) || refs.cols.has(c)) cell.classList.add("ref-line");
  });
  for (const q of refs.people) {
    $(`.card[data-k="${q}"]`, els.cards)?.classList.add("ref");
    const p = state.pos[q];
    if (p) cellEls[idx(p[0], p[1])].classList.add("ref-person");
  }
}

function clearRefs() {
  $$(".ref-room,.ref-obj,.ref-line,.ref-person", els.board).forEach(e => e.classList.remove("ref-room", "ref-obj", "ref-line", "ref-person"));
  $$(".card.ref", els.cards).forEach(e => e.classList.remove("ref"));
}

/* ---------------- rendering ---------------- */

function renderAll() {
  renderBoard();
  renderCards();
}

function renderBoard() {
  const n = puzzle.size;
  const people = puzzle.people;
  const occupant = Array(n * n).fill(-1);
  const rowCount = Array(n).fill(0), colCount = Array(n).fill(0);
  state.pos.forEach((p, k) => {
    if (!p) return;
    occupant[idx(p[0], p[1])] = k;
    rowCount[p[0]]++;
    colCount[p[1]]++;
  });

  for (let i = 0; i < n * n; i++) {
    const [r, c] = rcOf(i);
    const cell = cellEls[i];
    cell.querySelectorAll(".token,.token-letter,.x,.notes").forEach(e => e.remove());
    const who = occupant[i];
    const blocked = isBlocked(i);

    if (who >= 0) {
      const p = people[who];
      const t = document.createElement("div");
      t.className = "token" + (p.victim ? " victim" : "");
      t.style.setProperty("--k", who);
      if (rowCount[r] > 1 || colCount[c] > 1) t.classList.add("conflict");
      if (state.revealed) t.classList.add("reveal");
      if (i === justPlaced) t.classList.add("pop");
      if (settings.token === "portrait") {
        t.innerHTML = Avatar.svg(p, { crop: true });
        cell.append(t);
        cell.insertAdjacentHTML("beforeend", `<span class="token-letter${p.victim ? " victim" : ""}">${p.letter}</span>`);
      } else {
        t.textContent = p.letter;
        cell.append(t);
      }
    } else if (state.x[i] && !(blocked && settings.blockX)) {
      cell.insertAdjacentHTML("beforeend", `<div class="x">✕</div>`);
    } else if (state.notes[i].length) {
      const box = document.createElement("div");
      box.className = "notes";
      for (const k of state.notes[i]) {
        const s = document.createElement("span");
        s.textContent = people[k].letter;
        s.style.gridArea = `${Math.floor(k / 3) % 3 + 1} / ${(k % 3) + 1}`;
        if (people[k].victim) s.classList.add("victim");
        if (k === selected) s.classList.add("sel");
        box.append(s);
      }
      cell.append(box);
    }
  }
  justPlaced = -1;
  const allPlaced = state.pos.every(Boolean);
  els.submit.disabled = !allPlaced || state.solved || state.revealed;
}

/* ---------------- actions ---------------- */

function snapshot() {
  history.push(JSON.stringify(state));
  if (history.length > 300) history.shift();
}

function save() {
  store.set(puzzle.id, Object.assign({}, state, { sig: sigOf(puzzle.grid) }));
}

function locked() {
  if (state.solved || state.revealed) {
    toast("This case is closed.");
    return true;
  }
  return false;
}

function occupantOf(i) {
  return state.pos.findIndex(p => p && idx(p[0], p[1]) === i);
}

function needSelection() {
  if (selected !== null) return false;
  toast("Select a character first.");
  return true;
}

function placeAt(k, i) {
  const n = puzzle.size;
  const cur = state.pos[k];
  if (cur && idx(cur[0], cur[1]) === i) {
    state.pos[k] = null;  // hold again = pick back up
    Sound.lift();
  } else {
    const other = occupantOf(i);
    if (other >= 0) state.pos[other] = null;
    const [r, c] = [Math.floor(i / n), i % n];
    state.pos[k] = [r, c];
    state.x[i] = false;
    if (settings.autoX) {
      for (let t = 0; t < n; t++) {
        for (const j of [idx(r, t), idx(t, c)]) {
          if (j !== i && occupantOf(j) < 0 && !(isBlocked(j) && settings.blockX)) state.x[j] = true;
        }
      }
    }
    justPlaced = i;
    Sound.place();
    buzz(15);
  }
}

function place(i) {
  if (needSelection()) return;
  snapshot();
  placeAt(selected, i);
  // after placing, move the selection on to the next unplaced character
  if (state.pos[selected]) {
    const next = puzzle.people.findIndex((_, k) => !state.pos[k]);
    if (next >= 0) selected = next;
  }
  afterChange();
  if (state.pos.every(Boolean)) toast("Everyone's placed. Press Submit when you're sure.");
}

// Paint value decided from the first square of a tap/drag, then applied to every square touched.
function paintValue(i) {
  if (tool === "erase") return null;
  if (tool === "x") return !state.x[i];
  return !state.notes[i].includes(selected);
}

function paint(i, value) {
  if (isBlocked(i) && (tool !== "x" || settings.blockX)) return;
  if (tool === "erase") {
    const who = occupantOf(i);
    if (who >= 0) state.pos[who] = null;
    state.notes[i] = [];
    state.x[i] = false;
  } else if (occupantOf(i) >= 0) {
    return;
  } else if (tool === "x") {
    state.x[i] = value;
  } else {
    const notes = state.notes[i].filter(k => k !== selected);
    if (value) notes.push(selected);
    state.notes[i] = notes.sort((a, b) => a - b);
  }
}

function afterChange() {
  save();
  renderBoard();
  renderCards();
  if (hintIdx !== null) showHint(hintIdx);
}

function submit() {
  if (state.pos.some(p => !p) || locked()) return;
  const wrong = state.pos.filter((p, k) => p[0] !== secret.cells[k][0] || p[1] !== secret.cells[k][1]).length;
  if (wrong) {
    Sound.wrong();
    buzz([40, 60, 40]);
    els.board.animate([{ transform: "translateX(0)" }, { transform: "translateX(-8px)" }, { transform: "translateX(8px)" }, { transform: "translateX(0)" }], { duration: 300 });
    toast(wrong === 1 ? "Close! One person is in the wrong place." : `Not quite. ${wrong} people are in the wrong place.`);
    return;
  }
  state.solved = true;
  save();
  stopTimer();
  closeHint();
  renderBoard();
  Sound.win();
  buzz([30, 60, 30]);
  const stampAt = puzzle.people.length * 90 + 250;  // after the last portrait has been ringed
  els.wrap.style.setProperty("--stamp-delay", `${stampAt}ms`);
  els.wrap.classList.add("solving");
  setStamp(true);
  setTimeout(() => {
    els.wrap.classList.remove("solving");
    if (puzzle && state.solved) showResult(true);
  }, settings.anim ? stampAt + 1300 : 300);
}

function setStamp(on) {
  els.wrap.querySelector(".stamp")?.remove();
  els.wrap.classList.toggle("solved", on);
  if (on) els.wrap.insertAdjacentHTML("beforeend", `<div class="stamp"><span>CASE<br>SOLVED</span></div>`);
}

function showResult(won) {
  const m = puzzle.people[secret.murderer];
  const vi = puzzle.people.findIndex(p => p.victim);
  const v = puzzle.people[vi];
  const [r, c] = secret.cells[vi];
  const room = puzzle.rooms[roomAt(r, c)].name;
  $("#result-icon").textContent = won ? "🏆" : "🔎";
  $("#result-title").textContent = won ? "Case closed!" : "The answer";
  const figure = p => `<figure><div class="portrait">${Avatar.svg(p)}</div><figcaption>${esc(p.name)}${p.victim ? " (victim)" : ""}</figcaption></figure>`;
  const lead = won
    ? `<p>You've found the murderer! <b>${esc(m.name)}</b> (${m.letter}) killed <b>${esc(v.name)}</b> (${v.letter}) in the ${esc(room)}.</p>`
    : `<p><b>${esc(m.name)}</b> was alone with <b>${esc(v.name)}</b> in the ${esc(room)}.</p>`;
  const stats = won
    ? `<p class="muted">Solved in ${fmtTime(state.seconds)}${state.hintsUsed ? ` with ${state.hintsUsed} hint${state.hintsUsed > 1 ? "s" : ""}` : " without hints"}.</p>`
    : "";
  $("#result-text").innerHTML = `
    <div class="culprit">${figure(m)}${figure(v)}</div>
    ${lead}
    ${secret.motive ? `<div class="motive">${esc(secret.motive)}</div>` : ""}
    ${stats}`;
  const next = index[index.findIndex(p => p.id === puzzle.id) + 1];
  $("#result-next").hidden = !next;
  $("#result-next").onclick = () => { els.result.close(); location.hash = next.id; };
  els.result.showModal();
}

/* ---------------- board pointer input ---------------- */

function cellIndexAt(x, y) {
  const el = document.elementFromPoint(x, y)?.closest(".cell");
  return el && els.board.contains(el) ? Number(el.dataset.i) : null;
}

els.board.addEventListener("pointerdown", e => {
  if ((e.button !== 0 && e.button !== 2) || !puzzle) return;
  const i = cellIndexAt(e.clientX, e.clientY);
  if (i === null || isBlocked(i)) return;
  e.preventDefault();
  els.board.setPointerCapture(e.pointerId);
  hideTooltip();
  gesture = { start: i, last: i, dragged: false, held: false, value: null, timer: 0, restore: null };
  if (e.button === 2) {
    gesture.restore = tool;  // right button always marks X, whatever tool is active
    tool = "x";
  } else if (tool !== "erase") {
    gesture.timer = setTimeout(() => {
      if (!gesture || gesture.dragged || locked()) return;
      gesture.held = true;
      place(i);
    }, HOLD_MS);
  }
});

els.board.addEventListener("pointermove", e => {
  if (!gesture) {
    if (e.pointerType === "mouse") hoverCell(cellIndexAt(e.clientX, e.clientY));
    return;
  }
  if (gesture.held) return;
  const i = cellIndexAt(e.clientX, e.clientY);
  if (i === null || i === gesture.last) return;
  if (!gesture.dragged) {
    clearTimeout(gesture.timer);
    if (locked() || (tool === "note" && needSelection())) { gesture = null; return; }
    gesture.dragged = true;
    snapshot();
    gesture.value = paintValue(gesture.start);
    paint(gesture.start, gesture.value);
  }
  paint(i, gesture.value);
  gesture.last = i;
  renderBoard();
});

function endGesture() {
  if (!gesture) return;
  const g = gesture;
  try { finishGesture(g); } finally { if (g.restore) tool = g.restore; }
}

function finishGesture(g) {
  clearTimeout(g.timer);
  gesture = null;
  if (g.held) return;
  if (g.dragged) { afterChange(); return; }
  // plain tap
  const who = occupantOf(g.start);
  if (who >= 0 && tool === "note") { select(who); return; }
  if (locked() || (tool === "note" && needSelection())) return;
  snapshot();
  paint(g.start, paintValue(g.start));
  tool === "x" ? Sound.mark() : Sound.note();
  afterChange();
}
els.board.addEventListener("pointerup", endGesture);
els.board.addEventListener("pointercancel", () => {
  if (!gesture) return;
  clearTimeout(gesture.timer);
  if (gesture.restore) tool = gesture.restore;
  gesture = null;
});
els.board.addEventListener("pointerleave", () => hoverCell(null));
els.board.addEventListener("contextmenu", e => e.preventDefault());
// Mouse shortcut: double-click places the selected character. The two clicks before it
// toggled a note on and off again, so the board is otherwise unchanged.
els.board.addEventListener("dblclick", e => {
  if (!puzzle || tool !== "note") return;
  const i = cellIndexAt(e.clientX, e.clientY);
  if (i === null || isBlocked(i) || locked()) return;
  history.splice(-2);  // forget the two note toggles so Undo removes the placement in one step
  place(i);
});

let hoverRoom = -1;
function hoverCell(i) {
  const room = i === null ? -1 : roomAt(...rcOf(i));
  if (room !== hoverRoom) {
    hoverRoom = room;
    cellEls.forEach((cell, j) => cell.classList.toggle("room-hover", room >= 0 && roomAt(...rcOf(j)) === room));
    roomLabels.forEach((l, ri) => l.classList.toggle("hover", ri === room));
  }
  if (i === null || objectAt[i] < 0) return hideTooltip();
  const o = puzzle.objects[objectAt[i]];
  els.tooltip.textContent = o.name[0].toUpperCase() + o.name.slice(1);
  const rect = cellEls[i].getBoundingClientRect();
  els.tooltip.style.left = `${rect.left + rect.width / 2}px`;
  els.tooltip.style.top = `${rect.top - 4}px`;
  els.tooltip.hidden = false;
}
function hideTooltip() { els.tooltip.hidden = true; }

/* ---------------- tools ---------------- */

function setTool(t) {
  tool = t;
  $("#tool-x").setAttribute("aria-pressed", t === "x");
  $("#tool-erase").setAttribute("aria-pressed", t === "erase");
}

$("#tool-x").addEventListener("click", () => setTool(tool === "x" ? "note" : "x"));

// Eraser: click toggles the tool, holding the button wipes the whole board.
(() => {
  const btn = $("#tool-erase");
  let t = 0, fired = false;
  btn.addEventListener("pointerdown", () => {
    fired = false;
    t = setTimeout(() => {
      fired = true;
      if (locked()) return;
      snapshot();
      const keep = { struck: state.struck, seconds: state.seconds, hintsUsed: state.hintsUsed };
      state = Object.assign(freshState(), keep);
      buzz(30);
      afterChange();
      toast("Board cleared. Undo brings it back.");
    }, 700);
  });
  const cancel = () => clearTimeout(t);
  btn.addEventListener("pointerup", cancel);
  btn.addEventListener("pointerleave", cancel);
  btn.addEventListener("click", () => { if (!fired) setTool(tool === "erase" ? "note" : "erase"); });
})();

$("#tool-undo").addEventListener("click", () => {
  if (!history.length) return toast("Nothing to undo.");
  if (state.solved) return toast("This case is closed.");
  const { seconds, hintsUsed } = state;
  state = JSON.parse(history.pop());
  Object.assign(state, { seconds, hintsUsed });
  afterChange();
});

$("#tool-submit").addEventListener("click", submit);
$("#tool-hint").addEventListener("click", () => (hintIdx === null ? openHint() : closeHint()));

$("#tool-share").addEventListener("click", async () => {
  const url = location.href;
  try {
    if (navigator.share) await navigator.share({ title: "Murdoku: " + puzzle.title, url });
    else { await navigator.clipboard.writeText(url); toast("Link copied."); }
  } catch { /* cancelled */ }
});

$("#tool-sound").addEventListener("click", () => {
  settings.sound = !settings.sound;
  saveSettings();
  toast(settings.sound ? "Sound on" : "Sound off");
});

$("#tool-reveal").addEventListener("click", () => {
  if (state.solved) return showResult(true);
  if (!state.revealed && !confirm("Give up and show the solution?")) return;
  snapshot();
  state.revealed = true;
  state.pos = secret.cells.map(c => [...c]);
  stopTimer();
  closeHint();
  afterChange();
  showResult(false);
});

document.addEventListener("keydown", e => {
  if (!puzzle || els.game.hidden || e.target.closest("dialog")) return;
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") { e.preventDefault(); $("#tool-undo").click(); return; }
  if (e.key === "Escape") { closeHint(); return; }
  const k = puzzle.people.findIndex(p => p.letter.toLowerCase() === e.key.toLowerCase());
  if (k >= 0 && !e.ctrlKey && !e.metaKey && !e.altKey) select(k);
});

/* ---------------- hints ---------------- */

function openHint() {
  if (state.solved || state.revealed) return toast("This case is closed.");
  const steps = secret.hints || [];
  if (!steps.length) return toast("No hints for this case.");
  // start at the first step the board doesn't already satisfy
  let i = steps.findIndex(s => !(state.pos[s.person] && state.pos[s.person][0] === s.cell[0] && state.pos[s.person][1] === s.cell[1]));
  if (i < 0) i = steps.length - 1;
  showHint(i);
}

function showHint(i) {
  const steps = secret.hints;
  hintIdx = Math.max(0, Math.min(steps.length - 1, i));
  const s = steps[hintIdx];
  els.hint.hidden = false;
  $("#hint-count").textContent = `Hint ${hintIdx + 1}/${steps.length}`;
  $("#hint-text").innerHTML = fmt(s.text);
  $("#hint-prev").disabled = hintIdx === 0;
  $("#hint-next").disabled = hintIdx === steps.length - 1;
  const done = state.pos[s.person]?.[0] === s.cell[0] && state.pos[s.person]?.[1] === s.cell[1];
  $("#hint-apply").hidden = done;
  clearHintMarks();
  cellEls[idx(s.cell[0], s.cell[1])].classList.add("hint-target");
  for (const [r, c] of s.marks || []) cellEls[idx(r, c)].classList.add("hint-mark");
  setCoords();
}

function clearHintMarks() {
  $$(".hint-target,.hint-mark", els.board).forEach(e => e.classList.remove("hint-target", "hint-mark"));
}

function closeHint() {
  if (hintIdx === null) return;
  hintIdx = null;
  els.hint.hidden = true;
  if (puzzle) {
    clearHintMarks();
    setCoords();
  }
}

$("#hint-close").addEventListener("click", closeHint);
$("#hint-prev").addEventListener("click", () => showHint(hintIdx - 1));
$("#hint-next").addEventListener("click", () => showHint(hintIdx + 1));
$("#hint-apply").addEventListener("click", () => {
  if (locked()) return;
  const s = secret.hints[hintIdx];
  snapshot();
  state.hintsUsed++;
  placeAt(s.person, idx(s.cell[0], s.cell[1]));
  afterChange();
});

/* ---------------- tutorial ---------------- */

const demo = (cols, cells) => `<div class="tut-demo" style="grid-template-columns:repeat(${cols},30px)">${cells.map(c => {
  const cls = { A: "p", "✓": "ok", "✗": "no" }[c] || "";
  return `<i class="${cls}">${c === "." ? "" : c}</i>`;
}).join("")}</div>`;

const TUTORIAL = [
  ["🔎", "Welcome, detective", "There's been a murder. One of these people did it. The statements tell you who was where. Here's how it works."],
  ["🧩", "How to solve a case", "The victim was alone with the murderer. Work out exactly where every character was standing. Each card shows that character's statement."],
  ["⚠️", "One per row & column", "Each row and each column holds exactly one character. When you place someone, X's fill their row and column automatically."
    + demo(5, [".", ".", "✕", ".", ".", "✕", "✕", "A", "✕", "✕", ".", ".", "✕", ".", "."])],
  ["🧭", "What “beside” means", "Directly left, right, above or below, <b>and</b> in the same room. A wall in between means they're not beside each other."
    + demo(3, [".", "✓", ".", "✓", "A", "✗", ".", "✓", "."])],
  ["👆", "Placing characters", "First tap a character card. Then <b>press and hold</b> a square until their portrait appears. A quick tap only leaves a small pencil note."],
  ["🏆", "Crack the case", "Once everyone is placed, press <b>Submit</b> to check your answer. Stuck? <b>Hint</b> walks you through the next logical step."],
];
let tutStep = 0;

function openTutorial() {
  tutStep = 0;
  renderTutorial();
  els.tutorial.showModal();
}
function renderTutorial() {
  const [icon, title, body] = TUTORIAL[tutStep];
  $("#tut-step").textContent = `${String(tutStep + 1).padStart(2, "0")} / ${String(TUTORIAL.length).padStart(2, "0")}`;
  $("#tut-body").innerHTML = `<div class="big-icon">${icon}</div><h2>${title}</h2><div>${body}</div>`;
  $("#tut-dots").innerHTML = TUTORIAL.map((_, i) => `<i class="${i === tutStep ? "on" : ""}"></i>`).join("");
  $("#tut-back").hidden = tutStep === 0;
  $("#tut-next").textContent = tutStep === TUTORIAL.length - 1 ? "Let's play!" : "Next";
}
function closeTutorial() {
  store.set("seen-tutorial", true);
  els.tutorial.close();
}
$("#tut-next").addEventListener("click", () => {
  if (tutStep === TUTORIAL.length - 1) return closeTutorial();
  tutStep++;
  renderTutorial();
});
$("#tut-back").addEventListener("click", () => { tutStep = Math.max(0, tutStep - 1); renderTutorial(); });
$("#tut-skip").addEventListener("click", closeTutorial);
$("#tut-close").addEventListener("click", closeTutorial);

/* ---------------- help & options dialogs ---------------- */

$$("[data-open]").forEach(b => b.addEventListener("click", () => {
  const d = $("#" + b.dataset.open);
  if (d === els.options) renderOptions();
  d.showModal();
}));
$$("[data-close]").forEach(b => b.addEventListener("click", () => b.closest("dialog").close()));
for (const d of $$("dialog")) {
  d.addEventListener("click", e => { if (e.target === d) d === els.tutorial ? closeTutorial() : d.close(); });
}
els.help.querySelectorAll("[role=tab]").forEach(tab => tab.addEventListener("click", () => {
  els.help.querySelectorAll("[role=tab]").forEach(t => t.setAttribute("aria-selected", t === tab));
  els.help.querySelectorAll(".tab-panel").forEach(p => (p.hidden = p.dataset.panel !== tab.dataset.tab));
}));

function renderOptions() {
  const list = $("#opt-list");
  list.innerHTML = "";
  for (const o of OPTIONS) {
    const row = document.createElement("label");
    row.className = "opt";
    const text = `<span><b>${o.label}</b>${o.help ? `<small>${o.help}</small>` : ""}</span>`;
    if (o.type === "select") {
      row.innerHTML = `${text}<select>${o.choices.map(([v, l]) => `<option value="${v}"${settings[o.key] === v ? " selected" : ""}>${l}</option>`).join("")}</select>`;
      row.querySelector("select").addEventListener("change", e => { settings[o.key] = e.target.value; saveSettings(); });
    } else {
      row.innerHTML = `${text}<span class="switch"><input type="checkbox"${settings[o.key] ? " checked" : ""}><span></span></span>`;
      row.querySelector("input").addEventListener("change", e => { settings[o.key] = e.target.checked; saveSettings(); });
    }
    list.append(row);
  }
  const replay = document.createElement("div");
  replay.className = "opt";
  replay.innerHTML = `<span><b>Tutorial</b></span><button class="btn ghost small" type="button">Show again</button>`;
  replay.querySelector("button").addEventListener("click", () => { els.options.close(); openTutorial(); });
  list.append(replay);
}

/* ---------------- timer & toast ---------------- */

function startTimer() {
  stopTimer();
  els.timer.textContent = fmtTime(state.seconds);
  if (state.solved || state.revealed) return;
  timerId = setInterval(() => {
    if (document.hidden || $$("dialog[open]").length) return;
    state.seconds++;
    els.timer.textContent = fmtTime(state.seconds);
    if (state.seconds % 10 === 0) save();
  }, 1000);
}
function stopTimer() { clearInterval(timerId); timerId = null; }

let toastTimer = 0;
function toast(msg) {
  els.toast.textContent = msg;
  els.toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => els.toast.classList.remove("show"), 2400);
}

boot();
