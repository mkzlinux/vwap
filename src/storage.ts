const KEY = "bible-secrets-vault";

export type Progress = {
  workId: string;
  at: number;
};

export function loadProgress(): Progress | null {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Progress) : null;
  } catch {
    return null;
  }
}

export function saveProgress(workId: string) {
  localStorage.setItem(KEY, JSON.stringify({ workId, at: Date.now() }));
}

export function loadOpened(): boolean {
  return localStorage.getItem(KEY + "-gate") === "1";
}

export function markOpened() {
  localStorage.setItem(KEY + "-gate", "1");
}
