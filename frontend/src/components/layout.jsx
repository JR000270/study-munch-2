import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';

const links = [
  { to: "/home", label: "Home" },
  { to: "/chat", label: "Chats" },
  { to: "/quizzes", label: "Quizzes" },
  { to: "/flashcards", label: "Flashcards" },
  { to: "/files", label: "Files" },
];

const TOPIC_KEY = "studymunch_topic";

export default function Layout({ user, onSignOut }) {
  const [topic, setTopicState] = useState(() => {
    // a function passed to useState runs only on the first render
    try { return JSON.parse(localStorage.getItem(TOPIC_KEY)); }
    catch { return null; }
  });

  function setTopic(t) {
    setTopicState(t);
    if (t) localStorage.setItem(TOPIC_KEY, JSON.stringify(t));   // localStorage only stores strings
    else localStorage.removeItem(TOPIC_KEY);
  }

  function handleSignOut() {
    setTopic(null);   // otherwise the next person to sign in on this browser inherits your topic
    onSignOut();
  }

  const [collapsed, setCollapsed] = useState(false); 

  // NavLink calls this with { isActive }, so the current page's link can be highlighted
  const linkClass = ({ isActive }) =>
    `block px-3 py-2 rounded ${isActive ? "bg-amber-950 text-orange-400" : "text-orange-200 hover:bg-amber-950/50"}`;

  return (
    <div className="h-screen flex flex-col">
      <header className="px-6 py-3 border-b border-amber-900">
        <h1 className="text-3xl font-bold text-orange-500">Study Munch</h1>
        <p className="text-orange-200 text-sm">{topic ? `Munching on: ${topic.name}` : "No topic selected"}</p>
      </header>

      <div className="flex flex-1 min-h-0">
        <aside className={`${collapsed ? "w-14" : "w-64"} flex flex-col border-r border-amber-900 p-3 transition-all`}>
          <button onClick={() => setCollapsed(!collapsed)} className="self-end text-orange-400">
            {collapsed ? ">>" : "<<"}
          </button>

          {!collapsed && (
            <>
              <nav className="mt-2 flex flex-col gap-1">
                {links.map((link) => (
                  <NavLink key={link.to} to={link.to} className={linkClass}>
                    {link.label}
                  </NavLink>
                ))}
              </nav>

              {/* mt-auto pushes this to the bottom */}
              <div className="mt-auto flex flex-col gap-1">
                <NavLink to="/user" className={linkClass}>{user.username}</NavLink>
                <button onClick={handleSignOut} className="text-left px-3 text-sm text-orange-300 underline">
                  Sign out
                </button>
              </div>
            </>
          )}
        </aside>

        <main className="flex-1 overflow-y-auto p-6">
          <Outlet context={{ user, topic, setTopic }} />   {/* space for the different sub pages like chat room ,quizzes, etc. Passing the context & functions like the user and topic */}
        </main>
      </div>
    </div>
  );
}