import { useOutletContext, Link } from 'react-router-dom';

export default function Quizzes() {
  const { topic } = useOutletContext();

  if (!topic) {
    return <p className="text-orange-200">Pick a topic on <Link to="/home" className="underline">Home</Link> first.</p>;
  }
  return <h2 className="text-2xl text-orange-400">Quizzes on {topic.name}</h2>;
}