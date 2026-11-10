import { useOutletContext, Link} from 'react-router-dom';
import { useState, useEffect } from 'react';
import { getChats, createChat } from '../api';

export default function ChatRoom() {
  const { topic } = useOutletContext();

  if (!topic) {
    return <p className="text-orange-200">Pick a topic on <Link to="/home" className="underline">Home</Link> first.</p>;
  }

  const [chats, setChats] = useState([]);
  const [chat, setChat] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [newName, setNewName] = useState("");

  //load the topic and its chats once, when ChatRoom mounts
  useEffect(() => {
      getChats(topic.id)
        .then(setChats)
        .catch((err) => setError(err.message))
        .finally(() => setLoading(false));
    }, [topic.id]);

  //for adding a new chat to the topic
  async function handleAdd(e) {
      e.preventDefault();
      if (!newName.trim()) return;
      try {
        const created = await createChat(topic.id, newName.trim());
        setChats((prev) => [...prev, created]);   // add to the list without refetching
        setNewName("");
      } catch (err) {
        setError(err.message);
      }
    }
  

  return (
    <>
      {!chat && (
          <div>
            <h2 className="text-2xl text-orange-400">Chats about {topic.name}</h2>
            <div className= "border border-amber-500 rounded max-w-xl p-3 flex flex-col gap-2">
              <ul>
                {loading && <li className="text-orange-200">Loading...</li>}
                {!loading && chats.length === 0 && (
                  <li className="text-orange-200">No chats yet. Add your first one below.</li>
                  )}
                {chats.map((c) => (
                  <li key={c.id}>
                    <button onClick={() => setChat(c)} className="w-full text-left px-3 py-2 rounded">
                      {c.name}
                    </button>
                  </li>
                ))}
              </ul>

              <form onSubmit={handleAdd} className="flex gap-2 pt-2 border-t border-amber-700">
                <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="New chat name" className="flex-1 p-2 rounded bg-black text-white" />
                <button className="p-2 rounded bg-orange-500 font-bold">Add</button>
              </form>
              {error && <p className="text-red-400 text-sm">{error}</p>}
             </div>
          </div>
      )}
      {chat && (
        <div>
          <h2 className="text-2xl text-orange-400">Chat: {chat.name}</h2>
        </div>
      )}
    </>
  );
}