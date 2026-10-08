"use strict";

/* ============================================================
   Murdoku — static web player. Puzzles come from puzzles/*.json
   (built by generator/build.py).
   ============================================================ */

const $ = (sel, root = document) => root.querySelector(sel);
const HOLD_MS = 380;
const SAVE_PREFIX = "murdoku:v1:";

const store = {
  get(key) {
    try { return JSON.parse(localStorage.getItem(SAVE_PREFIX + key)); } catch { return null; }
  },
  set(key, value) {
    try { localStorage.setItem(SAVE_PREFIX + key, JSON.stringify(value)); } catch { /* storage unavailable */ }
  },
};

let index = [];          // case list
let puzzle = null;       // current puzzle json
let secret = null;       // {cells, murderer}
let state = null;        // player progress (see freshState)
let selected = null;     // selected person index
let tool = "note";       // "note" | "x" | "erase"
let history = [];
let timerId = null;
let gesture = null;

const els = {
  home: $("#home"), game: $("#game"), list: $("#case-list"), board: $("#board"),
  legend: $("#legend"), suspects: $("#suspects"), clues: $("#clues"), timer: $("#timer"),
  title: $("#case-title"), meta: $("#case-meta"), toast: $("#toast"),
  result: $("#result"), help: $("#help"),
};

/* ---------------- routing ---------------- */

async function boot() {
  try {
    index = await (await fetch("puzzles/index.json")).json();
  } catch {
    els.list.innerHTML = `<p class="muted">Couldn't load puzzles. If you opened this file directly, serve the folder instead (e.g. <code>py -m http.server</code>).</p>`;
    return;
  }
  window.addEventListener("hashchange", route);
  route();
}

function route() {
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
    const saved = store.get(p.id);
    const a = document.createElement("a");
    a.className = "case-card";
    a.href = "#" + p.id;
    a.innerHTML = `
      <h3><span>${p.title}</span>${saved?.solved ? '<span class="solved">✓ solved</span>' : ""}</h3>
      <div class="meta"><span class="pill ${p.difficulty}">${p.difficulty}</span>${p.size}×${p.size} · ${p.rooms.length} rooms</div>
      <div class="meta">${p.rooms.join(", ")}</div>`;
    els.list.append(a);
  }
}

async function openCase(id) {
  puzzle = await (await fetch(`puzzles/${id}.json`)).json();
  secret = JSON.parse(atob(puzzle.secret));
  state = store.get(id) || freshState();
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
  renderAll();
  startTimer();
  window.scrollTo(0, 0);
}

function freshState() {
  const n = puzzle.size;
  return {
    pos: Array(puzzle.people.length).fill(null),       // person -> [r, c]
    notes: Array.from({ length: n * n }, () => []),     // cell -> person indices
    x: Array(n * n).fill(false),                        // cell -> ruled out
    struck: [],                                         // crossed-off clue indices
    seconds: 0,
    solved: false,
    revealed: false,
  };
}

/* ---------------- board geometry ---------------- */

let cellEls = [];
let objectAt = [];  // cell -> object index or -1

const idx = (r, c) => r * puzzle.size + c;
const roomAt = (r, c) => puzzle.grid[r][c];
const isBlocked = i => objectAt[i] >= 0 && !puzzle.objects[objectAt[i]].occupiable;

