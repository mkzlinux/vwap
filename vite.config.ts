import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import fs from "node:fs";
import path from "node:path";

const file = path.resolve("data/comments.json");

function readAll(): unknown[] {
  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    return [];
  }
}
function writeAll(rows: unknown[]) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(rows, null, 2));
}

function commentsApi(): Plugin {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handle = (req: any, res: any, next: () => void) => {
    const url: string = req.originalUrl || req.url || "";
    if (!url.startsWith("/api/comments")) return next();
    res.setHeader("Content-Type", "application/json");
    res.setHeader("Access-Control-Allow-Origin", "*");
    if (req.method === "OPTIONS") {
      res.statusCode = 200;
      res.end("");
      return;
    }
    if (req.method === "GET") {
      const u = new URL(url, "http://local");
      const workId = u.searchParams.get("workId") || "";
      const all = readAll() as { workId: string }[];
      res.end(JSON.stringify(workId ? all.filter((c) => c.workId === workId) : all));
      return;
    }
    if (req.method === "POST") {
      const chunks: Buffer[] = [];
      req.on("data", (c: Buffer) => chunks.push(c));
      req.on("end", () => {
        try {
          const body = JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
          const item = {
            id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
            workId: String(body.workId || ""),
            name: String(body.name || "").slice(0, 48),
            body: String(body.body || "").slice(0, 800),
            at: new Date().toISOString(),
          };
          const all = readAll();
          all.push(item);
          writeAll(all);
          res.statusCode = 201;
          res.end(JSON.stringify(item));
        } catch {
          res.statusCode = 400;
          res.end(JSON.stringify({ error: "bad json" }));
        }
      });
      return;
    }
    res.statusCode = 405;
    res.end("{}");
  };

  return {
    name: "comments-api",
    configureServer(server) {
      server.middlewares.use(handle);
    },
    configurePreviewServer(server) {
      server.middlewares.use(handle);
    },
  };
}

export default defineConfig({
  plugins: [react(), commentsApi()],
  server: { host: "0.0.0.0", port: 5173, allowedHosts: true },
  preview: { host: "0.0.0.0", port: 4173, allowedHosts: true },
});
