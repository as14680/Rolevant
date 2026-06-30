# Rolevant

> **Your most relevant PM roles, intelligently surfaced.**

Rolevant is an AI-powered job search dashboard built specifically for Product Managers. It aggregates the latest PM roles from across the web, scores each one against your resume and profile using Claude AI, and helps you prep a tailored application in one click — so you spend your time on the right roles, not searching for them.

---

## Features

### Live Job Aggregation
Rolevant pulls from multiple sources every time you refresh, giving you a consolidated feed of the latest PM roles posted across the internet — no manual searching required.

| Source | Type | Notes |
|---|---|---|
| RemoteOK | API | 30–50 remote PM roles per fetch |
| Remotive | API | Curated remote product roles |
| Arbeitnow | API | Global PM listings |
| We Work Remotely | RSS | Management & product roles |
| Remote.co PM | RSS | Dedicated PM feed |
| HackerNews Jobs | RSS | Startup & tech PM roles |
| JSearch (RapidAPI) | API | LinkedIn + Indeed + Glassdoor *(optional, free tier)* |

### AI Fit Scoring (0–100)
Claude AI reads the full job description alongside your resume and profile, then returns a structured fit score broken down across five dimensions:

- **Role & seniority alignment** (25%)
- **Skills overlap** (25%)
- **Domain / industry fit** (20%)
- **Location & remote policy** (15%)
- **Compensation alignment** (15%)

Each job gets a letter grade (A–D), a plain-English rationale, your strongest matches, gaps to address, and a recommendation: `Strong Apply`, `Apply`, `Maybe`, or `Skip`.

### Seniority Filter
Filter the job feed by detected seniority level — automatically parsed from job titles:

`All Levels` · `Junior` · `Mid` · `Senior` · `Principal` · `Director+`

Live counts update alongside the filter tabs so you always know how many roles are at each level.

### Years of Experience (YOE) Filters
Two sliders let you narrow results by the minimum and maximum years of experience a role requires — extracted directly from job descriptions using pattern matching. Useful when you want to filter out roles that are clearly too junior or too senior.

### One-Click Application Prep
Hit the **✦ Prep** button on any scored job and Rolevant generates two things:

1. **Tailored Resume** — your resume rewritten and reordered to match the specific role, emphasizing the most relevant experience and language from the job description.
2. **Cover Letter** — a three-paragraph cover letter: a hook that references the company's product, a middle paragraph making the case for you as the best PM for this role, and a call to action.

Both are displayed side-by-side in a modal with one-click copy and a direct link to the job posting. Generated materials are cached so you never pay for the same prep twice.

### Application Tracking
Every job moves through a clear pipeline:

```
Fetched → Pending (unscored) → To Review (scored) → Applied / Maybe / Skipped
```

The **History** tab tracks everything you've acted on, with the ability to reset any job back to `To Review`.

### Settings
Configure everything from the UI — no config file editing needed:

- **Profile** — name, title, years of experience, target roles, preferred industries, salary range, deal breakers, priorities
- **LinkedIn URL** — passed to Claude as additional context for scoring
- **Resume** — paste your full resume in markdown or plain text
- **Job Sources** — toggle individual sources on/off per refresh
- **JSearch API Key** — add your RapidAPI key to unlock LinkedIn and Indeed results

---

## Screenshots

> *(coming soon — run locally to see the dashboard)*

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.9+, FastAPI, Uvicorn |
| Database | SQLite (WAL mode) |
| AI | Anthropic Claude (`claude-opus-4-7`) with prompt caching |
| Job Sources | REST APIs + RSS via `feedparser` + `requests` |
| Frontend | Vanilla JS, single-file HTML/CSS (no build step) |

---

## Getting Started

### Prerequisites

