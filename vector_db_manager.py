"""
向量数据库管理器
负责Milvus向量数据库的初始化、数据保存和搜索功能
"""

import os
import json
import hashlib
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
import numpy as np

try:
    from pymilvus import (
        connections,
        Collection,
        CollectionSchema,
        FieldSchema,
        DataType,
        utility
    )
    MILVUS_AVAILABLE = True
except ImportError:
    MILVUS_AVAILABLE = False
    print("⚠️  PyMilvus未安装，向量数据库功能将不可用")

try:
    from openai import OpenAI
    EMBEDDING_AVAILABLE = True
except ImportError:
    EMBEDDING_AVAILABLE = False
    print("⚠️  OpenAI客户端未安装，文本嵌入功能将不可用")


class VectorDBManager:
    """向量数据库管理器"""
    
    def __init__(self, config=None):
        """
        初始化向量数据库管理器
        
        Args:
            config: 配置对象
        """
        if config is None:
            from config import ChatConfig
            config = ChatConfig()
            
        self.config = config
        self.collection_name = getattr(config, 'MILVUS_COLLECTION_NAME', 'chat_agent_test')
        self.host = getattr(config, 'MILVUS_HOST', 'localhost')
        self.port = getattr(config, 'MILVUS_PORT', '19530')
        self.dim = getattr(config, 'EMBEDDING_DIM', 1024)  # 调整为硅基流动embedding的维度
        
        self.collection = None
        self.embedding_client = None
        self._is_connected = False
        
        # 初始化
        self._initialize_embedding_client()
        self._initialize_milvus()
    
    def _initialize_embedding_client(self):
        """初始化嵌入API客户端"""
        if not EMBEDDING_AVAILABLE:
            print("⚠️  OpenAI客户端不可用，将使用随机向量")
            return
            
        try:
            # 使用硅基流动的embedding API
            if hasattr(self.config, 'API_KEY') and self.config.API_KEY:
                self.embedding_client = OpenAI(
                    api_key=self.config.API_KEY,
                    base_url=self.config.API_BASE_URL
                )
                print(f"✅ Embedding API客户端初始化成功")
            else:
                print("⚠️  未找到API密钥，embedding功能将不可用")
                self.embedding_client = None
        except Exception as e:
            print(f"⚠️  Embedding API客户端初始化失败: {e}")
            self.embedding_client = None
    
    def _initialize_milvus(self):
        """初始化Milvus连接和集合"""
        if not MILVUS_AVAILABLE:
            print("⚠️  Milvus不可用，向量搜索功能将被禁用")
            return
            
        try:
            # 连接到Milvus
            connections.connect(
                alias="default",
                host=self.host,
                port=self.port
            )
            self._is_connected = True
            print(f"✅ Milvus连接成功: {self.host}:{self.port}")
            
            # 创建或获取集合
            self._setup_collection()
            
        except Exception as e:
            print(f"⚠️  Milvus连接失败: {e}")
            self._is_connected = False
    
    def _setup_collection(self):
        """设置Milvus集合"""
        try:
            # 检查集合是否存在
            if utility.has_collection(self.collection_name):
                self.collection = Collection(self.collection_name)
                print(f"✅ 集合已存在: {self.collection_name}")
            else:
                # 创建新集合
                self._create_collection()
                
            # 确保集合已加载
            if not self.collection.has_index():
                self._create_index()
                
            self.collection.load()
            print(f"✅ 集合已加载: {self.collection_name}")
            
        except Exception as e:
            print(f"⚠️  集合设置失败: {e}")
            self.collection = None
    
    def _create_collection(self):
        """创建新的Milvus集合"""
        # 定义字段
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=128),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="content_type", dtype=DataType.VARCHAR, max_length=50),
            FieldSchema(name="metadata", dtype=DataType.VARCHAR, max_length=1000),
            FieldSchema(name="timestamp", dtype=DataType.VARCHAR, max_length=50),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dim)
        ]
        
        # 创建集合模式
        schema = CollectionSchema(fields, f"知识库集合: {self.collection_name}")
        
        # 创建集合
        self.collection = Collection(self.collection_name, schema)
        print(f"✅ 集合创建成功: {self.collection_name}")
    
    def _create_index(self):
        """为向量字段创建索引"""
        index_params = {
            "metric_type": "COSINE",  # 使用余弦相似度
            "index_type": "IVF_FLAT",
            "params": {"nlist": 1024}
        }
        
        self.collection.create_index("embedding", index_params)
        print("✅ 向量索引创建成功")
    
    @property
    def is_available(self) -> bool:
        """检查向量数据库是否可用"""
        return (MILVUS_AVAILABLE and 
                self._is_connected and 
                self.collection is not None and
                self.embedding_client is not None)
    
    def get_embedding(self, text: str) -> Optional[List[float]]:
        """
        获取文本的向量嵌入
        
        Args:
            text: 输入文本
            
        Returns:
            向量嵌入列表
        """
        if not text.strip():
            return None
            
        if self.embedding_client is None:
            # 如果没有嵌入客户端，返回随机向量（仅用于测试）
            np.random.seed(hash(text) % 2**32)
            return np.random.rand(self.dim).tolist()
        
        try:
            # 使用硅基流动的embedding API
            embedding_model = getattr(self.config, 'EMBEDDING_MODEL_NAME', 'BAAI/bge-m3')
            response = self.embedding_client.embeddings.create(
                model=embedding_model,
                input=text,
                encoding_format="float"
            )
            
            embedding = response.data[0].embedding
            return embedding
            
        except Exception as e:
            print(f"⚠️  文本嵌入失败: {e}")
            # 失败时返回随机向量作为fallback
            np.random.seed(hash(text) % 2**32)
            return np.random.rand(self.dim).tolist()
    
    def save_data(self, 
                  content: str, 
                  content_type: str = "text",
                  metadata: Dict[str, Any] = None) -> Optional[str]:
        """
        保存数据到向量数据库
        
        Args:
            content: 内容文本
            content_type: 内容类型 (text, conversation, knowledge等)
            metadata: 元数据
            
        Returns:
            数据ID，失败返回None
        """
        if not self.is_available:
            print("⚠️  向量数据库不可用")
            return None
        
        if not content.strip():
            print("⚠️  内容为空，跳过保存")
            return None
        
        try:
            # 生成唯一ID
            content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
            timestamp = datetime.now().isoformat()
            data_id = f"{content_type}_{timestamp}_{content_hash[:8]}"
            
            # 获取向量嵌入
            embedding = self.get_embedding(content)
            if embedding is None:
                print("⚠️  无法获取文本嵌入")
                return None
            
            # 准备数据
            entities = [
                [data_id],  # id
                [content],  # content
                [content_type],  # content_type
                [json.dumps(metadata or {}, ensure_ascii=False)],  # metadata
                [timestamp],  # timestamp
                [embedding]  # embedding
            ]
            
            # 插入数据
            self.collection.insert(entities)
            self.collection.flush()
            
            print(f"✅ 数据保存成功: {data_id}")
            return data_id
            
        except Exception as e:
            print(f"⚠️  数据保存失败: {e}")
            return None
    
    def search_similar(self, 
                      query_text: str, 
                      limit: int = 5,
                      content_type_filter: Optional[str] = None,
                      similarity_threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        搜索相似内容
        
        Args:
            query_text: 查询文本
            limit: 返回结果数量限制
            content_type_filter: 内容类型过滤
            similarity_threshold: 相似度阈值
            
        Returns:
            搜索结果列表
        """
        if not self.is_available:
            print("⚠️  向量数据库不可用")
            return []
        
        if not query_text.strip():
            return []
        
        try:
            # 获取查询向量
            query_embedding = self.get_embedding(query_text)
            if query_embedding is None:
                return []
            
            # 搜索参数
            search_params = {
                "metric_type": "COSINE",
                "params": {"nprobe": 10}
            }
            
            # 构建过滤表达式
            expr = None
            if content_type_filter:
                expr = f'content_type == "{content_type_filter}"'
            
            # 执行搜索
            results = self.collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=limit,
                expr=expr,
                output_fields=["content", "content_type", "metadata", "timestamp"]
            )
            
            # 处理结果
            formatted_results = []
            for hits in results:
                for hit in hits:
                    # 检查相似度阈值
                    if hit.score >= similarity_threshold:
                        try:
                            metadata = json.loads(hit.entity.get('metadata', '{}'))
                        except:
                            metadata = {}
                            
                        formatted_results.append({
                            'id': hit.id,
                            'content': hit.entity.get('content', ''),
                            'content_type': hit.entity.get('content_type', ''),
                            'metadata': metadata,
                            'timestamp': hit.entity.get('timestamp', ''),
                            'similarity': float(hit.score)
                        })
            
            print(f"✅ 搜索完成，找到 {len(formatted_results)} 条相关结果")
            return formatted_results
            
        except Exception as e:
            print(f"⚠️  搜索失败: {e}")
            return []
    
    def search_by_content_type(self, content_type: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        按内容类型搜索数据
        
        Args:
            content_type: 内容类型
            limit: 结果数量限制
            
        Returns:
            搜索结果列表
        """
        if not self.is_available:
            return []
        
        try:
            # 查询表达式
            expr = f'content_type == "{content_type}"'
            
            # 执行查询
            results = self.collection.query(
                expr=expr,
                output_fields=["content", "content_type", "metadata", "timestamp"],
                limit=limit
            )
            
            # 格式化结果
            formatted_results = []
            for result in results:
                try:
                    metadata = json.loads(result.get('metadata', '{}'))
                except:
                    metadata = {}
                    
                formatted_results.append({
                    'id': result['id'],
                    'content': result.get('content', ''),
                    'content_type': result.get('content_type', ''),
                    'metadata': metadata,
                    'timestamp': result.get('timestamp', '')
                })
            
            return formatted_results
            
        except Exception as e:
            print(f"⚠️  按类型查询失败: {e}")
            return []
    
    def delete_data(self, data_id: str) -> bool:
        """
        删除数据
        
        Args:
            data_id: 数据ID
            
        Returns:
            是否删除成功
        """
        if not self.is_available:
            return False
        
        try:
            expr = f'id == "{data_id}"'
            self.collection.delete(expr)
            self.collection.flush()
            print(f"✅ 数据删除成功: {data_id}")
            return True
            
        except Exception as e:
            print(f"⚠️  数据删除失败: {e}")
            return False
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        获取集合统计信息
        
        Returns:
            统计信息字典
        """
        if not self.is_available:
            return {}
        
        try:
            stats = self.collection.num_entities
            return {
                'total_entities': stats,
                'collection_name': self.collection_name,
                'embedding_dim': self.dim,
                'is_available': True
            }
        except Exception as e:
            print(f"⚠️  获取统计信息失败: {e}")
            return {'is_available': False, 'error': str(e)}
    
    def close(self):
        """关闭连接"""
        try:
            if self._is_connected:
                connections.disconnect("default")
                print("✅ Milvus连接已关闭")
        except Exception as e:
            print(f"⚠️  关闭连接失败: {e}")
    
    def save_chat_history_archive(self, chat_history: List[Dict], archive_timestamp: str = None) -> bool:
        """
        将聊天历史保存到向量数据库作为归档
        
        Args:
            chat_history: 聊天历史列表
            archive_timestamp: 归档时间戳，为None时使用当前时间
            
        Returns:
            保存是否成功
        """
        if not chat_history:
            print("⚠️  聊天历史为空，跳过归档")
            return True
            
        if archive_timestamp is None:
            archive_timestamp = datetime.now().isoformat()
        
        try:
            # 批量保存聊天记录
            success_count = 0
            
            for i, chat_item in enumerate(chat_history):
                # 构建对话内容
                conversation_text = f"用户: {chat_item.get('user', '')}\n助手: {chat_item.get('bot', '')}"
                
                # 元数据
                metadata = {
                    "original_timestamp": chat_item.get("timestamp", ""),
                    "archive_timestamp": archive_timestamp,
                    "conversation_index": i,
                    "total_conversations": len(chat_history),
                    "user_message": chat_item.get('user', ''),
                    "bot_response": chat_item.get('bot', '')
                }
                
                # 保存到向量数据库
                result = self.save_data(
                    content=conversation_text,
                    content_type="chat_archive",
                    metadata=metadata
                )
                
                if result:
                    success_count += 1
                else:
                    print(f"⚠️  保存第{i+1}条对话失败")
            
            print(f"✅ 成功归档 {success_count}/{len(chat_history)} 条聊天记录到向量数据库")
            return success_count == len(chat_history)
            
        except Exception as e:
            print(f"❌ 归档聊天历史失败: {e}")
            return False


# 全局向量数据库管理器实例
_global_vector_db = None


def get_vector_db_manager(config=None) -> VectorDBManager:
    """
    获取全局向量数据库管理器实例
    
    Args:
        config: 配置对象
        
    Returns:
        向量数据库管理器实例
    """
    global _global_vector_db
    
    if _global_vector_db is None:
        _global_vector_db = VectorDBManager(config)
    
    return _global_vector_db


def reset_vector_db_manager():
    """重置全局向量数据库管理器"""
    global _global_vector_db
    if _global_vector_db:
        _global_vector_db.close()
    _global_vector_db = None
