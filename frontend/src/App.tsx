import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AppProvider } from "./context";
import FilterSetup from "./components/FilterSetup";
import SwipeScreen from "./components/SwipeScreen";
import LikedList from "./components/LikedList";
import "./App.css";

export default function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<FilterSetup />} />
          <Route path="/swipe" element={<SwipeScreen />} />
          <Route path="/liked" element={<LikedList />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AppProvider>
  );
}
