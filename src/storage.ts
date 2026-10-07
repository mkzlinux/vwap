const K = {
  gate: "bs-gate",
  progress: "bs-progress",
  name: "bs-name",
  xp: "bs-xp",
  claimed: "bs-claimed",
  comments: "bs-comments",
};

export type Progress = { workId: string; at: number };

export function loadProgress(): Progress | null {
  try {
    return JSON.parse(localStorage.getItem(K.progress) || "null");
  } catch {
    return null;
  }
}
export function saveProgress(workId: string) {
  localStorage.setItem(K.progress, JSON.stringify({ workId, at: Date.now() }));
}
export function loadOpened() {
  return localStorage.getItem(K.gate) === "1";
}
export function markOpened() {
  localStorage.setItem(K.gate, "1");
}
export function loadName() {
  return localStorage.getItem(K.name) || "";
}
export function saveName(n: string) {
  localStorage.setItem(K.name, n.trim());
}
export function loadXp() {
  return Number(localStorage.getItem(K.xp) || 0);
}
export function addXp(n: number) {
  const v = loadXp() + n;
  localStorage.setItem(K.xp, String(v));
  return v;
}
export function claimedSeries(): string[] {
  try {
    return JSON.parse(localStorage.getItem(K.claimed) || "[]");
  } catch {
    return [];
  }
}
export function claimSeries(id: string) {
  const s = new Set(claimedSeries());
  s.add(id);
  localStorage.setItem(K.claimed, JSON.stringify([...s]));
}

export function localComments(workId: string) {
  try {
    const all = JSON.parse(localStorage.getItem(K.comments) || "[]");
    return all.filter((c: { workId: string }) => c.workId === workId);
  } catch {
    return [];
  }
}
export function pushLocalComment(c: { id: string; workId: string; name: string; body: string; at: string }) {
  const all = JSON.parse(localStorage.getItem(K.comments) || "[]");
  all.push(c);
  localStorage.setItem(K.comments, JSON.stringify(all));
}