- Python 3.9 or higher
- An [Anthropic API key](https://console.anthropic.com/)
- *(Optional)* A [RapidAPI key](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch) for LinkedIn/Indeed results (free tier: 200 req/month)

### 1. Clone the repo

```bash
git clone https://github.com/as14680/Rolevant.git
cd Rolevant
```

### 2. Install dependencies

```bash
pip3 install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and add your API key:

```env
ANTHROPIC_API_KEY=sk-ant-...

# Optional — enables LinkedIn + Indeed via JSearch (RapidAPI)
# JSEARCH_API_KEY=your_rapidapi_key_here
```

### 4. Start the dashboard

```bash
python3 run.py serve
```

Open **http://localhost:8000** in your browser.

### 5. First-time setup

1. Go to **Settings** in the sidebar
2. Fill in your **profile** (title, years of experience, target roles, skills, salary range)
3. Paste your **resume** in the resume field
4. Add your **LinkedIn URL**
5. Click **Save Changes**
6. Click **↻ Refresh Jobs** — this fetches the latest PM roles and auto-scores them with Claude
7. Switch to the **To Review** tab and start acting on your matches

---

## Usage

### Refreshing Jobs

Click **↻ Refresh Jobs** in the sidebar at any time. Rolevant will:
1. Fetch the latest listings from all active sources
2. Deduplicate against jobs already in the database
3. Automatically score up to 20 new jobs with Claude

Jobs that were fetched but not yet scored show as **Pending** (orange). You can score them manually with the **⚡ Score Pending** button.

### Filtering

Use the filter row to narrow your feed:

- **Status tabs** (To Review / Pending / Maybe / All) — your pipeline stages
- **Seniority tabs** (All / Junior / Mid / Senior / Principal / Director+) — filter by role level
- **YOE sliders** — set a minimum and maximum years-of-experience requirement

All filters combine — you can view "Senior" + "5+ YOE" scored jobs simultaneously.

### Applying

For each scored job you have four actions:

| Action | What it does |
|---|---|
| **✓ Apply** | Marks as applied, moves to History |
| **✦ Prep** | Opens one-click prep modal (tailored resume + cover letter) |
| **~ Maybe** | Saves to your Maybe list for later |
| **✕ Skip** | Dismisses the role |

The **✦ Prep** button is the core workflow: click it, wait ~20–40 seconds for Claude to generate your materials, copy the tailored resume or cover letter, then click **Open Job Posting →** to apply.

### Adding LinkedIn / Indeed

1. Sign up at [RapidAPI](https://rapidapi.com/) (free)
2. Subscribe to the [JSearch API](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch) (free tier: 200 requests/month)
3. Copy your API key
4. In Rolevant **Settings**, paste the key into the **JSearch API Key** field
5. Enable the **JSearch (LinkedIn/Indeed)** toggle
6. Click **Save Changes**, then **↻ Refresh Jobs**

---

## CLI Commands

```bash
# Start the web dashboard
python3 run.py serve

# Fetch + score jobs without starting the server
python3 run.py refresh
```

---

## Project Structure

```
Rolevant/
├── app.py            # FastAPI server — all API endpoints
├── ai_engine.py      # Claude integration — scoring + prep generation
├── fetcher.py        # Job fetching from APIs and RSS feeds
├── db.py             # SQLite database layer
├── config.py         # Default configuration values
├── run.py            # CLI entry point
├── requirements.txt
├── .env.example
└── static/
    └── index.html    # Full dashboard UI (single-file, no build step)
```

### Data Flow

```
Refresh triggered
       │
       ▼
fetcher.fetch_all()          ← pulls from all active sources
       │
       ▼
db.save_jobs()               ← deduplicates by URL, inserts new rows
       │
       ▼
ai_engine.score_unscored()   ← Claude scores each pending job
       │
       ▼
db.save_analysis()           ← stores score + structured analysis
       │
       ▼
Dashboard (index.html)       ← reads from /api/jobs, renders cards
```

### Seniority Detection

Seniority is detected from the job title using keyword matching at fetch time:

| Level | Keywords matched |
|---|---|
| `junior` | junior, associate pm, jr., entry level |
| `mid` | *(default — no keyword match)* |
| `senior` | senior, sr. |
| `principal` | principal, staff pm, lead pm |
| `director+` | director, vp, vice president, head of product, cpo |

### Prompt Caching

To minimise API costs, Rolevant uses Anthropic's prompt caching on the system prompt. The system prompt contains the full candidate profile and resume — the largest part of each scoring call. This is marked with `cache_control: ephemeral` and cached for 5 minutes, meaning all jobs scored in a single batch share the same cached context.

---

## Roadmap

- [ ] Email digest — daily summary of top-scored new roles
- [ ] Auto-refresh on a schedule (cron)
- [ ] Company research panel — quick snapshot of the company alongside the job
- [ ] Interview prep mode — question bank based on job description + your gaps
- [ ] Bulk export — export your applied jobs to CSV
- [ ] Dark/light mode toggle

---

## Contributing

Pull requests are welcome. For significant changes, open an issue first to discuss what you'd like to change.

1. Fork the repo
2. Create your feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "Add your feature"`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a pull request

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">Built with Claude AI · FastAPI · SQLite</p>
