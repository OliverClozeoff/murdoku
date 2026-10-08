"use strict";

/* Procedural cartoon portraits. Same name -> same face, every time. */

const Avatar = (() => {
  const SKIN = ["#f6d5bd", "#eebf9a", "#d9a074", "#b47a4f", "#8a5634", "#f3c9a5", "#5e3a22"];
  const HAIR = ["#2b1d16", "#4a2f20", "#7a4b27", "#b07a3c", "#dcb66e", "#a3a3a3", "#e6e2da", "#a2402a", "#151515"];
  const SHIRT = ["#3d5a80", "#9a3b3b", "#4f7a4f", "#7a5c99", "#c08a2d", "#2f6f73", "#5b5b66", "#b45f7c", "#8a6a4a"];
  const BG = ["#9ec5d6", "#e8b6a5", "#b9d3a8", "#d6c3e8", "#f0d58c", "#a9c8c0", "#e3b9cf", "#c9c1b1"];

  function hash(str) {
    let h = 2166136261;
    for (const ch of str) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
    return h >>> 0;
  }
  function rng(seed) {
    let s = seed || 1;
    return () => ((s = Math.imul(s ^ (s >>> 15), 2246822519) ^ Math.imul(s ^ (s >>> 13), 3266489917)) >>> 0) / 4294967296;
  }
  const pick = (r, arr) => arr[Math.floor(r() * arr.length)];

  const HAIR_TOP = "M29 50 C27 27 40 20 50 20 C61 20 74 27 71 50 C67 39 59 33 50 33 C41 33 33 39 29 50 Z";
  const STYLES = {
    f: ["long", "bob", "bun", "ponytail", "long"],
    m: ["short", "short", "curly", "bald", "side"],
  };

  function features(person) {
    const r = rng(hash(person.name + person.gender));
    const age = r();
    return {
      skin: pick(r, SKIN),
      hair: age > 0.82 ? pick(r, ["#a3a3a3", "#e6e2da"]) : pick(r, HAIR.slice(0, 5).concat(["#a2402a", "#151515"])),
      shirt: pick(r, SHIRT),
      bg: person.victim ? "#c9b3e0" : pick(r, BG),
      style: pick(r, STYLES[person.gender] || STYLES.m),
      beard: person.gender === "m" && r() < 0.35 ? pick(r, ["full", "mustache"]) : null,
      glasses: r() < 0.25,
      earrings: person.gender === "f" && r() < 0.4,
    };
  }

  function hairBack(f) {
    switch (f.style) {
      case "long": return `<path d="M26 52 C22 24 40 17 50 17 C62 17 79 24 74 52 L78 96 C66 100 34 100 22 96 Z" fill="${f.hair}"/>`;
      case "bob": return `<path d="M26 52 C23 24 40 17 50 17 C62 17 78 24 74 52 L75 76 C66 80 34 80 25 76 Z" fill="${f.hair}"/>`;
      case "ponytail": return `<ellipse cx="76" cy="58" rx="8" ry="18" fill="${f.hair}" transform="rotate(-14 76 58)"/>`;
      case "bun": return `<circle cx="50" cy="17" r="10" fill="${f.hair}"/>`;
      default: return "";
    }
  }

  function hairFront(f) {
    switch (f.style) {
      case "bald":
        return `<path d="M29 52 C29 44 31 40 33 38 L34 52 Z M71 52 C71 44 69 40 67 38 L66 52 Z" fill="${f.hair}"/>`;
      case "curly": {
        let d = "";
        for (const [x, y] of [[32, 40], [36, 31], [43, 25], [50, 23], [57, 25], [64, 31], [68, 40]]) d += `<circle cx="${x}" cy="${y}" r="8" fill="${f.hair}"/>`;
        return d;
      }
      case "side":
        return `<path d="M29 50 C27 27 40 20 52 20 C63 21 74 28 71 50 C68 40 62 33 46 31 C40 36 33 42 29 50 Z" fill="${f.hair}"/>`;
      default:
        return `<path d="${HAIR_TOP}" fill="${f.hair}"/>`;
    }
  }

  function svg(person, { crop = false } = {}) {
    const f = features(person);
    const vb = crop ? "20 16 60 60" : "0 0 100 110";
    const beard = f.beard === "full"
      ? `<path d="M30 56 C31 76 42 82 50 82 C58 82 69 76 70 56 C66 66 58 70 50 70 C42 70 34 66 30 56 Z" fill="${f.hair}"/>`
      : f.beard === "mustache" ? `<path d="M42 64 C46 61 49 62 50 63 C51 62 54 61 58 64 C54 66 46 66 42 64 Z" fill="${f.hair}"/>` : "";
    const glasses = f.glasses
      ? `<g fill="none" stroke="#2a2a2a" stroke-width="1.6"><circle cx="42" cy="52" r="5.5"/><circle cx="58" cy="52" r="5.5"/><path d="M47.5 52 H52.5"/></g>` : "";
    const earrings = f.earrings ? `<circle cx="30" cy="60" r="1.8" fill="#e0b84a"/><circle cx="70" cy="60" r="1.8" fill="#e0b84a"/>` : "";
    return `<svg viewBox="${vb}" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      ${crop ? "" : `<rect width="100" height="110" fill="${f.bg}"/>`}
      ${hairBack(f)}
      <path d="M12 110 C14 90 30 82 50 82 C70 82 86 90 88 110 Z" fill="${f.shirt}"/>
      <path d="M43 82 L50 92 L57 82 Z" fill="${f.skin}"/>
      <rect x="44" y="68" width="12" height="16" rx="4" fill="${f.skin}"/>
      <ellipse cx="30" cy="54" rx="4" ry="6" fill="${f.skin}"/>
      <ellipse cx="70" cy="54" rx="4" ry="6" fill="${f.skin}"/>
      <ellipse cx="50" cy="50" rx="20" ry="24" fill="${f.skin}"/>
      ${earrings}
      ${beard}
      <g fill="#2a2a2a"><circle cx="42" cy="52" r="2.2"/><circle cx="58" cy="52" r="2.2"/></g>
      <g stroke="${f.hair === "#e6e2da" ? "#8f8a80" : f.hair}" stroke-width="2" stroke-linecap="round"><path d="M38 45 L45 44"/><path d="M55 44 L62 45"/></g>
      <path d="M50 54 Q48 59 51 60" fill="none" stroke="rgba(0,0,0,.35)" stroke-width="1.4" stroke-linecap="round"/>
      <path d="M45 66 Q50 69 55 66" fill="none" stroke="#7a3b32" stroke-width="1.8" stroke-linecap="round"/>
      ${glasses}
      ${hairFront(f)}
    </svg>`;
  }

  return { svg };
})();
