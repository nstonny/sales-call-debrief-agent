from pathlib import Path

from debrief_agent.rag.loaders.loader_factory import LoaderFactory

loader_factory = LoaderFactory()
documents = loader_factory.load_documents(Path("src/data/knowledge_base"))

print(
    f"Loaded {len(documents)} documents"
)