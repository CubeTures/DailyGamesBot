// When a daily game ends (win or fall), the game writes three localStorage
// keys in one go, and nothing game-related before that:
//   TR_CURRENT_GAME_SESSION = {hasWon: true, lastGameCompletedDate: 20261015,
//     responseIndexes: [0, 1, 3, 1, 3, 3, 0, 0, 3],
//     responsePoints: [250, 250, 250, 250, 250, 210, 240, 250, 0],
//     totalAnswersPoints: 800, totalTimeBonusPoints: 1150}
//     one entry per question answered: the option picked (-1 when the 15s
//     timer ran out) and its points, 100 + 10 per second left if right, 0 if
//     wrong. Three wrong and you fall: a loss has hasWon false and stops
//     early, e.g. responsePoints [230, 0, 240, 0, 0]. Only saved for today's
//     puzzle, never for archive ones, and replaced if the player tries again.
//   TR_GAMES_OF_THE_WEEK = [{id: 20871, date: 20261015, hasWon: true,
//     attempts: 1, gameStatus: 1, title: "Tightrope Week 115 Thursday"}, ...]
//     the puzzle's id, per date played.
//   TR_GAME_STATS = {crossed, currentStreak, longestStreak, ...}
// The game shows a total that also has a difficulty bonus, and a rank; neither
// is stored. Its gtag event "tightrope_quiz_completed" (in window.dataLayer,
// in the page the game ended in) carries both, so they come from there, or
// failing that (after a reload) from the game's own tables below.
const todayNum = Number(today().replaceAll("-", ""));
const st = ls("TR_CURRENT_GAME_SESSION");
const game = (ls("TR_GAMES_OF_THE_WEEK") ?? []).find?.(g => g?.date === todayNum);

const finished = st?.lastGameCompletedDate === todayNum
  && Array.isArray(st?.responsePoints) && !!game?.id;

const completed = (() => {
  const dl = window.dataLayer ?? [];
  for (let i = dl.length - 1; i >= 0; i--) {
    const e = dl[i];
    if (e?.[0] === "event" && e?.[1] === "tightrope_quiz_completed"
        && e?.[2]?.tightrope_quiz_date === todayNum && !e?.[2]?.tightrope_quiz_is_archived) return e[2];
  }
  return null;
})();

// The game's difficulty bonus for surviving, by weekday (rises through the
// week), and the totals each rank needs (more than); copied from its JS.
const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const BONUS = { Sunday: 320, Monday: 200, Tuesday: 220, Wednesday: 240, Thursday: 260, Friday: 280, Saturday: 300 };
const RANK_AT = {
  Monday: [1640, 1775, 2020, 2170], Tuesday: [1590, 1700, 1920, 2125],
  Wednesday: [1605, 1720, 1960, 2150], Thursday: [1630, 1745, 1985, 2170],
  Friday: [1650, 1770, 2000, 2190], Saturday: [1660, 1780, 2000, 2190],
  Sunday: [1660, 1770, 2020, 2240],
};
const RANKS = ["Great!", "High Flyer!", "Tightrope Boss!", "Walking Encyclopedia!", "Clever Funambulist!"];
const weekday = WEEKDAYS[new Date(Math.floor(todayNum / 1e4), Math.floor(todayNum / 100) % 100 - 1, todayNum % 100).getDay()];

const answerPoints = st?.totalAnswersPoints ?? 0;
const timeBonus = st?.totalTimeBonusPoints ?? 0;
const difficultyBonus = completed?.difficulty_points ?? (st?.hasWon ? BONUS[weekday] : 0);
const total = completed?.tightrope_quiz_total_points_of_the_game ?? answerPoints + timeBonus + difficultyBonus;
const rank = !st?.hasWon ? null
  : (completed?.tightrope_quiz_score_label ?? RANKS[(RANK_AT[weekday] ?? []).filter(t => total > t).length]);

// The share text's bar: one mark per question, right, wrong (or timed out),
// or never reached, then a party or a bandaged face.
const marks = Array.from({ length: 9 }, (_, i) =>
  i >= (st?.responsePoints?.length ?? 0) ? ":white_large_square:"
    : st.responsePoints[i] > 0 ? ":white_check_mark:" : ":broken_heart:");
const bar = marks.join("") + (st?.hasWon ? " :tada:" : " :face_with_head_bandage:");
