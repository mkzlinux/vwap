# Bible Secrets · The Vault

Cinematic, game-like library of **Bible Secrets with Tinotenda Gwiriri**.

- Interactive constellation map of series
- Broadcast covers in the Abrahamic Season II style: **WE ARE TAKING OVER** + date + series
- Extracted teaching text as a designed scroll
- Comments API (`/api/comments`) — works in `npm run dev` (writes `data/comments.json`) and on Vercel (`api/comments.js`)
- Eastern Wall — Coming Soon
- Episode / series Q&A, Courts of Heaven trial, Watcher expedition, Word arcade
- Certificate for 70%+ winners

```bash
npm install
npm run dev
```

Deploy on Vercel from this repo. Comments persist in-process on Vercel until you attach a store; locally they persist to `data/comments.json`.
