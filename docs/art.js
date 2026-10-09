"use strict";

/* Top-down furniture art, drawn as SVG.
   Each piece is drawn once over its whole footprint: a two-square table is one table.
   Everything is designed lying horizontally (L x 100 units, 100 units per square) and
   rotated for pieces that stand vertically on the board. */

const Art = (() => {
  const INK = "#3a3631";
  const line = (w = 4) => `stroke="${INK}" stroke-width="${w}" stroke-linejoin="round" stroke-linecap="round"`;
  const CAR_COLORS = ["#d9534f", "#4f86c6", "#e0b33a", "#5fa35a", "#8c8f96", "#f2f2ee"];

  function placeSetting(cx, cy) {
    return `
      <circle cx="${cx}" cy="${cy}" r="17" fill="#fbfaf6" ${line(3)}/>
      <circle cx="${cx}" cy="${cy}" r="10" fill="none" stroke="#d9d4c7" stroke-width="2.5"/>
      <path d="M${cx - 27} ${cy - 15} V${cy + 15} M${cx - 30} ${cy - 15} V${cy - 6} M${cx - 24} ${cy - 15} V${cy - 6}"
            fill="none" stroke="#7d7a73" stroke-width="2.5" stroke-linecap="round"/>
      <path d="M${cx + 27} ${cy - 15} q5 8 0 14 V${cy + 15}" fill="none" stroke="#7d7a73" stroke-width="2.5" stroke-linecap="round"/>`;
  }

  const draw = {
    table(L) {
      let s = `<rect x="6" y="10" width="${L - 12}" height="80" rx="10" fill="#c79a66" ${line()}/>
               <rect x="14" y="18" width="${L - 28}" height="64" rx="6" fill="none" stroke="#a97b49" stroke-width="3"/>`;
      for (let i = 0; i < L / 100; i++) s += placeSetting(i * 100 + 50, 50);
      return s;
    },

    carpet(L) {
      let s = "";
      for (const x of [4, L - 4]) {  // fringe on the short ends
        for (let y = 18; y <= 82; y += 8) s += `<path d="M${x} ${y} H${x === 4 ? 0 : L}" stroke="#e7c27d" stroke-width="3"/>`;
      }
      s += `<rect x="4" y="10" width="${L - 8}" height="80" rx="3" fill="#b5533f" ${line(3)}/>
            <rect x="12" y="18" width="${L - 24}" height="64" fill="none" stroke="#e7c27d" stroke-width="4"/>
            <rect x="19" y="25" width="${L - 38}" height="50" fill="#9c4434"/>`;
      for (let i = 0; i < L / 100; i++) {
        const cx = i * 100 + 50;
        s += `<path d="M${cx} 32 L${cx + 16} 50 L${cx} 68 L${cx - 16} 50 Z" fill="#e7c27d"/>
              <circle cx="${cx}" cy="50" r="5" fill="#9c4434"/>`;
      }
      return s;
    },

    bed(L) {
      return `<rect x="6" y="8" width="${L - 12}" height="84" rx="8" fill="#8a6242" ${line()}/>
              <rect x="12" y="14" width="${L - 24}" height="72" rx="6" fill="#f5f1e8"/>
              <rect x="18" y="20" width="38" height="60" rx="12" fill="#ffffff" ${line(3)}/>
              <rect x="66" y="12" width="${L - 78}" height="76" rx="6" fill="#6f95c4" ${line(3)}/>
              <path d="M78 12 V88" stroke="#5a7fae" stroke-width="5"/>
              <path d="M96 30 h${L - 130} M96 50 h${L - 130} M96 70 h${L - 130}" stroke="#86a9d3" stroke-width="3"/>`;
    },

    sofa(L) {
      let s = `<rect x="6" y="8" width="${L - 12}" height="84" rx="14" fill="#8e6aa8" ${line()}/>
               <rect x="6" y="8" width="${L - 12}" height="24" rx="12" fill="#7a5794" ${line(3)}/>
               <rect x="6" y="8" width="20" height="84" rx="10" fill="#7a5794" ${line(3)}/>
               <rect x="${L - 26}" y="8" width="20" height="84" rx="10" fill="#7a5794" ${line(3)}/>`;
      const seats = Math.max(1, Math.round(L / 100));
      const w = (L - 52) / seats;
      for (let i = 0; i < seats; i++) {
        s += `<rect x="${26 + i * w + 2}" y="34" width="${w - 4}" height="54" rx="8" fill="#a585bd" ${line(2.5)}/>`;
      }
      return s;
    },

    // Front view: a top-down chair is just a brown square, this reads as a chair at a glance.
    chair() {
      return `<ellipse cx="50" cy="93" rx="30" ry="4" fill="rgba(0,0,0,.16)"/>
              <rect x="27" y="8" width="8" height="62" rx="3" fill="#8f6a43" ${line(3)}/>
              <rect x="65" y="8" width="8" height="62" rx="3" fill="#8f6a43" ${line(3)}/>
              <rect x="24" y="8" width="52" height="13" rx="5" fill="#a97b49" ${line(3)}/>
              <rect x="40" y="21" width="6" height="34" fill="#a97b49" ${line(2)}/>
              <rect x="54" y="21" width="6" height="34" fill="#a97b49" ${line(2)}/>
              <rect x="31" y="72" width="6" height="16" fill="#6f5136" ${line(2)}/>
              <rect x="63" y="72" width="6" height="16" fill="#6f5136" ${line(2)}/>
              <path d="M24 55 H76 L84 66 H16 Z" fill="#c69a6e" ${line(3)}/>
              <rect x="16" y="66" width="68" height="8" rx="2" fill="#a97b49" ${line(3)}/>
              <rect x="18" y="74" width="8" height="18" rx="2" fill="#8f6a43" ${line(3)}/>
              <rect x="74" y="74" width="8" height="18" rx="2" fill="#8f6a43" ${line(3)}/>`;
    },

    bathtub(L) {
      return `<rect x="6" y="10" width="${L - 12}" height="80" rx="36" fill="#f4f6f7" ${line()}/>
              <rect x="18" y="22" width="${L - 36}" height="56" rx="26" fill="#8fd0e6"/>
              <path d="M40 40 q12 -6 24 0 M${L - 90} 58 q12 -6 24 0" fill="none" stroke="#c4e8f4" stroke-width="4" stroke-linecap="round"/>
              <circle cx="${L - 24}" cy="50" r="7" fill="#a9b4ba" ${line(2.5)}/>`;
    },

    bench(L) {
      return `<rect x="16" y="12" width="12" height="76" rx="3" fill="#6f5136" ${line(3)}/>
              <rect x="${L - 28}" y="12" width="12" height="76" rx="3" fill="#6f5136" ${line(3)}/>
              ${[18, 42, 66].map(y => `<rect x="6" y="${y}" width="${L - 12}" height="16" rx="4" fill="#b98a5a" ${line(3)}/>`).join("")}`;
    },

    car(L, seed) {
      const body = CAR_COLORS[seed % CAR_COLORS.length];
      const front = L - 6;  // car faces right
      return `<rect x="6" y="12" width="${L - 12}" height="76" rx="30" fill="${body}" ${line()}/>
              <path d="M${front - 58} 22 L${front - 30} 28 L${front - 30} 72 L${front - 58} 78 Z" fill="#9fc6dc" ${line(3)}/>
              <rect x="${L * 0.32}" y="24" width="${L * 0.28}" height="52" rx="8" fill="rgba(255,255,255,.28)" ${line(3)}/>
              <path d="M${L * 0.2} 26 L${L * 0.3} 28 L${L * 0.3} 72 L${L * 0.2} 74 Z" fill="#9fc6dc" ${line(3)}/>
              <circle cx="${front - 6}" cy="24" r="5" fill="#ffe28a" ${line(2)}/>
              <circle cx="${front - 6}" cy="76" r="5" fill="#ffe28a" ${line(2)}/>`;
    },

    shelf() {
      const books = ["#d9534f", "#4f86c6", "#e0b33a", "#5fa35a", "#8e6aa8", "#e07b39"];
      let s = `<rect x="10" y="14" width="80" height="72" rx="4" fill="#8f6a43" ${line()}/>
               <rect x="16" y="20" width="68" height="60" fill="#5e4430"/>`;
      let x = 18;
      books.forEach((c, i) => {
        const w = 9 + (i % 2) * 2;
        s += `<rect x="${x}" y="${24 + (i % 3) * 3}" width="${w}" height="${54 - (i % 3) * 3}" rx="1.5" fill="${c}" ${line(1.5)}/>`;
        x += w + 1;
      });
      return s;
    },

    // Plants and trees are seen from the side (they stand up), everything else from above.
    plant(L, seed) {
      const tilt = (seed % 3) - 1;  // a little variety between plants
      const leaf = (x, y, rx, ry, rot, c) =>
        `<ellipse cx="${x}" cy="${y}" rx="${rx}" ry="${ry}" fill="${c}" ${line(2.5)} transform="rotate(${rot + tilt * 6} ${x} ${y})"/>`;
      return `<ellipse cx="50" cy="92" rx="24" ry="5" fill="rgba(0,0,0,.18)"/>
              ${leaf(30, 38, 9, 24, -38, "#4f9e4c")}${leaf(70, 38, 9, 24, 38, "#4f9e4c")}
              ${leaf(40, 30, 8, 25, -14, "#62b25c")}${leaf(60, 30, 8, 25, 14, "#62b25c")}
              ${leaf(50, 26, 8, 26, 0, "#74c06a")}
              <path d="M30 58 H70 L64 90 H36 Z" fill="#c46b4f" ${line(3)}/>
              <rect x="27" y="54" width="46" height="10" rx="3" fill="#d6805f" ${line(3)}/>`;
    },

    tree(L, seed) {
      const trunk = `<ellipse cx="50" cy="93" rx="30" ry="5" fill="rgba(0,0,0,.2)"/>
                     <rect x="44" y="70" width="12" height="22" rx="3" fill="#7a5233" ${line(3)}/>`;
      if (seed % 2 === 0) {
        // pine: three stacked layers
        return trunk + [[40, 78, 40], [22, 60, 32], [6, 42, 22]].map(([top, bottom, half], i) =>
          `<path d="M50 ${top} L${50 + half} ${bottom} H${50 - half} Z" fill="${["#2f7a3f", "#38894a", "#43985a"][i]}" ${line(3)}/>`
        ).join("");
      }
      // round leafy tree: bushy crown made of overlapping circles
      return trunk + `<circle cx="50" cy="42" r="30" fill="#3f8a46" ${line(3)}/>
                      <circle cx="32" cy="50" r="18" fill="#3f8a46" ${line(3)}/>
                      <circle cx="68" cy="50" r="18" fill="#3f8a46" ${line(3)}/>
                      <circle cx="50" cy="42" r="27" fill="#3f8a46"/>
                      <circle cx="40" cy="32" r="10" fill="#5aa85c"/><circle cx="60" cy="40" r="8" fill="#5aa85c"/>`;
    },

    tv() {
      return `<rect x="34" y="72" width="32" height="12" rx="3" fill="#5a5f66" ${line(3)}/>
              <rect x="8" y="18" width="84" height="56" rx="6" fill="#2b2f36" ${line()}/>
              <rect x="14" y="24" width="72" height="44" rx="3" fill="#3d4b5c"/>
              <path d="M22 60 L44 30" stroke="#5f7590" stroke-width="5" stroke-linecap="round"/>`;
    },

    sink() {
      return `<rect x="10" y="14" width="80" height="72" rx="8" fill="#dfe5e8" ${line()}/>
              <ellipse cx="50" cy="56" rx="27" ry="20" fill="#b7d9e6" ${line(3)}/>
              <circle cx="50" cy="58" r="4" fill="#7b8a92"/>
              <rect x="45" y="20" width="10" height="20" rx="3" fill="#9aa4aa" ${line(2.5)}/>`;
    },

    toolbox() {
      return `<path d="M36 34 V22 H64 V34" fill="none" ${line(5)}/>
              <rect x="14" y="32" width="72" height="50" rx="6" fill="#d0443c" ${line()}/>
              <path d="M14 46 H86" ${line(3)}/>
              <rect x="44" y="42" width="12" height="8" rx="2" fill="#f0c94a" ${line(2)}/>`;
    },

    pond(L) {
      return `<path d="M20 22 Q${L / 2} 2 ${L - 20} 20 Q${L - 2} 50 ${L - 18} 80 Q${L / 2} 98 20 80 Q2 50 20 22 Z"
                    fill="#74c0e2" stroke="#4a90b0" stroke-width="4"/>
              <ellipse cx="${L * 0.38}" cy="40" rx="14" ry="5" fill="none" stroke="#b4e1f2" stroke-width="3"/>
              <ellipse cx="${L * 0.62}" cy="64" rx="18" ry="6" fill="none" stroke="#b4e1f2" stroke-width="3"/>
              <path d="M${L - 40} 34 a12 12 0 1 0 8 4 l-8 8 Z" fill="#5fae5a" stroke="#2f6b33" stroke-width="2.5"/>`;
    },
  };

  /** SVG for a placed object covering w x h squares (one of them is 1). */
  function svg(type, w, h, seed = 0) {
    const fn = draw[type];
    if (!fn) return null;
    const vertical = h > w;
    const L = 100 * Math.max(w, h);
    const inner = fn(L, seed);
    const body = vertical ? `<g transform="translate(100 0) rotate(90)">${inner}</g>` : inner;
    return `<svg viewBox="0 0 ${100 * w} ${100 * h}" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" overflow="visible">${body}</svg>`;
  }

  return { svg };
})();
