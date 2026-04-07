/**
 * Draggable swipe card — no external library needed.
 * Drag/throw left = pass, right = like.
 */
import { useRef, useState, type ReactNode } from "react";

interface Props {
  onSwipe: (direction: "left" | "right") => void;
  children: ReactNode;
}

const SWIPE_THRESHOLD = 80; // px before a drag is counted as a swipe
const ROTATION_FACTOR = 0.08; // degrees per px of horizontal drag

export default function SwipeCard({ onSwipe, children }: Props) {
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [swiping, setSwiping] = useState(false);
  const startRef = useRef<{ x: number; y: number } | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  function handlePointerDown(e: React.PointerEvent) {
    // Only respond to primary pointer (finger or left-click)
    if (e.button !== undefined && e.button !== 0) return;
    startRef.current = { x: e.clientX, y: e.clientY };
    containerRef.current?.setPointerCapture(e.pointerId);
    setSwiping(true);
  }

  function handlePointerMove(e: React.PointerEvent) {
    if (!startRef.current) return;
    setOffset({
      x: e.clientX - startRef.current.x,
      y: e.clientY - startRef.current.y,
    });
  }

  function handlePointerUp() {
    if (!startRef.current) return;
    const { x } = offset;
    startRef.current = null;
    setSwiping(false);

    if (Math.abs(x) >= SWIPE_THRESHOLD) {
      onSwipe(x > 0 ? "right" : "left");
    } else {
      // Snap back
      setOffset({ x: 0, y: 0 });
    }
  }

  const rotation = offset.x * ROTATION_FACTOR;
  const opacity = Math.max(0, 1 - Math.abs(offset.x) / 300);

  return (
    <div
      ref={containerRef}
      className="swipe-card-wrapper"
      style={{
        transform: `translate(${offset.x}px, ${offset.y}px) rotate(${rotation}deg)`,
        transition: swiping ? "none" : "transform 0.3s ease, opacity 0.3s ease",
        opacity,
        cursor: swiping ? "grabbing" : "grab",
        touchAction: "none",
        userSelect: "none",
      }}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerUp}
    >
      {/* Swipe hint overlays */}
      {offset.x > 20 && (
        <div className="swipe-hint swipe-hint--like" style={{ opacity: Math.min(1, offset.x / SWIPE_THRESHOLD) }}>
          ♥ Like
        </div>
      )}
      {offset.x < -20 && (
        <div className="swipe-hint swipe-hint--pass" style={{ opacity: Math.min(1, -offset.x / SWIPE_THRESHOLD) }}>
          ✕ Pass
        </div>
      )}
      {children}
    </div>
  );
}