function buildBoard() {
  const n = puzzle.size;
  const b = els.board;
  b.innerHTML = "";
  b.style.setProperty("--n", n);
  cellEls = [];
  objectAt = Array(n * n).fill(-1);
  puzzle.objects.forEach((o, k) => o.cells.forEach(([r, c]) => (objectAt[idx(r, c)] = k)));

  for (let r = 0; r < n; r++) {
    for (let c = 0; c < n; c++) {
      const i = idx(r, c);
      const cell = document.createElement("div");
      cell.className = "cell";
      cell.dataset.i = i;
      cell.style.background = puzzle.rooms[roomAt(r, c)].color;

      // thick walls where the room changes
      const W = "var(--wall)", t = "4px";
      const shadows = [];
      if (r > 0 && roomAt(r - 1, c) !== roomAt(r, c)) shadows.push(`inset 0 ${t} 0 ${W}`);
      if (r < n - 1 && roomAt(r + 1, c) !== roomAt(r, c)) shadows.push(`inset 0 -${t} 0 ${W}`);
      if (c > 0 && roomAt(r, c - 1) !== roomAt(r, c)) shadows.push(`inset ${t} 0 0 ${W}`);
      if (c < n - 1 && roomAt(r, c + 1) !== roomAt(r, c)) shadows.push(`inset -${t} 0 0 ${W}`);
      cell.style.boxShadow = shadows.join(",");

      const k = objectAt[i];
      if (k >= 0) {
        const o = puzzle.objects[k];
        const tile = document.createElement("div");
        tile.className = "obj " + (o.type === "carpet" ? "carpet" : o.occupiable ? "open" : "block");
        // stretch toward the other half of a multi-square object
        for (const [dr, dc, side] of [[-1, 0, "top"], [1, 0, "bottom"], [0, -1, "left"], [0, 1, "right"]]) {
          const rr = r + dr, cc = c + dc;
          if (rr >= 0 && rr < n && cc >= 0 && cc < n && objectAt[idx(rr, cc)] === k) tile.style[side] = "-2px";
        }
        const first = o.cells[0][0] === r && o.cells[0][1] === c;
        if (first && o.icon) tile.innerHTML = `<span class="icon">${o.icon}</span>`;
        tile.title = o.name;
        cell.append(tile);
        if (!o.occupiable) cell.classList.add("blocked");
      }
      b.append(cell);
      cellEls.push(cell);
    }
  }

  // room name labels: first square of each room, spanning its run along that row
  puzzle.rooms.forEach((room, ri) => {
    let start = null;
    for (let r = 0; r < n && !start; r++) for (let c = 0; c < n; c++) if (roomAt(r, c) === ri) { start = [r, c]; break; }
    let run = 0;
    while (start[1] + run < n && roomAt(start[0], start[1] + run) === ri) run++;
    const label = document.createElement("div");
    label.className = "room-label";
    label.textContent = room.name;
    label.style.top = `calc(${(start[0] / n) * 100}% + 2px)`;
    label.style.left = `calc(${(start[1] / n) * 100}% + 2px)`;
    label.style.maxWidth = `calc(${(run / n) * 100}% - 6px)`;
    b.append(label);
  });

  els.legend.innerHTML = puzzle.rooms
    .map(r => `<span><i style="background:${r.color}"></i>${r.name}</span>`)
    .join("");
}

/* ---------------- rendering ---------------- */

function renderAll() {
  renderBoard();
  renderSuspects();
  renderClues();
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
    const r = Math.floor(i / n), c = i % n;
    const cell = cellEls[i];
    cell.querySelectorAll(".mark,.x,.notes").forEach(e => e.remove());
    const who = occupant[i];
    cell.classList.toggle("covered", who < 0 && (rowCount[r] > 0 || colCount[c] > 0));

    if (who >= 0) {
      const m = document.createElement("div");
      m.className = "mark";
      if (people[who].victim) m.classList.add("victim");
      if (rowCount[r] > 1 || colCount[c] > 1) m.classList.add("conflict");
      if (state.revealed) m.classList.add("reveal");
      m.innerHTML = `<span>${people[who].letter}</span>`;
      cell.append(m);
    } else if (state.x[i]) {
      const x = document.createElement("div");
      x.className = "x";
      x.textContent = "✕";
      cell.append(x);
    } else if (state.notes[i].length) {
      const box = document.createElement("div");
      box.className = "notes";
      for (const k of state.notes[i]) {
        const s = document.createElement("span");
        s.textContent = people[k].letter;
        s.style.gridArea = `${Math.floor(k / 3) + 1} / ${(k % 3) + 1}`;
        if (people[k].victim) s.classList.add("victim");
        if (k === selected) s.classList.add("sel");
        box.append(s);
      }
      cell.append(box);
    }
  }
}

function renderSuspects() {
  els.suspects.innerHTML = "";
  puzzle.people.forEach((p, k) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip" + (state.pos[k] ? " placed" : "");
    chip.setAttribute("aria-pressed", k === selected);
    chip.innerHTML = `<span class="badge${p.victim ? " victim" : ""}">${p.letter}</span>${p.name}`;
    chip.addEventListener("click", () => select(k));
    els.suspects.append(chip);
  });
}

