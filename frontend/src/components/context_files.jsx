import { useOutletContext, Link } from 'react-router-dom';
import { useState, useEffect, useRef } from 'react';
import { upload_source, list_sources } from '../api';

export default function ContextFiles() {
  const { topic } = useOutletContext();
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => {
      if (!topic) return;
      list_sources(topic.id)
        .then(setFiles)
        .catch((err) => setError(err.message))
        .finally(() => setLoading(false));
  }, [topic?.id]);

  // function pick(t) {
  //      // optional: jump straight in. Remove this line to stay on Home.
  // }

  {/*adding context files to the topic*/}
  async function handleAdd(e) {
      e.preventDefault();
      if (!selectedFile) return;
      setError("");          // clear the last error before trying again
      setUploading(true);
      try {
        const created = await upload_source(topic.id, selectedFile);
        setFiles((prev) => [...prev, created]);   // add to the list without refetching
        setSelectedFile(null);
        fileInputRef.current.value = "";          // file inputs can't be reset via state
      } catch (err) {
        setError(err.message);  // the backend's "detail" text, e.g. "File too large"
      } finally {
        setUploading(false);
      }
  }
  
  if (!topic) {
    {/*direct user back to home if they try to access this page without a topic selected*/}
    return <p className="text-orange-200">Pick a topic on <Link to="/home" className="underline">Home</Link> first.</p>;
  }
  return (
    <div>
      <h2 className="text-2xl text-orange-400">Context Files for {topic.name}</h2>
    
      <div className="bg-amber-900 border border-amber-500 rounded max-w-xl p-3 flex flex-col gap-2">
        <ul className="max-h-72 overflow-y-auto flex flex-col gap-1">
          {loading && <li className="text-orange-200">Loading...</li>}
          {!loading && files.length === 0 && (
            <li className="text-orange-200">No files yet. Add your first one below.</li>
          )}
          {files.map((t) => (
            <li key={t.id}>
              <button
                // onClick={() => pick(t)}
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
          {/*input for adding a new context file. `accept` only filters the picker; the backend still validates*/}
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt,.md,.pdf,.docx,.pptx,.jpeg,.jpg,.png"
            onChange={(e) => setSelectedFile(e.target.files[0] ?? null)}
            className="flex-1 text-orange-200 file:mr-2 file:px-3 file:py-1 file:rounded file:border-0 file:bg-amber-950 file:text-orange-300"
          />
          <button
            disabled={!selectedFile || uploading}
            className="px-3 rounded bg-orange-500 font-bold disabled:opacity-50 hover:cursor-pointer"
          >
            {uploading ? "Uploading..." : "Add"}
          </button>
        </form>

        {error && <p className="text-red-400 text-sm">{error}</p>}
      </div>
    </div>
  );
}