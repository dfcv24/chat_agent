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
        先用大模型分析对话内容，按主题分组后再保存
        
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
            # 先分析聊天历史内容
            analyzed_segments = self._analyze_chat_history(chat_history)
            if not analyzed_segments:
                print("⚠️  聊天历史解析失败，跳过归档")
                return True
            
            # 保存分析后的段落
            success_count = 0
            total_segments = len(analyzed_segments)
            
            for i, segment in enumerate(analyzed_segments):
                # 构建段落内容
                content = f"主题总结: {segment['topic']}\n\n详细对话:\n{segment['summary']}"
                
                # 构建元数据
                metadata = {
                    "archive_timestamp": archive_timestamp,
                    "segment_index": i,
                    "total_segments": total_segments,
                    "topic": segment['topic'],
                    "summary": segment['summary'],
                    "conversation_count": segment['conversation_count'],
                    "start_time": segment.get('start_time', ''),
                    "end_time": segment.get('end_time', ''),
                    "keywords": segment.get('keywords', []),
                    "importance_score": segment.get('importance_score', 0.5)
                }
                
                # 保存到向量数据库
                result = self.save_data(
                    content=content,
                    content_type="chat_topic_archive",
                    metadata=metadata
                )
                
                if result:
                    success_count += 1
                    print(f"✅ 保存主题段落 {i+1}/{total_segments}: {segment['topic']}")
                else:
                    print(f"⚠️  保存主题段落 {i+1}/{total_segments} 失败: {segment['topic']}")
            
            print(f"✅ 成功归档 {success_count}/{total_segments} 个主题段落到向量数据库")
            return success_count == total_segments
            
        except Exception as e:
            print(f"❌ 归档聊天历史失败: {e}")
            return False
    
    def _analyze_chat_history(self, chat_history: List[Dict]) -> List[Dict]:
        """
        使用大模型分析聊天历史，提取主题和总结
        
        Args:
            chat_history: 聊天历史列表（单一消息格式）
            
        Returns:
            分析后的段落列表
        """
        if not self.embedding_client:
            print("⚠️  没有可用的AI客户端进行分析")
            return []
        
        try:
            # 构建聊天历史文本 - 适配新的单一消息格式
            conversation_text = ""
            current_user_msg = ""
            
            for i, chat_item in enumerate(chat_history):
                timestamp = chat_item.get("timestamp", f"消息{i+1}")
                
                if "user" in chat_item:
                    current_user_msg = chat_item["user"]
                    conversation_text += f"[{timestamp}]\n用户: {current_user_msg}\n"
                elif "assistant" in chat_item or "assistent" in chat_item:
                    assistant_msg = chat_item.get("assistant", chat_item.get("assistent", ""))
                    conversation_text += f"助手: {assistant_msg}\n\n"
            
            if not conversation_text.strip():
                print("⚠️  没有有效的对话内容可分析")
                return []
            
            # 构建分析提示
            analysis_prompt = f"""
请分析以下聊天历史，将对话按主题分组并总结。要求：

1. 识别对话中的主要话题和主题转换点
2. 将相关对话分组到同一主题下
3. 为每个主题生成简洁的总结
4. 提取关键词
5. 评估每个主题的重要性（0-1分）

聊天历史：
{conversation_text}

请按以下JSON格式返回分析结果：
{{
    "segments": [
        {{
            "topic": "主题名称",
            "summary": "主题总结（50字以内）",
            "content": "相关对话内容",
            "keywords": ["关键词1", "关键词2"],
            "importance_score": 0.8,
            "conversation_count": 3,
            "start_time": "开始时间",
            "end_time": "结束时间"
        }}
    ]
}}
"""
            
            # 调用大模型分析
            response = self.embedding_client.chat.completions.create(
                model=getattr(self.config, 'MEMORY_MODEL', 'Qwen/Qwen3-8B'),
                messages=[
                    {"role": "system", "content": "你是一个专业的对话分析师，擅长分析和总结对话内容。请仔细分析对话并按要求返回JSON格式的结果。"},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.3,
                max_tokens=4000
            )
            
            # 解析响应
            analysis_text = response.choices[0].message.content
            
            # 尝试提取JSON部分
            import re
            json_match = re.search(r'\{.*\}', analysis_text, re.DOTALL)
            if json_match:
                analysis_json = json.loads(json_match.group())
                segments = analysis_json.get('segments', [])
                
                print(f"✅ 聊天历史分析完成，识别出 {len(segments)} 个主题段落")
                return segments
            else:
                print("⚠️  无法解析大模型返回的分析结果")
                print(f"原始返回: {analysis_text[:200]}...")
                return []
                
        except Exception as e:
            print(f"⚠️  聊天历史分析失败: {e}")
            return []

    def search_related_chat_history(self, query: str, limit: int = 5) -> List[Dict]:
        """
        搜索与查询相关的历史聊天记录
        优先搜索主题化的归档，然后搜索原始归档
        
        Args:
            query: 查询文本
            limit: 返回结果数量限制
            
        Returns:
            相关的聊天历史记录列表
        """
        if not self.is_available or not query.strip():
            return []
        
        try:
            # 获取查询的向量嵌入
            query_embedding = self.get_embedding(query)
            if query_embedding is None:
                return []
            
            # 搜索参数
            search_params = {
                "metric_type": "COSINE",
                "params": {"nprobe": 10}
            }
            
            # 搜索主题化归档
            topic_results = self._search_topic_archives(query_embedding, search_params, limit)
            
            return topic_results[:limit]
            
        except Exception as e:
            print(f"⚠️  搜索相关聊天历史失败: {e}")
            return []
    
    def _search_topic_archives(self, query_embedding, search_params, limit):
        """搜索主题化的聊天归档"""
        try:
            expr = 'content_type == "chat_topic_archive"'
            results = self.collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=limit,
                expr=expr,
                output_fields=["content", "metadata", "timestamp"]
            )
            
            chat_records = []
            similarity_threshold = getattr(self.config, 'HISTORY_SIMILARITY_THRESHOLD', 0.7)
            
            if results and len(results) > 0:
                for hit in results[0]:
                    if hit.score > similarity_threshold:
                        try:
                            metadata = json.loads(hit.entity.get('metadata', '{}'))
                            chat_record = {
                                'content': hit.entity.get('content', ''),
                                'score': hit.score,
                                'timestamp': hit.entity.get('timestamp', ''),
                                'archive_type': 'topic',
                                'topic': metadata.get('topic', ''),
                                'summary': metadata.get('summary', ''),
                                'keywords': metadata.get('keywords', []),
                                'importance_score': metadata.get('importance_score', 0.5),
                                'conversation_count': metadata.get('conversation_count', 0)
                            }
                            chat_records.append(chat_record)
                        except Exception as e:
                            print(f"⚠️  解析主题归档结果失败: {e}")
                            continue
            
            return chat_records
        except Exception as e:
            print(f"⚠️  搜索主题归档失败: {e}")
            return []