function renderClues() {
  els.clues.innerHTML = "";
  const groups = puzzle.people.map((p, k) => ({ k, person: p, clues: [] }));
  const facts = [];
  puzzle.clues.forEach((cl, ci) => (cl.person === null ? facts : groups[cl.person].clues).push(ci));

  const clueBtn = ci => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "clue" + (state.struck.includes(ci) ? " done" : "");
    b.textContent = puzzle.clues[ci].text;
    b.addEventListener("click", () => {
      const s = state.struck;
      s.includes(ci) ? s.splice(s.indexOf(ci), 1) : s.push(ci);
      b.classList.toggle("done");
      save();
    });
    return b;
  };

  for (const g of groups) {
    const card = document.createElement("div");
    card.className = "person-card" + (g.k === selected ? " selected" : "");
    const head = document.createElement("button");
    head.type = "button";
    head.className = "person-head";
    head.innerHTML = `<span class="badge${g.person.victim ? " victim" : ""}">${g.person.letter}</span>
      <strong>${g.person.name}</strong>${g.person.victim ? '<span class="tag">victim</span>' : ""}`;
    head.addEventListener("click", () => select(g.k));
    card.append(head);
    if (g.clues.length) g.clues.forEach(ci => card.append(clueBtn(ci)));
    else card.insertAdjacentHTML("beforeend", `<p class="none">No statement.</p>`);
    els.clues.append(card);
  }
  if (facts.length) {
    const card = document.createElement("div");
    card.className = "person-card facts";
    card.innerHTML = `<strong>Also known</strong>`;
    facts.forEach(ci => card.append(clueBtn(ci)));
    els.clues.append(card);
  }
}

function select(k) {
  selected = selected === k ? null : k;
  renderBoard();
  renderSuspects();
  els.clues.querySelectorAll(".person-card").forEach((card, i) => card.classList.toggle("selected", i === selected));
}

/* ---------------- actions ---------------- */

function snapshot() {
  history.push(JSON.stringify(state));
  if (history.length > 200) history.shift();
}

function save() {
  store.set(puzzle.id, state);
}

function locked() {
  if (state.solved || state.revealed) {
    toast("This case is closed.");
    return true;
  }
  return false;
}

function occupantOf(i) {
  const n = puzzle.size;
  return state.pos.findIndex(p => p && idx(p[0], p[1]) === i);
}

function needSelection() {
  if (selected !== null) return false;
  toast("Pick a person first.");
  els.suspects.querySelectorAll(".chip").forEach(c => {
    c.classList.remove("attention");
    void c.offsetWidth;
    c.classList.add("attention");
  });
  return true;
}

function place(i) {
  if (needSelection()) return;
  snapshot();
  const n = puzzle.size;
  const cur = state.pos[selected];
  if (cur && idx(cur[0], cur[1]) === i) {
    state.pos[selected] = null;  // hold again = pick back up
  } else {
    const other = occupantOf(i);
    if (other >= 0) state.pos[other] = null;
    state.pos[selected] = [Math.floor(i / n), i % n];
    state.x[i] = false;
  }
  cellEls[i].classList.remove("flash");
  void cellEls[i].offsetWidth;
  cellEls[i].classList.add("flash");
  if (navigator.vibrate) navigator.vibrate(15);
  afterChange();
  checkComplete();
}

// Paint value decided from the first square of a tap/drag, then applied to every square touched.
function paintValue(i) {
  if (tool === "erase") return null;
  if (tool === "x") return !state.x[i];
  return !state.notes[i].includes(selected);
}

function paint(i, value) {
  if (isBlocked(i)) return;
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
    if (value) state.x[i] = false;
  }
}

function afterChange() {
  save();
  renderBoard();
  renderSuspects();
}

function checkComplete() {
  if (state.pos.some(p => !p)) return;
  const right = state.pos.every((p, k) => p[0] === secret.cells[k][0] && p[1] === secret.cells[k][1]);
  if (!right) {
    toast("Everyone's placed, but something doesn't add up…");
    return;
  }
  state.solved = true;
  save();
  stopTimer();
  showResult(true);
}

