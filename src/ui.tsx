import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import type { Comment, QuizQuestion, Work } from "./types";
import { loadName, localComments, pushLocalComment, saveName } from "./storage";

export function Particles() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    if (!ctx) return;
    let raf = 0;
    const dots = Array.from({ length: 60 }, () => ({
      x: Math.random(),
      y: Math.random(),
      r: Math.random() * 1.6 + 0.3,
      s: Math.random() * 0.15 + 0.03,
    }));
    const draw = () => {
      c.width = innerWidth;
      c.height = innerHeight;
      ctx.clearRect(0, 0, c.width, c.height);
      ctx.fillStyle = "rgba(224,184,58,.55)";
      for (const d of dots) {
        d.y -= d.s / 120;
        if (d.y < 0) d.y = 1;
        ctx.beginPath();
        ctx.arc(d.x * c.width, d.y * c.height, d.r, 0, Math.PI * 2);
        ctx.fill();
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, []);
  return <canvas className="particles" ref={ref} />;
}

export function Nav({ onSearch }: { onSearch: () => void }) {
  return (
    <header className="nav">
      <Link to="/" className="brand">
        <img src="/art/seal.png" alt="" />
        <span>
          <span className="brand-kicker">Live transmission</span>
          <span className="brand-name">Bible Secrets</span>
        </span>
      </Link>
      <nav className="nav-links">
        <Link className="hide-sm" to="/">
          Map
        </Link>
        <Link className="hide-sm" to="/library">
          Stacks
        </Link>
        <Link to="/play">Play</Link>
        <Link className="hide-sm" to="/eastern">
          Eastern Wall
        </Link>
        <button className="search-btn" onClick={onSearch} type="button">
          Seek
        </button>
      </nav>
    </header>
  );
}

export function Comments({ work }: { work: Work }) {
  const [rows, setRows] = useState<Comment[]>([]);
  const [name, setName] = useState(loadName());
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let live = true;
    fetch(`/api/comments?workId=${encodeURIComponent(work.id)}`)
      .then((r) => r.json())
      .then((d) => {
        if (!live) return;
        const server = Array.isArray(d) ? d : [];
        const local = localComments(work.id);
        const map = new Map<string, Comment>();
        [...server, ...local].forEach((c) => map.set(c.id, c));
        setRows([...map.values()].sort((a, b) => a.at.localeCompare(b.at)));
      })
      .catch(() => setRows(localComments(work.id)));
    return () => {
      live = false;
    };
  }, [work.id]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !body.trim()) return;
    setBusy(true);
    saveName(name);
    const optimistic: Comment = {
      id: `local-${Date.now()}`,
      workId: work.id,
      name: name.trim(),
      body: body.trim(),
      at: new Date().toISOString(),
    };
    try {
      const res = await fetch("/api/comments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workId: work.id, name: name.trim(), body: body.trim() }),
      });
      const saved = res.ok ? await res.json() : optimistic;
      pushLocalComment(saved);
      setRows((r) => [...r, saved]);
      setBody("");
    } catch {
      pushLocalComment(optimistic);
      setRows((r) => [...r, optimistic]);
      setBody("");
    }
    setBusy(false);
  };

  return (
    <section className="comments">
      <h3>House comments</h3>
      {rows.length === 0 && <p style={{ fontFamily: "var(--serif)", color: "var(--muted)" }}>Be the first voice on this transmission.</p>}
      {rows.map((c) => (
        <div className="comment" key={c.id}>
          <strong>{c.name}</strong>
          <small>{new Date(c.at).toLocaleString()}</small>
          <p>{c.body}</p>
        </div>
      ))}
      <form className="form" onSubmit={submit}>
        <input placeholder="Your name in the house" value={name} onChange={(e) => setName(e.target.value)} />
        <textarea placeholder="Leave a word…" value={body} onChange={(e) => setBody(e.target.value)} />
        <button className="btn" disabled={busy} type="submit">
          Post to the wall
        </button>
      </form>
    </section>
  );
}

export function QuizRun({
  items,
  onDone,
}: {
  items: QuizQuestion[];
  onDone: (score: number, total: number) => void;
}) {
  const [i, setI] = useState(0);
  const [picked, setPicked] = useState<number | null>(null);
  const [score, setScore] = useState(0);
  const q = items[i];
  if (!q) return null;

  const choose = (n: number) => {
    if (picked != null) return;
    setPicked(n);
    if (n === q.answer) setScore((s) => s + 1);
  };
  const next = () => {
    if (i + 1 >= items.length) {
      onDone(score, items.length);
      return;
    }
    setI(i + 1);
    setPicked(null);
  };

  return (
    <div className="quiz-box">
      <h3>
        Question {i + 1} / {items.length}
      </h3>
      <div className="q">
        <p>{q.prompt}</p>
        {q.choices.map((c, n) => {
          let cls = "choice";
          if (picked != null) {
            if (n === q.answer) cls += " good";
            else if (n === picked) cls += " bad";
          } else if (picked === n) cls += " on";
          return (
            <button key={c} className={cls} type="button" onClick={() => choose(n)}>
              {c}
            </button>
          );
        })}
        {picked != null && <div className="insight">{q.insight}</div>}
      </div>
      {picked != null && (
        <button className="btn" type="button" onClick={next}>
          {i + 1 >= items.length ? "Receive verdict" : "Next"}
        </button>
      )}
    </div>
  );
}

