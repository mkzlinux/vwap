import { useEffect, useMemo, useState } from "react";
import { Link, Navigate, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";
import {
  downloadUrl,
  previewUrl,
  searchWorks,
  series,
  seriesById,
  siblings,
  workById,
  works,
  worksInSeries,
} from "./catalog";
import { loadOpened, loadProgress, markOpened, saveProgress } from "./storage";
import type { Work } from "./types";

function Tome({ work, cover }: { work: Work; cover: string }) {
  const s = seriesById[work.seriesId];
  return (
    <Link className="tome" to={`/read/${work.id}`}>
      <div className="tome-cover">
        <div className="spine" />
        <img src={cover} alt="" />
        <div className="tome-meta">
          <div className="tome-series">{s?.title}</div>
          <div className="tome-title">{work.title}</div>
          {work.part != null && <div className="tome-part">Vol. {String(work.part).replace(".5", "†")}</div>}
        </div>
      </div>
    </Link>
  );
}

function Rail({ title, subtitle, items }: { title: string; subtitle?: string; items: Work[] }) {
  if (!items.length) return null;
  return (
    <section className="section">
      <div className="section-head">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
      </div>
      <div className="rail">
        {items.map((work) => (
          <Tome key={work.id} work={work} cover={seriesById[work.seriesId]?.cover ?? "/art/hero.jpg"} />
        ))}
      </div>
    </section>
  );
}

function Nav({ onSearch }: { onSearch: () => void }) {
  return (
    <header className="nav">
      <Link to="/" className="brand">
        <img src="/art/seal.png" alt="Bible Secrets seal" />
        <span className="brand-text">
          <span className="brand-kicker">The Vault</span>
          <span className="brand-name">Bible Secrets</span>
        </span>
      </Link>
      <nav className="nav-links">
        <Link className="hide-sm" to="/library">
          Library
        </Link>
        <Link className="hide-sm" to="/about">
          The House
        </Link>
        <button className="search-btn" onClick={onSearch}>
          Seek
        </button>
      </nav>
    </header>
  );
}

function Home() {
  const continueId = loadProgress()?.workId;
  const cont = continueId ? workById[continueId] : undefined;
  const featured = works.filter((w) => w.featured);
  const hero = featured[0] ?? works[0];

  return (
    <div>
      <section className="hero">
        <div className="hero-bg" />
        <div className="hero-inner">
          <img className="seal-hero" src="/art/seal.png" alt="" />
          <div className="kicker">Tinotenda Gwiriri · The Living Library</div>
          <h1>
            Bible Secrets
            <span>where the revealed things become ours</span>
          </h1>
          <p>
            A cinematic sanctum for every teaching in the vault — Days of Noah, the return of the priest-king, the
            Abrahamic mysteries, and the sealed Kruptos Protocol. Read them here, in the light.
          </p>
          <div className="cta-row">
            <Link className="btn" to={cont ? `/read/${cont.id}` : `/read/${hero.id}`}>
              {cont ? "Continue reading" : "Open the first volume"}
            </Link>
            <Link className="btn ghost" to="/library">
              Enter the stacks
            </Link>
          </div>
        </div>
      </section>

      <div className="featured-grid">
        <Link className="feature-card" to="/read/10swHqoEyakOyTEBDZldDBgfsSfz6eZpg">
          <img src="/art/kruptos.jpg" alt="" />
          <div className="feature-copy">
            <div className="kicker">Featured volume</div>
            <h3>The Kruptos Protocol</h3>
            <p>TRoM Volume III. A sealed work for those learning to handle what was hidden.</p>
            <span className="btn">Read in the vault</span>
          </div>
        </Link>
        <Link className="feature-card" to="/series/noah">
          <img src="/art/noah.jpg" alt="" />
          <div className="feature-copy">
            <div className="kicker">Epic series</div>
            <h3>The Days of Noah</h3>
            <p>Thirty-five movements: watchers, courts, and blood.</p>
            <span className="btn ghost">Browse the series</span>
          </div>
        </Link>
      </div>

      {cont && <Rail title="Resume" subtitle="The last lamp you left burning" items={[cont]} />}

      {series.map((s) => (
        <Rail key={s.id} title={s.title} subtitle={s.tagline} items={worksInSeries(s.id)} />
      ))}

      <section className="manifesto">
        <blockquote>
          “The secret things belong unto the Lord our God, but the things which are revealed belong to us and to our
          children forever.”
        </blockquote>
        <cite>Deuteronomy 29:29 · Bible Secrets Defined</cite>
      </section>

      <section className="section">
        <div className="section-head">
          <h2>The stacks</h2>
          <p>Every series kept in the house.</p>
        </div>
        <div className="series-grid">
          {series.map((s) => (
            <Link key={s.id} className="series-tile" to={`/series/${s.id}`}>
              <img src={s.cover} alt="" />
              <div className="veil" />
              <div className="copy">
                <span>{worksInSeries(s.id).length} volumes</span>
                <h3>{s.title}</h3>
              </div>
            </Link>
          ))}
        </div>
      </section>

      <footer className="footer">Bible Secrets with Tinotenda Gwiriri · The Vault</footer>
    </div>
  );
}

function Library() {
  const [filter, setFilter] = useState("all");
  const list = filter === "all" ? works : worksInSeries(filter);
  const sorted = useMemo(() => {
    if (filter !== "all") return list;
    return [...works].sort((a, b) => a.title.localeCompare(b.title));
  }, [filter, list]);

  return (
    <div className="page">
      <div className="page-kicker">The complete collection</div>
      <h1>Library</h1>
      <p className="lede">
        {works.length} teachings drawn from the original Drive vault. Open any volume and read it in the sanctum — no
        leaving the house.
      </p>
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
      <div className="works-grid">
        {sorted.map((work) => (
          <Tome key={work.id} work={work} cover={seriesById[work.seriesId]?.cover ?? "/art/hero.jpg"} />
        ))}
      </div>
    </div>
  );
}

function SeriesPage() {
  const { id } = useParams();
  const s = id ? seriesById[id] : undefined;
  if (!s) return <Navigate to="/library" replace />;
  const items = worksInSeries(s.id);
  return (
    <div>
      <section className="hero" style={{ minHeight: "62vh" }}>
        <div
            className="hero-bg"
            style={{
              background: `linear-gradient(to top, #07060a, rgba(7,6,10,.4)), url(${s.cover}) center/cover no-repeat`,
            }}
          />
        <div className="hero-inner">
          <div className="kicker">{s.tagline}</div>
          <h1>{s.title}</h1>
          <p>{s.description}</p>
          <div className="cta-row">
            <Link className="btn" to={`/read/${items[0].id}`}>
              Begin the series
            </Link>
          </div>
        </div>
      </section>
      <Rail title={`${items.length} volumes`} items={items} />
    </div>
  );
}

function About() {
  return (
    <div className="page">
      <div className="page-kicker">The house</div>
      <h1>Bible Secrets</h1>
      <p className="lede">
        Not every word is suitable for everyone, and not all secrets wish to be held. These teachings are alive. When
        they are revealed, Deuteronomy 29:29 says they no longer remain only with Him — they belong to us, and to our
        children, that we may do them.
      </p>
      <p className="lede">
        This vault gathers the original library of Tinotenda Gwiriri: the Abrahamic arc, Heis, the Word of God, the
        unmasking, meditation, the Days of Noah, the Return of Melchizedek, and the comic issues. Read them as they were
        placed in the house — in sequence, in the light, without leaving the page.
      </p>
      <div className="series-grid">
        {series.map((s) => (
          <Link key={s.id} className="series-tile" to={`/series/${s.id}`}>
            <img src={s.cover} alt="" />
            <div className="veil" />
            <div className="copy">
              <span>{s.tagline}</span>
              <h3>{s.title}</h3>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

function Reader() {
  const { id } = useParams();
  const work = id ? workById[id] : undefined;
  const navigate = useNavigate();

  useEffect(() => {
    if (work) saveProgress(work.id);
  }, [work]);

  if (!work) return <Navigate to="/library" replace />;
  const s = seriesById[work.seriesId];
  const { prev, next } = siblings(work);

  return (
    <div className="reader-shell">
      <div className="reader-bar">
        <div className="reader-title">
          <small>
            <Link to={`/series/${s.id}`}>{s.title}</Link>
          </small>
          <strong>{work.title}</strong>
        </div>
        <div className="reader-actions">
          <Link to="/">Vault</Link>
          {prev && (
            <button onClick={() => navigate(`/read/${prev.id}`)} type="button">
              Previous
            </button>
          )}
          {next && (
            <button onClick={() => navigate(`/read/${next.id}`)} type="button">
              Next
            </button>
          )}
          <a href={downloadUrl(work)} target="_blank" rel="noreferrer">
            Download
          </a>
        </div>
      </div>
      <div className="reader-stage">
        <iframe title={work.title} src={previewUrl(work)} allow="autoplay" />
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
        <input
          autoFocus
          placeholder="Seek a mystery…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <div className="search-results">
          {q && hits.length === 0 && <div className="empty">Nothing in the vault matches.</div>}
          {hits.map((w) => (
            <Link key={w.id} className="search-hit" to={`/read/${w.id}`} onClick={onClose}>
              <small>{seriesById[w.seriesId]?.title}</small>
              <b>{w.title}</b>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [gate, setGate] = useState(() => !loadOpened());
  const [search, setSearch] = useState(false);
  const loc = useLocation();
  const isReader = loc.pathname.startsWith("/read/");

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
      {!isReader && <div className="vignette" />}
      {gate && (
        <div
          className="gate"
          onClick={() => {
            markOpened();
            setGate(false);
          }}
        >
          <div>
            <img src="/art/seal.png" alt="" />
            <h2>Open the vault</h2>
            <p>The revealed things belong to us.</p>
          </div>
        </div>
      )}
      {!isReader && <Nav onSearch={() => setSearch(true)} />}
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/library" element={<Library />} />
        <Route path="/series/:id" element={<SeriesPage />} />
        <Route path="/about" element={<About />} />
        <Route path="/read/:id" element={<Reader />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <SearchOverlay open={search} onClose={() => setSearch(false)} />
    </>
  );
}
