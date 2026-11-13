# TODO

## P1

- Also need to account for multiple games being played in the same day --
  discord announcements need to stack for that user and points and time need to be summed

- Cross with friends
    - Have a new "co-op" tag
        - Automatically send link to join when they start typing
        - ":sun: @player started @game <title>!\njoin them at <url>"
    - Output scores as
        - ":sun: n player(s) played @game <title>\n1. @player1 <score1>\n2. @player2 <score2>..." (sorted by score)
        - Log completion time as that denoted by site
        - Whenever completing multiple in a day, just increment their score
        - Score is number of squares filled, don't know if "give answer" counts to this
    - Time in leaderboard is just total cumulative time

## P2

- Remove auto-refreshing to just refresh on demand
- Let players download their own results
- Statistics board: per game and per person
    - Elo / rating system
- Send notifications when running out on time as a reminder to play
- Help button in top right to explain features

## Ideas

- `/report @game-tag <share-text>` command to report broken games
    - Sends capture of network / localStorage to admin view
    - Logs in leaderboard as "manual" to maintain streak
- session syncing
    - Sync cookies and localStorage between devices per user
- See if we can allow logins to accounts for saved progress
    - Try an un-man-in-the-middle strategy
        - Redirect them to the actual site so they can login
        - When they get back attempt to fetch their token for them?
            - Probably not possible

## Games

- https://squaredle.app/
- https://playplain.app/play

- https://googlefeud.com/feudle/
- https://framed.wtf/
- https://www.lyricle.app/
- https://www.cinenerdle.app/
- https://www.thewikipediagame.com/
- https://www.vulture.com/article/daily-movie-grid-trivia-game-cinematrix.html
- https://originle.io/mattias/?day=3
- https://playdaily.org/noillirk
- https://listdle.com/
- https://playdaily.org/
