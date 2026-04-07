import { useState, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useApp } from "../context";
import ShowCard from "./ShowCard";
import SwipeCard from "./SwipeCard";
import { recordSwipe, fetchShows, type Show } from "../api";

export default function SwipeScreen() {
  const { sessionId, filters, queue, likedShows, setLikedShows } = useApp();
  const navigate = useNavigate();

  const [remaining, setRemaining] = useState<Show[]>([...queue]);
  const [likedCount, setLikedCount] = useState(likedShows.length);
  const [lastSwipe, setLastSwipe] = useState<"left" | "right" | null>(null);
  const [swipeKey, setSwipeKey] = useState(0); // force re-render hint indicator

  useEffect(() => {
    if (!sessionId) navigate("/");
  }, [sessionId, navigate]);

  const onSwipe = useCallback(
    async (direction: "left" | "right", show: Show) => {
      const liked = direction === "right";
      setLastSwipe(direction);
      setSwipeKey((k) => k + 1);

      if (liked) {
        setLikedShows([...likedShows, show]);
        setLikedCount((c) => c + 1);
      }

      const next = remaining.filter((s) => s.id !== show.id);
      setRemaining(next);

      await recordSwipe(sessionId, show.id, liked);

      // Re-rank every 5 swipes
      if (next.length % 5 === 0 && next.length > 0) {
        const fresh = await fetchShows(sessionId, filters);
        setRemaining(fresh);
      }
    },
    [sessionId, filters, remaining, likedShows, setLikedShows]
  );

  const swipeTop = useCallback(
    (direction: "left" | "right") => {
      if (remaining.length === 0) return;
      const top = remaining[remaining.length - 1];
      onSwipe(direction, top);
    },
    [remaining, onSwipe]
  );

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "ArrowLeft") swipeTop("left");
      else if (e.key === "ArrowRight") swipeTop("right");
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [swipeTop]);

  if (!sessionId) return null;

  if (remaining.length === 0) {
    return (
      <div className="empty-screen">
        <h2>All done!</h2>
        <p>You've seen all the shows matching your filters.</p>
        <button className="btn-start" onClick={() => navigate("/liked")}>
          View your liked shows ({likedCount})
        </button>
        <button className="btn-secondary" onClick={() => navigate("/")}>
          Change filters
        </button>
      </div>
    );
  }

  // Render top 3 cards — only top one is interactive
  const visible = remaining.slice(-3);
  const topShow = visible[visible.length - 1];

  return (
    <div className="swipe-screen">
      <header className="swipe-header">
        <button className="btn-text" onClick={() => navigate("/")}>
          ← Filters
        </button>
        <span className="swipe-count">
          {remaining.length} remaining · {likedCount} liked
        </span>
        <button className="btn-text" onClick={() => navigate("/liked")}>
          Liked →
        </button>
      </header>

      {lastSwipe && (
        <div
          key={swipeKey}
          className={`swipe-indicator swipe-indicator--${lastSwipe}`}
        >
          {lastSwipe === "right" ? "❤️ Liked!" : "👎 Passed"}
        </div>
      )}

      <div className="card-stack">
        {/* Background cards (decorative, offset slightly) */}
        {visible.slice(0, -1).map((show, i) => (
          <div
            key={show.id}
            className="card-bg"
            style={{
              transform: `translateY(${(visible.length - 1 - i) * 8}px) scale(${0.96 - (visible.length - 2 - i) * 0.02})`,
              zIndex: i,
            }}
          >
            <ShowCard show={show} />
          </div>
        ))}

        {/* Top interactive card */}
        <SwipeCard
          key={topShow.id}
          onSwipe={(dir) => onSwipe(dir, topShow)}
        >
          <ShowCard show={topShow} />
        </SwipeCard>
      </div>

      <div className="swipe-buttons">
        <button
          className="swipe-btn swipe-btn--pass"
          onClick={() => swipeTop("left")}
          title="Pass"
        >
          ✕
        </button>
        <button
          className="swipe-btn swipe-btn--like"
          onClick={() => swipeTop("right")}
          title="Like"
        >
          ♥
        </button>
      </div>
    </div>
  );
}
