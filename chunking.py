from llama_index.core import Document
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core.node_parser import SentenceSplitter
from dotenv import load_dotenv
from sqlmodel import Session, select
from database.models import Source, Chunk
import uuid


load_dotenv("keys.env")
embed_model = OpenAIEmbedding(model="text-embedding-3-small")


def ingest_source(session: Session, source: Source, documents: list[Document]) -> int:

    splitter = SentenceSplitter(chunk_size=512, chunk_overlap=50)
    # 1. Split the documents into nodes (chunks)
    nodes = splitter.get_nodes_from_documents(documents)
    # 2. Embed all the chunk texts in one batch call
    texts = [node.get_content() for node in nodes]
    embeddings = embed_model.get_text_embedding_batch(texts)
    # 3. Create a Chunk row for each: source_id, chunk_index, content, embedding
    for i, (node, embedding) in enumerate(zip(nodes, embeddings)):
        session.add(Chunk(source_id=source.id, chunk_index=i,
                        content=node.get_content(), embedding=embedding))

    # 4. Commit, and return how many chunks were saved
    session.commit()
    return  len(nodes)


def search_chunks(session: Session, topic_id: uuid.UUID, question: str, k: int = 5, max_distance: float = .60) -> list[tuple[Chunk, Source, float]]:
    query_embedding = embed_model.get_query_embedding(question)
    distance = Chunk.embedding.cosine_distance(query_embedding).label("distance")
    statement = (
        select(Chunk, Source, distance)
        .join(Source, Chunk.source_id == Source.id)
        .where(Source.topic_id == topic_id, distance < max_distance)
        .order_by(distance)
        .limit(k)
    )

    return list(session.exec(statement).all())

