from typing import List, Dict
from mcn_layer import remember as m_remember, query as m_query, maintain as m_maintain

class MCNClient:
    @staticmethod
    def remember(vectors: List[List[float]], meta: List[Dict]) -> None:
        m_remember(vectors, meta)

    @staticmethod
    def query(vectors: List[List[float]], topk: int = 5):
        return m_query(vectors, topk=topk)

    @staticmethod
    def maintain() -> None:
        m_maintain()
