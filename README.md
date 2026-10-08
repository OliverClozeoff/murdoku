# Murdoku

A logic murder-mystery puzzle game. Place every person on the floor plan with one person per row and column, follow the witness statements, and find who was alone with the victim.

- `generator/` is Python (standard library only, 3.10+). It builds random floor plans, hides a solution, writes clues, and trims them while a solver confirms there is exactly **one** solution. A step-by-step "human" solver (`hints.py`) then solves each case one deduction at a time. Those steps become the in-game hints, and they're also used to check the difficulty.
- `docs/` is the static web game (HTML/CSS/JS, no build step). GitHub Pages serves it as-is. `avatar.js` draws the character portraits.

## Make puzzles

```bash
py generator/build.py                         # 21 puzzles, seed 2026
py generator/build.py --count 40 --seed 99    # different set
```

Output goes to `docs/puzzles/` (one JSON per case plus `index.json`). Sizes and difficulties cycle through `PLAN` in `generator/build.py`.

Difficulty is checked, not just requested. Easy cases can be solved with simple steps only, medium ones need 1–3 "what if" look-ahead rounds, and hard ones need 3 or more. No case ever needs trial and error. The build prints these counts for each case.

## Play locally

```bash
py -m http.server 8000 --directory docs
```

Then open http://localhost:8000. Opening `index.html` directly from disk won't work because the browser blocks `fetch` for local files.

## Publish on GitHub Pages

1. Push this folder to a GitHub repository.
2. Go to **Settings → Pages**, choose **Deploy from a branch**, then select branch `main` and folder `/docs`.
3. The site appears at `https://<username>.github.io/<repo>/`.

## Extending

- **Rooms and furniture:** `ROOM_TYPES` and `OBJECT_TYPES` in `generator/murdoku/model.py`.
- **Names:** `SUSPECTS` and `VICTIMS` (name and gender, for She/He in clues) in the same file. Initials must be unique, and only the victim may start with V.
- **Motives:** `MOTIVES` in `generator/murdoku/story.py`.
- **Clue types:** add them in `generator/murdoku/clues.py` (`render`, `refs`, a `*_holds` check, and `true_clues`). The solver and hint engine pick them up through the `UNARY` and `BINARY` sets.
