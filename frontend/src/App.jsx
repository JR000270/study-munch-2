import './App.css';
import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Welcome from './components/welcome';
import Layout from './components/layout';
import Home from './components/home';
import ChatRoom from './components/chat_room';
import Quizzes from './components/quizzes';
import Flashcards from './components/flashcards';
import ContextFiles from './components/context_files';
import UserPage from './components/user_page';
import { getToken, clearToken, getMe } from './api';
import { motion } from "motion/react"


function AppContent() {
  const [user, setUser] = useState(null);         // null = signed out
  const [checking, setChecking] = useState(true);

  // On first load: if a token was saved, ask the backend who it belongs to.
  useEffect(() => {
    if (!getToken()) { setChecking(false); return; }
    getMe()
      .then(setUser)
      .catch(() => clearToken())                  // expired (60 min) or invalid: discard it
      .finally(() => setChecking(false));
  }, []);

  function signOut() {
    clearToken();
    setUser(null);
  }

  if (checking) return null;   // otherwise a signed-in user briefly sees the landing page

  return (
    <div className="bg-black min-h-screen">
      <Routes>
        <Route path="/"
          element={user ? <Navigate to="/home" replace /> : <Welcome onSignIn={setUser} />} />
        {/* Pathless layout route: no URL of its own, it just wraps its children */}
        <Route element={user ? <Layout user={user} onSignOut={signOut} /> : <Navigate to="/" replace />}>
          <Route path="home" element={<Home />} />
          <Route path="chat" element={<ChatRoom />} />
          <Route path="quizzes" element={<Quizzes />} />
          <Route path="flashcards" element={<Flashcards />} />
          <Route path="files" element={<ContextFiles />} />
          <Route path="user" element={<UserPage />} />
        </Route>

        {/* Any unknown URL goes back to the start */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}

export default function App() {
  return <BrowserRouter><AppContent /></BrowserRouter>;
}