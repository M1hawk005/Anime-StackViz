// Thin typed client for the read-only serving API. The base URL is injected at
// build time (VITE_API_BASE) so the same bundle points at local or hosted API.
const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://localhost:8000";

export interface SequelPrediction {
  canonical_id: string;
  title_romaji: string | null;
  season_year: number | null;
  average_score: number | null;
  popularity: number | null;
  got_sequel: number;
  sequel_probability: number;
}

export interface HiddenGem {
  title_romaji: string | null;
  title_english: string | null;
  quality: number | null;
  average_score: number | null;
  mal_score: number | null;
  popularity: number | null;
  season_year: number | null;
  gem_score: number | null;
}

export interface Franchise {
  tag: string;
  total_questions: number;
  peak_period: string;
  peak_count: number;
  active_months: number;
}

async function getJSON<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => getJSON<{ status: string; products: Record<string, number> }>("/health"),
  sequels: (limit = 50) => getJSON<SequelPrediction[]>(`/sequels?limit=${limit}`),
  gems: (limit = 50) => getJSON<HiddenGem[]>(`/gems?limit=${limit}`),
  buzz: (limit = 50) => getJSON<Franchise[]>(`/buzz?limit=${limit}`),
};
