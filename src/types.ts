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
};
