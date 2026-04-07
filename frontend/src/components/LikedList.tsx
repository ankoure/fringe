import { useNavigate } from "react-router-dom";
import { useApp } from "../context";
import type { Show } from "../api";

function priceLabel(show: Show): string {
  if (show.is_free) return "Free";
  if (show.is_pwyw) return "Pay What You Want";
  if (show.price_min_gbp !== null && show.price_max_gbp !== null) {
    if (show.price_min_gbp === show.price_max_gbp)
      return `£${show.price_min_gbp.toFixed(2)}`;
    return `£${show.price_min_gbp.toFixed(2)} – £${show.price_max_gbp.toFixed(2)}`;
  }
  return "";
}

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

export default function LikedList() {
  const { likedShows } = useApp();
  const navigate = useNavigate();

  return (
    <div className="liked-page">
      <header className="liked-header">
        <button className="btn-text" onClick={() => navigate("/swipe")}>
          ← Keep swiping
        </button>
        <h1>Your Fringe List</h1>
        <span>{likedShows.length} show{likedShows.length !== 1 ? "s" : ""}</span>
      </header>

      {likedShows.length === 0 ? (
        <div className="liked-empty">
          <p>No liked shows yet — go swipe some!</p>
          <button className="btn-start" onClick={() => navigate("/swipe")}>
            Start swiping
          </button>
        </div>
      ) : (
        <ul className="liked-list">
          {likedShows.map((show) => (
            <li key={show.id} className="liked-item">
              {show.thumbnail_url && show.thumbnail_url !== "nan" && (
                <img
                  src={show.thumbnail_url}
                  alt={show.title}
                  className="liked-thumb"
                />
              )}
              <div className="liked-info">
                <h3>{show.title}</h3>
                <p className="liked-meta">
                  <span className="genre-badge">{GENRE_LABELS[show.genre] ?? show.genre}</span>
                  {" · "}{show.venue_name}
                  {show.duration_mins ? ` · ${show.duration_mins} min` : ""}
                </p>
                <p className="liked-dates">{show.dates_display}</p>
                <p className="liked-price">{priceLabel(show)}</p>
                {show.content_warnings.length > 0 && (
                  <p className="liked-warnings">
                    {show.content_warnings.slice(0, 3).join(" · ")}
                  </p>
                )}
              </div>
              <div className="liked-actions">
                {show.url_website && show.url_website !== "nan" && (
                  <a
                    href={show.url_website}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn-tickets"
                  >
                    Tickets →
                  </a>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