export function ArcadeRun({
  items,
  seconds = 45,
  onDone,
}: {
  items: QuizQuestion[];
  seconds?: number;
  onDone: (score: number, total: number) => void;
}) {
  const [i, setI] = useState(0);
  const [score, setScore] = useState(0);
  const [left, setLeft] = useState(seconds);
  const scoreRef = useRef(0);
  const iRef = useRef(0);

  useEffect(() => {
    const t = setInterval(() => {
      setLeft((s) => {
        if (s <= 1) {
          clearInterval(t);
          onDone(scoreRef.current, items.length);
          return 0;
        }
        return s - 1;
      });
    }, 1000);
    return () => clearInterval(t);
  }, [items.length, onDone]);

  const q = items[i];
  if (!q || left <= 0) return null;

  const hit = (n: number) => {
    if (n === q.answer) {
      scoreRef.current += 1;
      setScore(scoreRef.current);
    }
    if (iRef.current + 1 >= items.length) {
      onDone(scoreRef.current, items.length);
      return;
    }
    iRef.current += 1;
    setI(iRef.current);
  };

  return (
    <div className="quiz-box">
      <div className="timer">00:{String(left).padStart(2, "0")} · combo {score}</div>
      <div className="q">
        <p>{q.prompt}</p>
        {q.choices.map((c, n) => (
          <button key={c} className="choice" type="button" onClick={() => hit(n)}>
            {c}
          </button>
        ))}
      </div>
    </div>
  );
}

export function Result({
  score,
  total,
  title,
}: {
  score: number;
  total: number;
  title: string;
}) {
  const nav = useNavigate();
  const pct = Math.round((score / Math.max(total, 1)) * 100);
  const win = pct >= 70;
  return (
    <div className="quiz-box" style={{ textAlign: "center" }}>
      <h3>{win ? "You prevailed" : "The court is not finished"}</h3>
      <p className="lede" style={{ margin: "0 auto 16px" }}>
        {title} · {score}/{total} · {pct}%
      </p>
      {win ? (
        <button className="btn" type="button" onClick={() => nav(`/certificate?score=${score}&total=${total}&title=${encodeURIComponent(title)}`)}>
          Claim certificate
        </button>
      ) : (
        <p style={{ color: "var(--muted)" }}>Seventy percent opens the seal. Return and try the trial again.</p>
      )}
    </div>
  );
}

export async function paintCertificate(opts: {
  canvas: HTMLCanvasElement;
  name: string;
  title: string;
  score: string;
  date: string;
}) {
  const ctx = opts.canvas.getContext("2d");
  if (!ctx) return;
  const w = 1600;
  const h = 1100;
  opts.canvas.width = w;
  opts.canvas.height = h;
  const bg = new Image();
  bg.src = "/art/cert.jpg";
  const seal = new Image();
  seal.src = "/art/seal.png";
  await Promise.all([
    new Promise((r) => {
      bg.onload = r;
      bg.onerror = r;
    }),
    new Promise((r) => {
      seal.onload = r;
      seal.onerror = r;
    }),
  ]);
  ctx.drawImage(bg, 0, 0, w, h);
  ctx.fillStyle = "rgba(8,6,4,.28)";
  ctx.fillRect(0, 0, w, h);
  if (seal.width) ctx.drawImage(seal, w / 2 - 70, 70, 140, 140);
  ctx.textAlign = "center";
  ctx.fillStyle = "#e8d48a";
  ctx.font = "22px Cinzel, serif";
  ctx.fillText("HOUSE OF BIBLE SECRETS  ·  TINOTENDA GWIRIRI", w / 2, 250);
  ctx.font = "70px Cinzel, serif";
  ctx.fillText("CERTIFICATE", w / 2, 340);
  ctx.font = "italic 28px Cormorant Garamond, serif";
  ctx.fillText("This seal is given to", w / 2, 420);
  ctx.fillStyle = "#fff6d2";
  ctx.font = "64px Cormorant Garamond, serif";
  ctx.fillText(opts.name || "A child of the house", w / 2, 510);
  ctx.fillStyle = "#e8d48a";
  ctx.font = "26px Cormorant Garamond, serif";
  ctx.fillText("who prevailed in", w / 2, 580);
  ctx.font = "36px Cinzel, serif";
  ctx.fillText(opts.title.toUpperCase(), w / 2, 640);
  ctx.font = "24px Outfit, sans-serif";
  ctx.fillText(`${opts.score}   ·   ${opts.date}`, w / 2, 720);
  ctx.font = "italic 22px Cormorant Garamond, serif";
  ctx.fillText("The revealed things belong to us and to our children forever.", w / 2, 820);
  ctx.font = "16px Cinzel, serif";
  ctx.fillText("DEUTERONOMY 29:29", w / 2, 860);
}