function showResult(won) {
  const m = puzzle.people[secret.murderer];
  const v = puzzle.people.find(p => p.victim);
  const [r, c] = secret.cells[puzzle.people.indexOf(v)];
  const room = puzzle.rooms[roomAt(r, c)].name;
  $("#result-title").textContent = won ? "Case closed!" : "The answer";
  $("#result-text").innerHTML = `<b>${m.name}</b> was alone with <b>${v.name}</b> in the ${room}.` +
    (secret.motive ? `<span class="motive">${secret.motive}</span>` : "") +
    (won ? `<span class="muted small">Solved in ${fmtTime(state.seconds)}.</span>` : "");
  const next = index[index.findIndex(p => p.id === puzzle.id) + 1];
  $("#result-next").hidden = !next;
  $("#result-next").onclick = () => { els.result.close(); location.hash = next.id; };
  els.result.showModal();
}

/* ---------------- pointer input on the board ---------------- */

function cellIndexAt(x, y) {
  const el = document.elementFromPoint(x, y)?.closest(".cell");
  return el && els.board.contains(el) ? Number(el.dataset.i) : null;
}

els.board.addEventListener("pointerdown", e => {
  if (e.button !== 0 || !puzzle) return;
  const i = cellIndexAt(e.clientX, e.clientY);
  if (i === null || isBlocked(i)) return;
  e.preventDefault();
  els.board.setPointerCapture(e.pointerId);
  gesture = { start: i, last: i, dragged: false, held: false, value: null, timer: 0 };
  if (tool !== "erase") {
    gesture.timer = setTimeout(() => {
      if (!gesture || gesture.dragged || locked()) return;
      gesture.held = true;
      place(i);
    }, HOLD_MS);
  }
});

els.board.addEventListener("pointermove", e => {
  if (!gesture || gesture.held) return;
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
  clearTimeout(gesture.timer);
  const g = gesture;
  gesture = null;
  if (g.held) return;
  if (g.dragged) { afterChange(); return; }
  // plain tap
  const who = occupantOf(g.start);
  if (who >= 0 && tool === "note") { select(who); return; }
  if (locked() || (tool === "note" && needSelection())) return;
  snapshot();
  paint(g.start, paintValue(g.start));
  afterChange();
}
els.board.addEventListener("pointerup", endGesture);
els.board.addEventListener("pointercancel", () => { if (gesture) clearTimeout(gesture.timer); gesture = null; });
els.board.addEventListener("contextmenu", e => e.preventDefault());

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
      const keep = { struck: state.struck, seconds: state.seconds };
      state = Object.assign(freshState(), keep);
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
  const seconds = state.seconds;
  state = JSON.parse(history.pop());
  state.seconds = seconds;
  afterChange();
  renderClues();
});

$("#tool-reveal").addEventListener("click", () => {
  if (state.solved) return showResult(true);
  if (!state.revealed && !confirm("Give up and show the solution?")) return;
  snapshot();
  state.revealed = true;
  state.pos = secret.cells.map(c => [...c]);
  stopTimer();
  afterChange();
  showResult(false);
});

document.addEventListener("keydown", e => {
  if (!puzzle || els.game.hidden || e.target.closest("dialog")) return;
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") { e.preventDefault(); $("#tool-undo").click(); return; }
  const k = puzzle.people.findIndex(p => p.letter.toLowerCase() === e.key.toLowerCase());
  if (k >= 0 && !e.ctrlKey && !e.metaKey && !e.altKey) select(k);
});

/* ---------------- timer, toast, help ---------------- */

const fmtTime = s => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

function startTimer() {
  stopTimer();
  els.timer.textContent = fmtTime(state.seconds);
  if (state.solved || state.revealed) return;
  timerId = setInterval(() => {
    if (document.hidden) return;
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
  toastTimer = setTimeout(() => els.toast.classList.remove("show"), 2200);
}

$("#help-btn").addEventListener("click", () => els.help.showModal());
$("#help-close").addEventListener("click", () => els.help.close());
for (const d of [els.help, els.result]) {
  d.addEventListener("click", e => { if (e.target === d) d.close(); });  // click on backdrop
}
els.help.querySelectorAll("[role=tab]").forEach(tab => tab.addEventListener("click", () => {
  els.help.querySelectorAll("[role=tab]").forEach(t => t.setAttribute("aria-selected", t === tab));
  els.help.querySelectorAll(".tab-panel").forEach(p => (p.hidden = p.dataset.panel !== tab.dataset.tab));
}));
if (!store.get("seen-help")) {
  store.set("seen-help", true);
  els.help.showModal();
}

boot();
