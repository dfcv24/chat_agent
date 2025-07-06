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
        
        try:
            response = self._client.chat.completions.create(
                model=model or self.config.CHAT_MODEL_NAME,
                messages=messages,
                max_tokens=max_tokens or self.config.MAX_TOKENS,
                temperature=temperature if temperature is not None else self.config.TEMPERATURE,
                top_p=self.config.TOP_P
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"⚠️  LLM调用失败: {e}")
            return None
    
    def simple_chat(self, 
                   user_message: str, 
                   system_prompt: Optional[str] = None,
                   temperature: Optional[float] = None) -> Optional[str]:
        """
        简化的聊天接口
        
        Args:
            user_message: 用户消息
            system_prompt: 系统提示词
            temperature: 温度参数
            
        Returns:
            生成的回复
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": user_message})
        
        return self.chat_completion(messages, temperature=temperature)
    
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
