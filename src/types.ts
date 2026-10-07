export type WorkKind = "pdf" | "doc";

export type Series = {
  id: string;
  title: string;
  roman?: string;
  tagline: string;
  description: string;
  cover: string;
  accent: string;
};

export type Work = {
  id: string;
  driveId: string;
  title: string;
  seriesId: string;
  season?: string;
  part?: number;
  kind: WorkKind;
  featured?: boolean;
  blurb?: string;
  date?: string;
};

export type Comment = {
  id: string;
  workId: string;
  name: string;
  body: string;
  at: string;
};

export type QuizQuestion = {
  id: string;
  seriesId?: string;
  workId?: string;
  prompt: string;
  choices: string[];
  answer: number;
  insight: string;
};
