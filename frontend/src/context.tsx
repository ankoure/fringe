import { createContext, useContext, useState, type ReactNode } from "react";
import type { Filters, Show } from "./api";

interface AppState {
  sessionId: string;
  setSessionId: (id: string) => void;
  filters: Filters;
  setFilters: (f: Filters) => void;
  queue: Show[];
  setQueue: (q: Show[]) => void;
  likedShows: Show[];
  setLikedShows: (s: Show[]) => void;
}

const defaultFilters: Filters = {
  genres: [],
  excludeWarnings: [],
  maxPrice: null,
  isFree: false,
  maxAge: null,
  wheelchair: false,
  bsl: false,
  captioned: false,
  excludeCancelled: true,
  excludeSoldOut: false,
};

const AppContext = createContext<AppState>({} as AppState);

export function AppProvider({ children }: { children: ReactNode }) {
  const [sessionId, setSessionId] = useState("");
  const [filters, setFilters] = useState<Filters>(defaultFilters);
  const [queue, setQueue] = useState<Show[]>([]);
  const [likedShows, setLikedShows] = useState<Show[]>([]);

  return (
    <AppContext.Provider
      value={{
        sessionId,
        setSessionId,
        filters,
        setFilters,
        queue,
        setQueue,
        likedShows,
        setLikedShows,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useApp() {
  return useContext(AppContext);
}
