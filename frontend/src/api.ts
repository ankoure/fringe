const BASE = import.meta.env.DEV ? "http://localhost:8000" : "";

export interface Show {
  id: string;
  title: string;
  genre: string;
  description: string;
  venue_name: string;
  space_name: string;
  duration_mins: number | null;
  age_restriction: string;
  age_numeric: number | null;
  content_warnings: string[];
  is_free: boolean;
  is_pwyw: boolean;
  price_min_gbp: number | null;
  price_max_gbp: number | null;
  url_website: string;
  thumbnail_url: string;
  dates_display: string;
  wheelchair_access: boolean;
  bsl_interpreted: boolean;
  captioned: boolean;
  audio_enhancement: boolean;
  cancelled: boolean;
}

export interface Filters {
  genres: string[];
  excludeWarnings: string[];
  maxPrice: number | null;
  isFree: boolean;
  maxAge: number | null;
  wheelchair: boolean;
  bsl: boolean;
  captioned: boolean;
  excludeCancelled: boolean;
  excludeSoldOut: boolean;
}

export async function createSession(): Promise<string> {
  const res = await fetch(`${BASE}/api/session`, { method: "POST" });
  const data = await res.json();
  return data.session_id;
}

export async function fetchGenres(): Promise<string[]> {
  const res = await fetch(`${BASE}/api/genres`);
  return res.json();
}

export async function fetchWarnings(): Promise<string[]> {
  const res = await fetch(`${BASE}/api/warnings`);
  return res.json();
}

export async function fetchShows(
  sessionId: string,
  filters: Filters
): Promise<Show[]> {
  const params = new URLSearchParams();
  params.set("session_id", sessionId);
  if (filters.genres.length) params.set("genres", filters.genres.join(","));
  if (filters.excludeWarnings.length)
    params.set("exclude_warnings", filters.excludeWarnings.join("|"));
  if (filters.maxPrice !== null) params.set("max_price", String(filters.maxPrice));
  if (filters.isFree) params.set("is_free", "true");
  if (filters.maxAge !== null) params.set("max_age", String(filters.maxAge));
  if (filters.wheelchair) params.set("wheelchair", "true");
  if (filters.bsl) params.set("bsl", "true");
  if (filters.captioned) params.set("captioned", "true");
  if (filters.excludeCancelled) params.set("exclude_cancelled", "true");
  if (filters.excludeSoldOut) params.set("exclude_sold_out", "true");

  const res = await fetch(`${BASE}/api/shows?${params}`);
  return res.json();
}

export async function recordSwipe(
  sessionId: string,
  showId: string,
  liked: boolean
): Promise<void> {
  await fetch(`${BASE}/api/swipe`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, show_id: showId, liked }),
  });
}

export async function fetchLiked(sessionId: string): Promise<Show[]> {
  const res = await fetch(`${BASE}/api/liked?session_id=${sessionId}`);
  return res.json();
}
