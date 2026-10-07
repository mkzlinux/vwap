let mem = globalThis.__bsComments || [];
globalThis.__bsComments = mem;

export default async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  if (req.method === "OPTIONS") return res.status(200).end();

  if (req.method === "GET") {
    const workId = String(req.query.workId || "");
    const list = workId ? mem.filter((c) => c.workId === workId) : mem;
    return res.status(200).json(list);
  }

  if (req.method === "POST") {
    const body = typeof req.body === "string" ? JSON.parse(req.body || "{}") : req.body || {};
    const name = String(body.name || "").slice(0, 48).trim();
    const text = String(body.body || "").slice(0, 800).trim();
    const workId = String(body.workId || "").trim();
    if (!name || !text || !workId) return res.status(400).json({ error: "Missing fields" });
    const item = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      workId,
      name,
      body: text,
      at: new Date().toISOString(),
    };
    mem.push(item);
    if (mem.length > 2000) mem = mem.slice(-2000);
    globalThis.__bsComments = mem;
    return res.status(201).json(item);
  }

  return res.status(405).json({ error: "Method not allowed" });
}
