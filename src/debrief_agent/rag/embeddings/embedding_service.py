from langchain_openai import OpenAIEmbeddings
from pydantic import SecretStr
from debrief_agent.core.config import OPENAI_API_KEY


embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    api_key=SecretStr(OPENAI_API_KEY),
)
