import { useOutletContext, useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { getTopics, createTopic } from '../api';

export default function Home() {
  const { user, topic, setTopic } = useOutletContext();
  const navigate = useNavigate();

  const [topics, setTopics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [newName, setNewName] = useState("");

  // Load the user's topics once, when Home mounts
  useEffect(() => {
    getTopics()
      .then(setTopics)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  function pick(t) {
    setTopic(t);
    navigate("/chat");   // optional: jump straight in. Remove this line to stay on Home.
  }

  async function handleAdd(e) {
    e.preventDefault();
    if (!newName.trim()) return;
    try {
      const created = await createTopic(newName.trim());
      setTopics((prev) => [...prev, created]);   // add to the list without refetching
      setNewName("");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <>
      <h2 className="text-2xl text-orange-400">Welcome back, {user.username}</h2>
      <p className="text-orange-400 text-xl pt-4 px-5">It's time to lock in</p>
      <p className="text-orange-400 text-xl pt-4">Topics</p>

      <div className="bg-amber-900 border border-amber-500 rounded max-w-xl p-3 flex flex-col gap-2">
        {/* max-h + overflow-y-auto: the box grows until it hits the max height, then scrolls */}
        <ul className="max-h-72 overflow-y-auto flex flex-col gap-1">
          {loading && <li className="text-orange-200">Loading...</li>}
          {!loading && topics.length === 0 && (
            <li className="text-orange-200">No topics yet. Add your first one below.</li>
          )}
          {topics.map((t) => (
            <li key={t.id}>
              <button
                onClick={() => pick(t)}
                className={`w-full text-left px-3 py-2 rounded ${
                  topic?.id === t.id ? "bg-amber-950 text-orange-300" : "text-orange-200 hover:bg-amber-950/50"
                }`}
              >
                {t.name}
              </button>
            </li>
          ))}
        </ul>

        <form onSubmit={handleAdd} className="flex gap-2 pt-2 border-t border-amber-700">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Add new topic..."
            className="flex-1 p-2 rounded bg-black text-white"
          />
          <button className="px-3 rounded bg-orange-500 font-bold">Add</button>
        </form>

        {error && <p className="text-red-400 text-sm">{error}</p>}
      </div>
    </>
  );
}