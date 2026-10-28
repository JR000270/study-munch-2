import './App.css';
import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Welcome from './components/welcome';
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
        <Route path="/home"
          element={user ? (
            <div className="p-8">
              <h1 className="text-6xl text-orange-500 font-bold">Study Munch</h1>
              <p className="text-orange-200">Signed in as {user.username}</p>
              <button onClick={signOut} className="mt-4 text-orange-300 underline">Sign out</button>
            </div>
          ) : <Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}

export default function App() {
  return <BrowserRouter><AppContent /></BrowserRouter>;
}