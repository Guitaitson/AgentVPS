"""
Memória Semântica com Qdrant.
Armazena conversas e contexto como vetores para busca semântica.
"""
import sys
import uuid
sys.path.insert(0, "/opt/vps-agent/core")

from typing import List, Dict, Optional
from datetime import datetime

# Qdrant client
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        PointStruct,
        VectorParams,
        Distance,
    )
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False


class SemanticMemory:
    """
    Gerencia memória semântica usando Qdrant.
    """
    
    COLLECTION_NAME = "agent_conversations"
    VECTOR_SIZE = 768  # MiniMax embeddings size
    
    def __init__(self, host: str = "127.0.0.1", port: int = 6333):
        self.host = host
        self.port = port
        self.client = None
        self._initialized = False
    
    def init(self) -> bool:
        """Inicializa conexão com Qdrant e cria collection se necessário."""
        if not QDRANT_AVAILABLE:
            print("[SemanticMemory] Qdrant client não disponível")
            return False
        
        try:
            self.client = QdrantClient(host=self.host, port=self.port)
            
            # Verificar se collection existe
            collections = self.client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if self.COLLECTION_NAME not in collection_names:
                # Criar collection
                self.client.create_collection(
                    collection_name=self.COLLECTION_NAME,
                    vectors_config=VectorParams(
                        size=self.VECTOR_SIZE,
                        distance=Distance.COSINE,
                    ),
                )
                print(f"[SemanticMemory] Collection '{self.COLLECTION_NAME}' criada")
            
            self._initialized = True
            print(f"[SemanticMemory] Conectado a Qdrant ({self.host}:{self.port})")
            return True
            
        except Exception as e:
            print(f"[SemanticMemory] Erro ao conectar: {e}")
            return False
    
    def _generate_embedding(self, text: str) -> List[float]:
        """
        Gera embedding para o texto usando API de embedding.
        Por enquanto, retorna embedding simulado.
        """
        # TODO: Integrar com MiniMax/OpenAI embedding API
        # Por enquanto, retorna hash simulado como vetor
        import hashlib
        hash_obj = hashlib.sha256(text.encode())
        hash_hex = hash_obj.hexdigest()
        
        # Converter hash em vetor de floats
        vector = []
        for i in range(0, len(hash_hex), 8):
            chunk = hash_hex[i:i+8]
            vector.append(int(chunk, 16) / 0xFFFFFFFF)
        
        # Padding para tamanho fixo
        while len(vector) < self.VECTOR_SIZE:
            vector.append(0.0)
        
        return vector[:self.VECTOR_SIZE]
    
    def save_conversation(
        self,
        user_id: str,
        message: str,
        response: str,
        intent: str,
        metadata: Optional[Dict] = None,
    ) -> Optional[str]:
        """
        Salva uma conversa na memória semântica.
        Retorna o ID do ponto criado.
        """
        if not self._initialized or not self.client:
            return None
        
        try:
            # Criar texto combinando mensagem e resposta
            full_text = f"Usuário: {message}\nAgente: {response}"
            
            # Gerar embedding
            vector = self._generate_embedding(full_text)
            
            # Criar payload
            payload = {
                "user_id": user_id,
                "message": message,
                "response": response,
                "intent": intent,
                "created_at": datetime.now().isoformat(),
            }
            if metadata:
                payload.update(metadata)
            
            # ID único
            point_id = str(uuid.uuid4())
            
            # Salvar no Qdrant
            self.client.upsert(
                collection_name=self.COLLECTION_NAME,
                points=[
                    PointStruct(
                        id=point_id,
                        vector=vector,
                        payload=payload,
                    )
                ]
            )
            
            return point_id
            
        except Exception as e:
            print(f"[SemanticMemory] Erro ao salvar: {e}")
            return None
    
    def search_similar(
        self,
        query: str,
        user_id: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict]:
        """
        Busca conversas similares ao query.
        """
        if not self._initialized or not self.client:
            return []
        
        try:
            # Gerar embedding do query
            query_vector = self._generate_embedding(query)
            
            # Buscar no Qdrant
            results = self.client.search(
                collection_name=self.COLLECTION_NAME,
                query_vector=query_vector,
                limit=limit,
                query_filter=None,
            )
            
            # Formatar resultados
            similar = []
            for hit in results:
                similar.append({
                    "id": hit.id,
                    "score": hit.score,
                    "message": hit.payload.get("message", ""),
                    "response": hit.payload.get("response", ""),
                    "intent": hit.payload.get("intent", ""),
                    "created_at": hit.payload.get("created_at", ""),
                })
            
            return similar
            
        except Exception as e:
            print(f"[SemanticMemory] Erro na busca: {e}")
            return []
    
    def get_user_history(
        self,
        user_id: str,
        limit: int = 10,
    ) -> List[Dict]:
        """
        Recupera histórico de conversas de um usuário.
        """
        if not self._initialized or not self.client:
            return []
        
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            
            results = self.client.scroll(
                collection_name=self.COLLECTION_NAME,
                limit=limit,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="user_id", match=MatchValue(value=user_id))
                    ]
                ),
            )
            
            history = []
            for point in results[0]:
                history.append({
                    "id": point.id,
                    "message": point.payload.get("message", ""),
                    "response": point.payload.get("response", ""),
                    "intent": point.payload.get("intent", ""),
                    "created_at": point.payload.get("created_at", ""),
                })
            
            return history
            
        except Exception as e:
            print(f"[SemanticMemory] Erro ao buscar histórico: {e}")
            return []
    
    def delete_user_history(self, user_id: str) -> bool:
        """
        Remove todas as memórias de um usuário.
        """
        if not self._initialized or not self.client:
            return False
        
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            
            self.client.delete(
                collection_name=self.COLLECTION_NAME,
                points_selector=Filter(
                    must=[
                        FieldCondition(key="user_id", match=MatchValue(value=user_id))
                    ]
                ),
            )
            return True
            
        except Exception as e:
            print(f"[SemanticMemory] Erro ao deletar: {e}")
            return False


# Instância global
semantic_memory = SemanticMemory()
