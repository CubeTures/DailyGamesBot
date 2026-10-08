// PokeDoku keeps no game state in the browser; it all comes from
// api.pokedoku.com (fetched at /__host/api.pokedoku.com/... on this port):
//   GET  /api/puzzle/current         today's grid: {"id": 1726, "date": "2026-10-08", ...}
//   GET  /api/pokemon/all            [{"id": 604, "name": "eelektross", ...}, ...]
//   GET  /api/puzzle/1726/solution   the player's grid so far (on page load)
//   POST /api/puzzle/solution/guess  {"result": true, "solution": <same shape>} after each guess
//   GET  /api/puzzle/1726/solution/stats   fetched right after either of the two above:
//     {"uniqueness": 134.003, "uniquenessPercentile": 20.9, "percentiles": {"1": 0.0066, ...}}
// The solution:
//   {"puzzleId": 1726, "puzzleSize": 9, "attempts": 9, "score": 8, "completed": true,
//    "cells": [604, 18, 282, 0, 249, 150, 10037, 10287, 10306], ...}
// `cells` is the grid row by row, a Pokémon id per correct cell and 0 for one
// still empty. `score` is how many are filled. `completed` turns true once
// the grid is full or all 9 guesses are used; running out is just score < 9.
// "Keep Playing" after a loss sets `extended` and allows more guesses, but
// the result is saved on the first completed check, so they never count.
//
// Each response is checked on its own, so what it says is kept on window
// for the later ones. Every assignment here only depends on `res`, because
// this runs twice per response (for `when`, then for the fields).
const pd = (window.__dgbPokedoku ??= {});
const url = req?.url ?? "";
if (/\/puzzle\/current$/.test(url) && res?.json?.id) pd.current = res.json;
if (/\/pokemon\/all$/.test(url) && Array.isArray(res?.json)) {
  pd.names = Object.fromEntries(res.json.map(p => [p.id, p.name]));
}
const solution = /\/solution\/guess$/.test(url) ? res?.json?.solution
  : /\/solution$/.test(url) ? res?.json : null;
if (solution?.puzzleId) {
  pd.solution = solution;
  pd.stats = null;  // stale until the stats fetch that follows this solution
}
if (/\/solution\/stats$/.test(url) && res?.json?.uniqueness != null) {
  pd.stats = { ...res.json, puzzleId: Number(url.match(/puzzle\/(\d+)\//)?.[1]) };
}
const sol = pd.solution;

// The grid is complete and its stats are in, and it's today's puzzle, not an
// archive one (those have their own ids).
const finished = !!sol?.completed
  && pd.stats?.puzzleId === sol.puzzleId
  && pd.current?.id === sol.puzzleId;
