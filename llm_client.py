"""
大语言模型客户端工具类
提供统一的大模型调用接口，方便在项目中复用
"""

import json
from typing import List, Dict, Optional, Any
from openai import OpenAI


class LLMClient:
    """大语言模型客户端"""
    
    def __init__(self, config=None):
        """
        初始化LLM客户端
        
        Args:
            config: 配置对象，如果为None则自动加载
        """
        if config is None:
            from config import ChatConfig
            config = ChatConfig()
        
        self.config = config
        self._client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """初始化OpenAI客户端"""
        try:
            if self.config.API_KEY:
                self._client = OpenAI(
                    api_key=self.config.API_KEY,
                    base_url=self.config.API_BASE_URL
                )
            else:
                print("⚠️  警告: 未找到API密钥，LLM功能将不可用")
        except Exception as e:
            print(f"⚠️  初始化LLM客户端失败: {e}")
            self._client = None
    
    @property
    def is_available(self) -> bool:
        """检查LLM是否可用"""
        return self._client is not None and self.config.API_KEY is not None
    
    def chat_completion(self, 
                       messages: List[Dict[str, str]], 
                       max_tokens: Optional[int] = None,
                       temperature: Optional[float] = None,
                       model: Optional[str] = None) -> Optional[str]:
        """
        基础的聊天完成接口
        
        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}]
            max_tokens: 最大token数
            temperature: 温度参数
            model: 模型名称
            
        Returns:
            生成的文本，如果失败返回None
        """
        if not self.is_available:
            return None
        extra_body = {
            "enable_thinking": False
        }
        
        try:
            response = self._client.chat.completions.create(
                model=model or self.config.CHAT_MODEL_NAME,
                messages=messages,
                max_tokens=max_tokens or self.config.MAX_TOKENS,
                temperature=temperature if temperature is not None else self.config.TEMPERATURE,
                top_p=self.config.TOP_P,
                extra_body=extra_body
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"⚠️  LLM调用失败: {e}")
            return None
    
    def chat_functional(self, 
                   user_message: str, 
                   system_prompt: Optional[str] = None,
                   temperature: Optional[float] = None,
                   tools: Optional[List[Dict]] = None,
                   tool_choice: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        简化的聊天接口，支持function calling并自动执行函数
        
        Args:
            user_message: 用户消息
            system_prompt: 系统提示词
            temperature: 温度参数
            tools: 工具定义列表，用于function calling
            tool_choice: 工具选择策略 ("none", "auto", "required" 或具体工具名)
            
        Returns:
            包含回复内容和函数执行结果的字典，格式：
            {
                "content": "回复内容",
                "function_results": [函数执行结果列表] 或 None,
                "finish_reason": "完成原因"
            }
            如果不使用tools，则直接返回字符串内容（保持向后兼容）
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": user_message})

        tools = self.get_db_query_tools() if tools is None else tools
        
        # 如果没有使用tools，保持原有行为
        if not tools:
            response = self.chat_completion(messages, temperature=temperature)
            return response
        
        # 使用function calling
        if not self.is_available:
            return None
        
        try:
            completion_kwargs = {
                "model": self.config.CHAT_MODEL_NAME,
                "messages": messages,
                "max_tokens": self.config.MAX_TOKENS,
                "temperature": temperature if temperature is not None else self.config.TEMPERATURE,
                "top_p": self.config.TOP_P,
                "tools": tools
            }
            
            if tool_choice:
                completion_kwargs["tool_choice"] = tool_choice
            
            response = self._client.chat.completions.create(**completion_kwargs)
            
            choice = response.choices[0]
            message = choice.message
            
            
            # 处理工具调用并执行函数
            if hasattr(message, 'tool_calls') and message.tool_calls:                
                try:
                    # 导入数据库查询管理器
                    from db_query_manager import DatabaseQueryManager
                    db_manager = DatabaseQueryManager()
                    
                    for tool_call in message.tool_calls:
                        function_name = tool_call.function.name
                        arguments = json.loads(tool_call.function.arguments)
                        
                        # 执行对应的函数
                        function_result = self._execute_db_function(db_manager, function_name, arguments)
                        
                        result = function_result
                        
                except Exception as e:
                    print(f"⚠️  函数执行失败: {e}")
            
            return result
            
        except Exception as e:
            print(f"⚠️  LLM Function Calling调用失败: {e}")
            return None
    
    def _execute_db_function(self, db_manager, function_name: str, arguments: Dict[str, Any]) -> Any:
        """
        执行数据库函数调用
        
        Args:
            db_manager: 数据库管理器实例
            function_name: 函数名
            arguments: 函数参数
            
        Returns:
            函数执行结果
        """
        print(f"🔍 执行函数: {function_name} with args: {arguments}")
        try:
            if function_name == "execute_query":
                sql = arguments.get("sql")
                params = arguments.get("params", [])
                return db_manager.execute_query(sql, params)
                
            elif function_name == "get_table_schema":
                table_name = arguments.get("table_name")
                return db_manager.get_table_schema(table_name)
                
            elif function_name == "list_tables":
                return db_manager.list_tables()
                
            elif function_name == "search_records":
                table_name = arguments.get("table_name")
                conditions = arguments.get("conditions", {})
                limit = arguments.get("limit", 10)
                return db_manager.search_records(table_name, conditions, limit)
                
            elif function_name == "insert_record":
                table_name = arguments.get("table_name")
                data = arguments.get("data")
                return db_manager.insert_record(table_name, data)
                
            elif function_name == "update_record":
                table_name = arguments.get("table_name")
                data = arguments.get("data")
                conditions = arguments.get("conditions")
                return db_manager.update_record(table_name, data, conditions)
                
            elif function_name == "delete_record":
                table_name = arguments.get("table_name")
                conditions = arguments.get("conditions")
                return db_manager.delete_record(table_name, conditions)
                
            elif function_name == "get_record_count":
                table_name = arguments.get("table_name")
                conditions = arguments.get("conditions", {})
                return db_manager.get_record_count(table_name, conditions)
                
            else:
                return {"error": f"未知函数: {function_name}"}
                
        except Exception as e:
            return {"error": f"函数执行错误: {str(e)}"}
    
    def extract_json(self, 
                    user_input: str, 
                    extraction_prompt: str,
                    fallback_value: Any = None) -> Any:
        """
        使用LLM提取JSON格式的信息
        
        Args:
            user_input: 用户输入
            extraction_prompt: 提取指令
            fallback_value: 失败时的默认值
            
        Returns:
            提取的JSON对象，失败时返回fallback_value
        """
        if not self.is_available:
            return fallback_value
        
        system_prompt = "你是一个专业的信息提取助手，只返回JSON格式的数据，不要任何其他说明文字。"
        
        response = self.simple_chat(
            user_message=extraction_prompt,
            system_prompt=system_prompt,
            temperature=0.1  # 使用较低温度确保一致性
        )
        
        if not response:
            return fallback_value
        
        # 尝试解析JSON
        try:
            # 查找JSON部分
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_text = response[start_idx:end_idx]
                return json.loads(json_text)
            else:
                return fallback_value
                
        except json.JSONDecodeError as e:
            print(f"⚠️  JSON解析失败: {e}, 原始响应: {response}")
            return fallback_value
    
    def analyze_intent(self, 
                      user_input: str, 
                      context: str = "",
                      possible_intents: List[str] = None) -> Optional[Dict[str, Any]]:
        """
        分析用户意图
        
        Args:
            user_input: 用户输入
            context: 上下文信息
            possible_intents: 可能的意图列表
            
        Returns:
            意图分析结果
        """
        if not self.is_available:
            return None
        
        prompt = f"""
请分析用户的意图和提取相关信息。

上下文：{context}
用户输入：{user_input}
"""
        
        if possible_intents:
            prompt += f"\n可能的意图类型：{', '.join(possible_intents)}"
        
        prompt += """
请以JSON格式返回分析结果，包含以下字段：
- intent: 主要意图
- confidence: 置信度(0-1)
- extracted_info: 提取的具体信息
- reasoning: 分析理由

示例：
{"intent": "provide_name", "confidence": 0.9, "extracted_info": {"name": "张三"}, "reasoning": "用户明确说出了自己的名字"}
"""
        
        return self.extract_json(user_input, prompt, {})
    
    def summarize_conversation(self, 
                             conversation_history: List[Dict[str, str]],
                             max_length: int = 200) -> Optional[str]:
        """
        总结对话历史
        
        Args:
            conversation_history: 对话历史
            max_length: 最大长度
            
        Returns:
            对话摘要
        """
        if not self.is_available or not conversation_history:
            return None
        
        # 构建对话文本
        conversation_text = "\n".join([
            f"{item.get('role', 'user')}: {item.get('content', '')}"
            for item in conversation_history[-10:]  # 只取最近10轮对话
        ])
        
        prompt = f"""
请用{max_length}字以内总结以下对话的主要内容：

{conversation_text}

要求：
1. 突出重点信息
2. 保持简洁明了
3. 中文回复
"""
        
        return self.simple_chat(prompt, temperature=0.3)

    @staticmethod
    def get_db_query_tools() -> List[Dict[str, Any]]:
        """
        获取数据库查询管理器的function calling工具定义
        
        Returns:
            工具定义列表，用于function calling
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "execute_query",
                    "description": "执行SQL查询语句，支持SELECT、INSERT、UPDATE、DELETE操作",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sql": {
                                "type": "string",
                                "description": "要执行的SQL语句"
                            },
                            "params": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "SQL参数列表，用于参数化查询",
                                "default": []
                            }
                        },
                        "required": ["sql"]
                    }
                }
            },
            {
                "type": "function", 
                "function": {
                    "name": "get_table_schema",
                    "description": "获取数据库表的结构信息",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "table_name": {
                                "type": "string",
                                "description": "表名"
                            }
                        },
                        "required": ["table_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_tables",
                    "description": "列出数据库中所有的表名",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_records",
                    "description": "根据条件搜索记录",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "table_name": {
                                "type": "string",
                                "description": "表名"
                            },
                            "conditions": {
                                "type": "object",
                                "description": "搜索条件，键值对格式",
                                "additionalProperties": {"type": "string"}
                            },
                            "limit": {
                                "type": "integer",
                                "description": "返回结果的最大数量",
                                "default": 10
                            }
                        },
                        "required": ["table_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "insert_record",
                    "description": "向表中插入新记录",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "table_name": {
                                "type": "string",
                                "description": "表名"
                            },
                            "data": {
                                "type": "object",
                                "description": "要插入的数据，键值对格式",
                                "additionalProperties": {"type": "string"}
                            }
                        },
                        "required": ["table_name", "data"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "update_record",
                    "description": "更新表中的记录",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "table_name": {
                                "type": "string",
                                "description": "表名"
                            },
                            "data": {
                                "type": "object",
                                "description": "要更新的数据，键值对格式",
                                "additionalProperties": {"type": "string"}
                            },
                            "conditions": {
                                "type": "object",
                                "description": "更新条件，键值对格式",
                                "additionalProperties": {"type": "string"}
                            }
                        },
                        "required": ["table_name", "data", "conditions"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "delete_record",
                    "description": "删除表中的记录",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "table_name": {
                                "type": "string",
                                "description": "表名"
                            },
                            "conditions": {
                                "type": "object",
                                "description": "删除条件，键值对格式",
                                "additionalProperties": {"type": "string"}
                            }
                        },
                        "required": ["table_name", "conditions"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_record_count",
                    "description": "获取表中记录的数量",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "table_name": {
                                "type": "string",
                                "description": "表名"
                            },
                            "conditions": {
                                "type": "object",
                                "description": "统计条件，键值对格式（可选）",
                                "additionalProperties": {"type": "string"}
                            }
                        },
                        "required": ["table_name"]
                    }
                }
            }
        ]
    
# 全局LLM客户端实例
_global_llm_client = None


def get_llm_client(config=None) -> LLMClient:
    """
    获取全局LLM客户端实例
    
    Args:
        config: 配置对象，首次调用时使用
        
    Returns:
        LLM客户端实例
    """
    global _global_llm_client
    
    if _global_llm_client is None:
        _global_llm_client = LLMClient(config)
    
    return _global_llm_client


def reset_llm_client():
    """重置全局LLM客户端（用于测试或配置更新）"""
    global _global_llm_client
    _global_llm_client = None
