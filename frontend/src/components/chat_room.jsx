import { useOutletContext, Link} from 'react-router-dom';
import { useState, useEffect } from 'react';
import { getChats, createChat, getMessages, sendMessage } from '../api';

export default function ChatRoom() {
  const { topic } = useOutletContext();

  const [chats, setChats] = useState([]);
  const [chat, setChat] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [newName, setNewName] = useState("");
  const [newMessage, setNewMessage] = useState("");

  //load the topic and its chats once, when ChatRoom mounts
  useEffect(() => {
    if (!topic) return;
    getChats(topic.id)
      .then(setChats)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
    }, [topic.id]);

  // load the messages whenever a different chat is selected
  useEffect(() => {
    if (!chat) return; // no chat picked yet: nothing to load
    getMessages(chat.id)
      .then(setMessages)
      .catch((err) => setError(err.message));
  }, [chat?.id]);

  if (!topic) {
    return <p className="text-orange-200">Pick a topic on <Link to="/home" className="underline">Home</Link> first.</p>;
  }

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

  //for sending a new message in the selected chat
  async function handleSendMessage(e) {
      e.preventDefault();
      if (!newMessage.trim() || !chat) return;
      try {
        // setMessages((prev) => [...prev, { ...newMessage.trim(), role: "user" }]);   // add to the list without refetching
        const response = await sendMessage(chat.id, newMessage.trim());
        setMessages((prev) => [...prev, response]);   // add to the list without refetching
        setNewMessage("");
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
                    <button onClick={() => setChat(c)} className="w-full text-left px-3 py-2 rounded text-orange-200 hover:bg-amber-950/50">
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

          <div>
            <p className="text-orange-200 text-xl">All messages:</p>

            {messages.length === 0 && <p className="text-orange-200">No messages yet. Start the conversation below.</p>}
            
            {messages.map((m, i) => (
              <div key={i} className="border-b border-amber-700 py-1">
                <p className="text-orange-400 text-sm">{m.role === "user" ? "You" : "The Muncher"}</p>
                <p className="text-orange-200">{m.content}</p>
              </div>
            ))}
            
          </div>
          <form onSubmit={handleSendMessage} className="flex gap-2 pt-2 border-t border-amber-700">
                <input value={newMessage} onChange={(e) => setNewMessage(e.target.value)} placeholder="Type your message..." className="flex-1 p-2 rounded bg-black text-white" />
                <button className="p-2 rounded bg-orange-500 font-bold">Send</button>
          </form>
        </div>
      )}
    </>
  );
}