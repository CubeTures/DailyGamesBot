export default {
  puzzle_id: gid,                 // the shared game, not the puzzle
  title,
  // This browser's player in the game, as the site knows them; a start
  // report records it so their squares are credited to them whoever
  // reports the solve.
  player_id: solve?.dfacId ?? ls("dfac-id"),
  ...(solved ? {
    pid: req.url.match(/record_solve\/([^/?#]+)/)?.[1] ?? null,  // the puzzle
    // Squares this player filled (the proxy swaps in each credited
    // player's own from `players`) that are still theirs at the solve:
    // revealed ones count for nobody. Higher is better; it's summed over
    // the day's games on the scoreboard. A solo solve with no reveals is
    // every square, one that revealed everything is 0.
    score: squaresBy[solve.dfacId] ?? 0,
    total_squares: cells.length,
    revealed: cells.filter(c => c.revealed).length,
    // The whole game's solve time by the site's clock (shared by everyone
    // in it), summed over the day on the scoreboard.
    time_secs: Math.round(solve.time_to_solve / 1000),
    // Everyone in the game, with their squares; the announcement ranks them.
    players: playerIds.map(id => ({
      id,
      name: users[id]?.displayName ?? null,
      score: squaresBy[id] ?? 0,
    })),
  } : {}),
};
