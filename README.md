# reddit-topics

A small, **read-only** script that shows the top posts (title, score, comment count, link) of three public subreddits — r/technology, r/privacy, r/gadgets — so a personal, ad-free blog can see which technology topics people are discussing. Blog posts are written from official sources; Reddit content is not republished.

## What it does / does not do

- Reads `GET https://oauth.reddit.com/r/<subreddit>/top?t=day&limit=25` with an application-only OAuth token (`client_credentials`, "script" app).
- Keeps only `title`, `score`, `num_comments`, `permalink`.
- No posting, commenting, voting or messaging. No user login, profiles, private data or comment bodies.
- Reddit data is not republished, sold, shared, or used to train any machine learning or AI model.
- Optional `--save DIR` writes one JSON file per run; files older than 48 hours are deleted on the next run.
- About 4 requests per run (1 token + 3 listings), 2 seconds apart, once or twice a day.
- User-Agent: `script:naver-blog-topics:v0.1.0 (by /u/<username>)`.

## Usage

Python 3.9+ standard library only.

```
set REDDIT_CLIENT_ID=...
set REDDIT_CLIENT_SECRET=...
set REDDIT_USERNAME=...
python reddit_topics.py --period day --limit 25
python reddit_topics.py --dry-run      # shows the planned requests, no network
```

Credentials are read from environment variables only and are never stored in this repository.

## Policies followed

Reddit Data API Wiki, Responsible Builder Policy, Data API Terms. Access is used only after Reddit approves the request.
