# Murdoku

A logic murder-mystery puzzle game. Place every person on the floor plan with one person per row and column, follow the witness statements, and find who was alone with the victim.

- `generator/` is Python (standard library only, 3.10+). It builds random floor plans, hides a solution, writes clues, and trims them while a solver confirms there is exactly **one** solution. A step-by-step "human" solver (`hints.py`) then solves each case one deduction at a time. Those steps become the in-game hints, and they're also used to check the difficulty.
- `docs/` is the static web game (HTML/CSS/JS, no build step). GitHub Pages serves it as-is. `avatar.js` draws the character portraits.

## Make puzzles

```bash
py generator/build.py --add 20                # keep every existing case, add 20 new ones
py generator/build.py --count 33 --seed 2026  # build a brand-new set (REPLACES the existing cases)
py generator/build.py --reorder               # re-label existing cases after changing difficulty rules
```

Use `--add` to grow the collection: existing cases keep their numbers and content (so nobody's progress
is affected) and new ones get the next numbers. Repeated `--add` runs always give new cases. The case list
groups cases by difficulty, so new easy cases show up in the Easy section.

Output goes to `docs/puzzles/` (one JSON per case plus `index.json`). Board sizes cycle through `PLAN` in
`generator/build.py`.

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

- **Rooms and furniture:** `ROOM_TYPES` and `OBJECT_TYPES` in `generator/murdoku/model.py`. A room type marked repeatable can appear twice in one house ("North/South Bedroom"), which enables clues like "a woman was in the other Bedroom". Floor plans are built from rectangles in `make_rooms` (`generator/murdoku/generate.py`).
- **Names:** `SUSPECTS` and `VICTIMS` (name and gender, for She/He in clues) in the same file. Initials must be unique, and only the victim may start with V.
- **Motives:** `MOTIVES` in `generator/murdoku/story.py`.
- **Clue types:** add them in `generator/murdoku/clues.py` (`render`, `refs`, a `*_holds` check, and `true_clues`). The solver and hint engine pick them up through the `UNARY`, `BINARY` and `EXISTS` sets; `EXISTS` clues ("someone was …") also need a `target_cells` rule saying which squares that someone could be on.

**After changing `docs/` code:** bump the `?v=` number on the `style.css`, `avatar.js` and `game.js` links in `docs/index.html` so browsers fetch the new files instead of cached ones.
