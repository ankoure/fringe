import type { Show } from "../api";

interface Props {
  show: Show;
  style?: React.CSSProperties;
}

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
  CHILDRENS_SHOWS: "Children's",
  CIRCUS: "Circus",
  COMEDY: "Comedy",
  EVENTS: "Events",
  EXHIBITIONS: "Exhibitions",
  MUSIC: "Music",
  OPERA: "Opera",
  SPOKEN_WORD: "Spoken Word",
  THEATRE: "Theatre",
};

export default function ShowCard({ show, style }: Props) {
  const hasThumbnail = show.thumbnail_url && show.thumbnail_url !== "nan";

  return (
    <div className="show-card" style={style}>
      {hasThumbnail && (
        <div
          className="card-image"
          style={{ backgroundImage: `url(${show.thumbnail_url})` }}
        />
      )}
      <div className="card-body">
        <div className="card-meta">
          <span className="genre-badge">{GENRE_LABELS[show.genre] ?? show.genre}</span>
          {show.duration_mins && (
            <span className="duration">{show.duration_mins} min</span>
          )}
          <span className="price">{priceLabel(show)}</span>
        </div>

        <h2 className="card-title">{show.title}</h2>

        <p className="card-venue">
          {show.venue_name}
          {show.space_name && show.space_name !== "nan" ? ` · ${show.space_name}` : ""}
        </p>

        {show.dates_display && (
          <p className="card-dates">{show.dates_display}</p>
        )}

        <p className="card-description">{show.description}</p>

        {show.content_warnings.length > 0 && (
          <div className="warning-list">
            {show.content_warnings.slice(0, 4).map((w) => (
              <span key={w} className="warning-badge">{w}</span>
            ))}
            {show.content_warnings.length > 4 && (
              <span className="warning-badge warning-badge--more">
                +{show.content_warnings.length - 4} more
              </span>
            )}
          </div>
        )}

        <div className="card-access">
          {show.wheelchair_access && <span title="Wheelchair accessible">♿</span>}
          {show.bsl_interpreted && <span title="BSL interpreted">🤟</span>}
          {show.captioned && <span title="Captioned">CC</span>}
          {show.audio_enhancement && <span title="Audio enhancement">🔊</span>}
        </div>
      </div>
    </div>
  );
}
