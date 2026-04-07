import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useApp } from "../context";
import { createSession, fetchGenres, fetchShows, type Filters } from "../api";

const GENRE_LABELS: Record<string, string> = {
  CABARET: "Cabaret",
  CHILDRENS_SHOWS: "Children's Shows",
  CIRCUS: "Circus",
  COMEDY: "Comedy",
  EVENTS: "Events",
  EXHIBITIONS: "Exhibitions",
  MUSIC: "Music",
  OPERA: "Opera",
  SPOKEN_WORD: "Spoken Word",
  THEATRE: "Theatre",
};

const COMMON_WARNINGS = [
  "Strong language/swearing",
  "Scenes of a sexual nature",
  "Nudity",
  "Partial nudity",
  "Strobe lighting",
  "Loud noises",
  "Contains distressing or potentially triggering themes",
  "References to drug/alcohol misuse",
  "Audience participation",
];

export default function FilterSetup() {
  const { setSessionId, setFilters, setQueue } = useApp();
  const navigate = useNavigate();

  const [genres, setGenres] = useState<string[]>([]);
  const [selectedGenres, setSelectedGenres] = useState<string[]>([]);
  const [excludeWarnings, setExcludeWarnings] = useState<string[]>([]);
  const [maxPrice, setMaxPrice] = useState<number | null>(null);
  const [isFree, setIsFree] = useState(false);
  const [maxAge, setMaxAge] = useState<number | null>(null);
  const [wheelchair, setWheelchair] = useState(false);
  const [bsl, setBsl] = useState(false);
  const [captioned, setCaptioned] = useState(false);
  const [excludeSoldOut, setExcludeSoldOut] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchGenres().then(setGenres);
  }, []);

  function toggleGenre(g: string) {
    setSelectedGenres((prev) =>
      prev.includes(g) ? prev.filter((x) => x !== g) : [...prev, g]
    );
  }

  function toggleWarning(w: string) {
    setExcludeWarnings((prev) =>
      prev.includes(w) ? prev.filter((x) => x !== w) : [...prev, w]
    );
  }

  async function handleStart() {
    setLoading(true);
    const sid = await createSession();
    const filters: Filters = {
      genres: selectedGenres,
      excludeWarnings,
      maxPrice,
      isFree,
      maxAge,
      wheelchair,
      bsl,
      captioned,
      excludeCancelled: true,
      excludeSoldOut,
    };
    const shows = await fetchShows(sid, filters);
    setSessionId(sid);
    setFilters(filters);
    setQueue(shows);
    setLoading(false);
    navigate("/swipe");
  }

  return (
    <div className="filter-page">
      <header className="filter-header">
        <h1>Fringe Swipe</h1>
        <p>Tell us what you're in the mood for</p>
      </header>

      <section className="filter-section">
        <h2>Genres</h2>
        <p className="hint">Leave blank for all genres</p>
        <div className="chip-group">
          {genres.map((g) => (
            <button
              key={g}
              className={`chip ${selectedGenres.includes(g) ? "chip--active" : ""}`}
              onClick={() => toggleGenre(g)}
            >
              {GENRE_LABELS[g] ?? g}
            </button>
          ))}
        </div>
      </section>

      <section className="filter-section">
        <h2>Content warnings to exclude</h2>
        <p className="hint">Shows with these warnings won't appear</p>
        <div className="chip-group">
          {COMMON_WARNINGS.map((w) => (
            <button
              key={w}
              className={`chip chip--warning ${excludeWarnings.includes(w) ? "chip--excluded" : ""}`}
              onClick={() => toggleWarning(w)}
            >
              {excludeWarnings.includes(w) ? "✕ " : ""}{w}
            </button>
          ))}
        </div>
      </section>

      <section className="filter-section">
        <h2>Price</h2>
        <label className="toggle-row">
          <span>Free / Pay What You Want only</span>
          <input type="checkbox" checked={isFree} onChange={(e) => setIsFree(e.target.checked)} />
        </label>
        {!isFree && (
          <label className="range-row">
            <span>Max price: {maxPrice === null ? "any" : `£${maxPrice}`}</span>
            <input
              type="range"
              min={0}
              max={50}
              step={1}
              value={maxPrice ?? 50}
              onChange={(e) => {
                const v = parseInt(e.target.value);
                setMaxPrice(v === 50 ? null : v);
              }}
            />
          </label>
        )}
      </section>

      <section className="filter-section">
        <h2>Age suitability</h2>
        <label className="range-row">
          <span>Show me content rated up to: {maxAge === null ? "any age" : `${maxAge}+`}</span>
          <select
            value={maxAge ?? ""}
            onChange={(e) => setMaxAge(e.target.value ? parseInt(e.target.value) : null)}
          >
            <option value="">Any</option>
            <option value="5">5+</option>
            <option value="8">8+</option>
            <option value="12">12+</option>
            <option value="14">14+</option>
            <option value="16">16+</option>
            <option value="18">18+</option>
          </select>
        </label>
      </section>

      <section className="filter-section">
        <h2>Accessibility</h2>
        <label className="toggle-row">
          <span>Wheelchair accessible</span>
          <input type="checkbox" checked={wheelchair} onChange={(e) => setWheelchair(e.target.checked)} />
        </label>
        <label className="toggle-row">
          <span>BSL interpreted</span>
          <input type="checkbox" checked={bsl} onChange={(e) => setBsl(e.target.checked)} />
        </label>
        <label className="toggle-row">
          <span>Captioned</span>
          <input type="checkbox" checked={captioned} onChange={(e) => setCaptioned(e.target.checked)} />
        </label>
      </section>

      <section className="filter-section">
        <h2>Availability</h2>
        <label className="toggle-row">
          <span>Hide sold-out shows</span>
          <input type="checkbox" checked={excludeSoldOut} onChange={(e) => setExcludeSoldOut(e.target.checked)} />
        </label>
      </section>

      <div className="filter-footer">
        <button className="btn-start" onClick={handleStart} disabled={loading}>
          {loading ? "Loading shows…" : "Start swiping →"}
        </button>
      </div>
    </div>
  );
}
