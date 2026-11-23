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
  const [sending, setSending] = useState(false);

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
      const text = newMessage.trim();
      if (!text || !chat) return;
      setSending(true);
      setNewMessage("");
      // show the user's message immediately, before waiting on the LLM
      setMessages((prev) => [...prev, { role: "user", content: text }]);
      try {
        const response = await sendMessage(chat.id, text);
        setMessages((prev) => [...prev, response]);   // then append the assistant's reply
      } catch (err) {
        setError(err.message);
        setNewMessage(text); // give the text back so the user can retry
      } finally {
        setSending(false);
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
          <button onClick={() => setChat(null)} className="text-orange-400 underline mb-2 hover:cursor-pointer">Back to chats</button>
          <h2 className="text-2xl text-orange-400">Chat: {chat.name}</h2>

          {/*showing chat messages*/}
          <div className="flex flex-col gap-3 my-3">
            <p className="text-orange-200 text-xl">All messages:</p>

            {messages.length === 0 && <p className="text-orange-200">No messages yet. Start the conversation below.</p>}
            
            {messages.map((m, i) => (
              <div
                key={i}
                className={` py-2 max-w-[75%] ${
                  m.role === "user"
                    ? "self-end text-right"
                    : "self-start"
                }`}
              >
                <p className="px-4 text-orange-400 text-lg">{m.role === "user" ? "You" : "The Muncher"}</p>
                <p className="px-4 text-orange-200 border rounded border-amber-700  bg-amber-900/40">{m.content}</p>
              </div>
            ))}
          </div>

          {/*Sending messages*/}
          <form onSubmit={handleSendMessage} className="flex gap-2 pt-2 border-t border-amber-700">
                <input value={newMessage} onChange={(e) => setNewMessage(e.target.value)} placeholder="Type your message..." className="flex-1 p-2 rounded bg-black text-white" />
                {sending ? (
                  <button className="p-2 rounded bg-orange-500 font-bold" disabled>
                    Sending...
                  </button>
                ) : (
                  <button className="p-2 rounded bg-orange-500 font-bold">
                    Send
                  </button>
                )}
          </form>
        </div>
      )}
    </>
  );
}