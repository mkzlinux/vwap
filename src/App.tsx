import { useEffect, useMemo, useRef, useState } from "react";
import { Link, Navigate, Route, Routes, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { searchWorks, series, seriesById, siblings, workById, works, worksInSeries } from "./catalog";
import { teachingFor } from "./content";
import { dateFor, posterDate, sloganFor } from "./meta";
import { questionsFor, rankFor } from "./quiz";
import {
  addXp,
  claimSeries,
  claimedSeries,
  loadName,
  loadOpened,
  loadProgress,
  loadXp,
  markOpened,
  saveName,
  saveProgress,
} from "./storage";
import { ArcadeRun, Comments, Nav, Particles, QuizRun, Result, paintCertificate } from "./ui";
import type { Series } from "./types";

function Home() {
  const [open, setOpen] = useState<Series | null>(null);
  const cont = workById[loadProgress()?.workId || ""];
  const vols = open ? worksInSeries(open.id) : [];

  return (
    <div className="cosmos">
      <div className="cosmos-head">
        <div className="kicker">Tinotenda Gwiriri · Interactive vault</div>
        <h1>
          Select a mystery
          <em>touch a world — the volumes fan out</em>
        </h1>
        {cont && (
          <Link className="btn" to={`/read/${cont.id}`} style={{ marginTop: 8 }}>
            Resume last lamp
          </Link>
        )}
      </div>
      <div className="orbit">
        <img className="sun" src="/art/seal.png" alt="" onClick={() => setOpen(null)} />
        {series.map((s, i) => (
          <button
            key={s.id}
            className="planet"
            style={{ ["--a" as string]: (360 / series.length) * i, ["--i" as string]: i }}
            onClick={() => setOpen(s)}
            type="button"
          >
            <div className="orb">
              <img src={s.cover} alt="" />
            </div>
            <span>{s.title}</span>
          </button>
        ))}
      </div>
      {open && (
        <div className="drawer">
          <div className="drawer-top">
            <div>
              <div className="kicker">{open.tagline}</div>
              <h2>{open.title}</h2>
              <p className="lede">{open.description}</p>
            </div>
            <Link className="btn ghost" to={`/play/trial/${open.id}`}>
              Series trial
            </Link>
          </div>
          <div className="vol-grid">
            {vols.map((w) => (
              <Link className="vol" key={w.id} to={`/read/${w.id}`}>
                <small>
                  {w.season ? `Season ${w.season}` : open.title}
                  {w.part != null ? ` · ${w.part}` : ""}
                </small>
                <b>{w.title}</b>
                <div className="when">{posterDate(dateFor(w))}</div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Library() {
  const [filter, setFilter] = useState("all");
  const list = filter === "all" ? [...works].sort((a, b) => a.title.localeCompare(b.title)) : worksInSeries(filter);
  return (
    <div className="page">
      <div className="kicker">Every dated transmission</div>
      <h1>Stacks</h1>
      <p className="lede">{works.length} episodes. Slogan, date, and series kept on every cover — as the house designed Season II.</p>
      <div className="library-toolbar">
        <button className={`chip ${filter === "all" ? "on" : ""}`} onClick={() => setFilter("all")}>
          All
        </button>
        {series.map((s) => (
          <button key={s.id} className={`chip ${filter === s.id ? "on" : ""}`} onClick={() => setFilter(s.id)}>
            {s.title}
          </button>
        ))}
      </div>
      <div className="vol-grid">
        {list.map((w) => (
          <Link className="vol" key={w.id} to={`/read/${w.id}`}>
            <small>{seriesById[w.seriesId]?.title}</small>
            <b>{w.title}</b>
            <div className="when">{posterDate(dateFor(w))}</div>
          </Link>
        ))}
      </div>
    </div>
  );
}

function Broadcast() {
  const { id } = useParams();
  const work = id ? workById[id] : undefined;
  const nav = useNavigate();
  const [quizOn, setQuizOn] = useState(false);
  const [done, setDone] = useState<{ score: number; total: number } | null>(null);

  useEffect(() => {
    if (work) saveProgress(work.id);
    setQuizOn(false);
    setDone(null);
    window.scrollTo(0, 0);
  }, [work]);

  if (!work) return <Navigate to="/" replace />;
  const s = seriesById[work.seriesId];
  const { prev, next } = siblings(work);
  const body = teachingFor(work);
  const qs = questionsFor({ seriesId: work.seriesId, workId: work.id, n: 6 });

  return (
    <div className="poster">
      <div className="poster-hero">
        <div className="scan" />
        <div className="poster-stamp">
          <div className="series">
            {s.title}
            {work.season ? `  ·  SEASON ${work.season}` : ""}
            {work.part != null ? `  ·  PART ${String(work.part).replace(".5", "†")}` : ""}
          </div>
          <div className="slogan">{sloganFor(work)}</div>
          <div className="poster-date">{posterDate(dateFor(work))}</div>
          <div className="poster-title">{work.title}</div>
        </div>
      </div>
      <article className="scroll">
        {body.map((p, i) => (
          <p key={i}>{p}</p>
        ))}
      </article>
      <div className="episode-nav">
        {prev ? (
          <button className="btn ghost" type="button" onClick={() => nav(`/read/${prev.id}`)}>
            Previous
          </button>
        ) : (
          <span />
        )}
        {next && (
          <button className="btn" type="button" onClick={() => nav(`/read/${next.id}`)}>
            Next episode
          </button>
        )}
      </div>
      {!quizOn && !done && (
        <div className="quiz-box" style={{ textAlign: "center" }}>
          <h3>Episode trial</h3>
          <p className="lede" style={{ margin: "0 auto 14px" }}>
            Six questions from this series. Seventy percent claims a certificate.
          </p>
          <button className="btn" type="button" onClick={() => setQuizOn(true)}>
            Enter the court
          </button>
        </div>
      )}
      {quizOn && !done && (
        <QuizRun
          items={qs}
          onDone={(score, total) => {
            setDone({ score, total });
            addXp(score * 8);
          }}
        />
      )}
      {done && <Result score={done.score} total={done.total} title={`${s.title} · ${work.title}`} />}
      <Comments work={work} />
    </div>
  );
}

function PlayHub() {
  const xp = loadXp();
  const r = rankFor(xp);
  const claimed = claimedSeries();
  return (
    <div className="play">
      <div className="hud">
        <div>
          <div className="kicker">The game of the house</div>
          <h1 className="page" style={{ padding: 0 }}>
            Three doors, one vault
          </h1>
        </div>
        <div>
          Rank <b>{r.name}</b> · XP <b>{xp}</b> · Realms claimed <b>{claimed.length}</b>
        </div>
      </div>
      <p className="lede" style={{ margin: "12px auto 0", maxWidth: 1100 }}>
        Expedition map, Courts of Heaven trial, Word arcade. Every question is drawn from the PDFs and the dated
        transmissions.
      </p>
      <div className="play-grid">
        <Link className="play-card" to="/play/expedition" style={{ backgroundImage: "linear-gradient(to top, #05040a, transparent), url(/art/map.jpg)", backgroundSize: "cover" }}>
          <div className="kicker">01</div>
          <h3>Watcher expedition</h3>
          <p>Claim series-realms on the living map by passing their trial.</p>
          <span className="btn">Enter map</span>
        </Link>
        <Link className="play-card" to="/play/trial" style={{ backgroundImage: "linear-gradient(to top, #05040a, transparent), url(/art/court.jpg)", backgroundSize: "cover" }}>
          <div className="kicker">02</div>
          <h3>Courts of Heaven</h3>
          <p>Stand and answer. A mixed trial from the whole vault.</p>
          <span className="btn">Open court</span>
        </Link>
        <Link className="play-card" to="/play/arcade" style={{ backgroundImage: "linear-gradient(to top, #05040a, transparent), url(/art/arcade.jpg)", backgroundSize: "cover" }}>
          <div className="kicker">03</div>
          <h3>Word arcade</h3>
          <p>Forty-five seconds. Combos. No old bread.</p>
          <span className="btn">Start round</span>
        </Link>
      </div>
    </div>
  );
}

function Expedition() {
  const claimed = claimedSeries();
  return (
    <div className="page">
      <div className="kicker">Unlock the continent</div>
      <h1>Expedition</h1>
      <p className="lede">Each world is a series. Pass its trial to plant a seal. Click a realm to attempt it.</p>
      <div className="play-grid">
        {series.map((s) => {
          const on = claimed.includes(s.id);
          return (
            <Link key={s.id} className="play-card" to={`/play/trial/${s.id}`} style={{ backgroundImage: `linear-gradient(to top, #05040a, rgba(5,4,10,.4)), url(${s.cover})`, backgroundSize: "cover" }}>
              <div className="kicker">{on ? "Claimed" : "Locked light"}</div>
              <h3>{s.title}</h3>
              <p>{s.tagline}</p>
              <span className="btn">{on ? "Retake" : "Attempt"}</span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

function Trial() {
  const { seriesId } = useParams();
  const s = seriesId ? seriesById[seriesId] : undefined;
  const items = useMemo(() => questionsFor({ seriesId, n: 8 }), [seriesId]);
  const [done, setDone] = useState<{ score: number; total: number } | null>(null);
  const title = s ? `${s.title} trial` : "Courts of Heaven";
  return (
    <div className="play">
      <div className="hud">
        <div>
          <div className="kicker">{title}</div>
          <h1 className="page" style={{ padding: 0 }}>
            {s?.title ?? "The mixed court"}
          </h1>
        </div>
      </div>
      {!done && (
        <QuizRun
          items={items}
          onDone={(score, total) => {
            setDone({ score, total });
            addXp(score * 10);
            if (s && score / total >= 0.7) claimSeries(s.id);
          }}
        />
      )}
      {done && <Result score={done.score} total={done.total} title={title} />}
    </div>
  );
}

function Arcade() {
  const items = useMemo(() => questionsFor({ n: 12 }), []);
  const [done, setDone] = useState<{ score: number; total: number } | null>(null);
  return (
    <div className="play">
      <div className="hud">
        <div>
          <div className="kicker">Word arcade</div>
          <h1 className="page" style={{ padding: 0 }}>
            Catch the mystery
          </h1>
        </div>
      </div>
      {!done && (
        <ArcadeRun
          items={items}
          onDone={(score, total) => {
            setDone({ score, total });
            addXp(score * 6);
          }}
        />
      )}
      {done && <Result score={done.score} total={done.total} title="Word Arcade" />}
    </div>
  );
}

function Certificate() {
  const [sp] = useSearchParams();
  const canvas = useRef<HTMLCanvasElement>(null);
  const [name, setName] = useState(loadName());
  const title = sp.get("title") || "The Vault Trial";
  const score = `${sp.get("score") || "0"} / ${sp.get("total") || "0"}`;
  const date = new Date().toLocaleDateString("en-GB", { day: "2-digit", month: "long", year: "numeric" }).toUpperCase();

  const draw = async () => {
    if (!canvas.current) return;
    saveName(name);
    await paintCertificate({ canvas: canvas.current, name, title, score, date });
  };

  useEffect(() => {
    draw();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const download = () => {
    if (!canvas.current) return;
    const a = document.createElement("a");
    a.href = canvas.current.toDataURL("image/png");
    a.download = `bible-secrets-certificate.png`;
    a.click();
  };

  return (
    <div className="page cert-wrap">
      <div className="kicker">Winner’s seal</div>
      <h1>Certificate</h1>
      <p className="lede" style={{ marginLeft: "auto", marginRight: "auto" }}>
        Enter the name that should appear on the house seal, render, then download.
      </p>
      <div className="form" style={{ maxWidth: 480, margin: "0 auto 22px" }}>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name on the certificate" />
        <button className="btn" type="button" onClick={draw}>
          Render seal
        </button>
      </div>
      <canvas ref={canvas} />
      <div style={{ marginTop: 16 }}>
        <button className="btn" type="button" onClick={download}>
          Download PNG
        </button>
      </div>
    </div>
  );
}

function Eastern() {
  return (
    <div className="eastern">
      <div>
        <div className="kicker">Community of the house</div>
        <h1>EASTERN WALL</h1>
        <div className="lock">Coming soon</div>
        <p className="lede" style={{ margin: "18px auto 0" }}>
          A living wall of the nations — prayers, testimonies, and the next season of the house. The gate is measured.
          Until it opens, leave your word on each episode, and stand in the courts.
        </p>
      </div>
    </div>
  );
}

function SearchOverlay({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [q, setQ] = useState("");
  const hits = searchWorks(q);
  if (!open) return null;
  return (
    <div className="search-overlay" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()}>
        <input autoFocus placeholder="Seek a mystery…" value={q} onChange={(e) => setQ(e.target.value)} />
        {hits.map((w) => (
          <Link key={w.id} className="search-hit" to={`/read/${w.id}`} onClick={onClose}>
            <small>
              {seriesById[w.seriesId]?.title} · {posterDate(dateFor(w))}
            </small>
            <b>{w.title}</b>
          </Link>
        ))}
      </div>
    </div>
  );
}

export default function App() {
  const [gate, setGate] = useState(() => !loadOpened());
  const [search, setSearch] = useState(false);
  const loc = useLocation();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearch(true);
      }
      if (e.key === "Escape") setSearch(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <>
      <div className="grain" />
      <div className="vignette" />
      <Particles />
      {gate && (
        <div
          className="gate"
          onClick={() => {
            markOpened();
            setGate(false);
          }}
        >
          <div className="gate-inner">
            <img src="/art/seal.png" alt="" />
            <h2>Open the vault</h2>
            <p>We are taking over.</p>
          </div>
        </div>
      )}
      <Nav onSearch={() => setSearch(true)} />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/library" element={<Library />} />
        <Route path="/read/:id" element={<Broadcast />} />
        <Route path="/play" element={<PlayHub />} />
        <Route path="/play/expedition" element={<Expedition />} />
        <Route path="/play/trial" element={<Trial />} />
        <Route path="/play/trial/:seriesId" element={<Trial />} />
        <Route path="/play/arcade" element={<Arcade />} />
        <Route path="/certificate" element={<Certificate />} />
        <Route path="/eastern" element={<Eastern />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <SearchOverlay open={search} onClose={() => setSearch(false)} />
      <span style={{ display: "none" }}>{loc.pathname}</span>
    </>
  );
}
