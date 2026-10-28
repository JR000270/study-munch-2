import { useState } from 'react';
import { register, login, getMe } from '../api';

export default function Welcome({ onSignIn }) {
  const [mode, setMode] = useState("signin"); // "signin" or "signup"
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const isSignUp = mode === "signup";

  async function handleSubmit(e) {
    e.preventDefault();               // stop the browser's own full-page form submit
    setError("");
    setLoading(true);
    try {
      if (isSignUp) await register(username, password);
      await login(username, password);   // saves the token
      const me = await getMe();          // proves the token works, gets { id, username }
      onSignIn(me);                      // hand the user up to App
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="min-h-screen flex items-center justify-center gap-16 px-8">
      <div className="max-w-md">
        <h1 className="text-9xl font-bold text-orange-500">Study Munch</h1>
        <p className="mt-4 text-4xl text-orange-200">A monster for locking in</p>
      </div>

      <form onSubmit={handleSubmit} className="w-200 flex flex-col gap-3 bg-amber-950 p-10 rounded-xl">
        <h2 className="text-4xl text-orange-400">{isSignUp ? "Create account" : "Sign in"}</h2>
        <input className="p-2 rounded bg-black text-white" placeholder="Username"
          value={username} onChange={(e) => setUsername(e.target.value)}
          autoComplete="username" required />
        <input className="p-2 rounded bg-black text-white" type="password" placeholder="Password"
          value={password} onChange={(e) => setPassword(e.target.value)}
          autoComplete={isSignUp ? "new-password" : "current-password"} required />

        {error && <p className="text-red-400 text-sm">{error}</p>}

        <button disabled={loading} className="p-2 rounded bg-orange-500 font-bold disabled:opacity-50">
          {loading ? "..." : isSignUp ? "Sign up" : "Sign in"}
        </button>
        <button type="button" className="text-sm text-orange-300 underline"
          onClick={() => { setMode(isSignUp ? "signin" : "signup"); setError(""); }}>
          {isSignUp ? "Already have an account? Sign in" : "New here? Create an account"}
        </button>
      </form>
    </section>
  );
}