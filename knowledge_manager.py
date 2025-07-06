import json
import os
import re
from typing import Dict, Optional, Any
from datetime import datetime

class KnowledgeManager:
    """用户知识管理器"""
    
    def __init__(self, knowledge_file: str = "data/user_knowledge.json", 
                 template_file: str = "data/user_knowledge_template.json"):
        self.knowledge_file = knowledge_file
        self.template_file = template_file
        self.user_knowledge = {}
        self.pending_questions = []
        self.load_knowledge()
    
    def load_knowledge(self):
        """加载用户知识"""
        try:
            if os.path.exists(self.knowledge_file):
                with open(self.knowledge_file, 'r', encoding='utf-8') as f:
                    self.user_knowledge = json.load(f)
            else:
                # 如果用户知识文件不存在，从模板创建
                self.create_from_template()
        except Exception as e:
            print(f"⚠️  加载用户知识失败: {e}")
            self.create_from_template()
    
    def create_from_template(self):
        """从模板创建用户知识文件"""
        try:
            with open(self.template_file, 'r', encoding='utf-8') as f:
                template = json.load(f)
            
            # 复制模板到用户知识
            self.user_knowledge = template.copy()
            self.save_knowledge()
            print("✅ 已从模板创建用户知识文件")
        except Exception as e:
            print(f"❌ 创建用户知识文件失败: {e}")
            self.user_knowledge = {}
    
    def save_knowledge(self):
        """保存用户知识"""
        try:
            os.makedirs(os.path.dirname(self.knowledge_file), exist_ok=True)
            with open(self.knowledge_file, 'w', encoding='utf-8') as f:
                json.dump(self.user_knowledge, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️  保存用户知识失败: {e}")
    
    def get_next_question(self) -> Optional[str]:
        """获取下一个需要询问的问题"""
        for category_name, category in self.user_knowledge.items():
            for item_key, item_data in category.items():
                if isinstance(item_data, dict) and item_data.get("knowledge") is None:
                    return item_data.get("question", f"请告诉我关于{item_data.get('item', item_key)}的信息")
        return None
    
    def extract_info_from_response(self, user_response: str, question_context: str = "") -> Dict[str, Any]:
        """使用大模型从用户回复中提取信息"""
        try:
            # 使用LLM客户端
            from llm_client import get_llm_client
            llm = get_llm_client()
            
            # 如果LLM不可用，fallback到规则匹配
            if not llm.is_available:
                return self._extract_info_fallback(user_response, question_context)
            
            # 构建提取信息的提示词
            extraction_prompt = f"""
作为一个信息提取助手，请从用户的回复中提取相关信息。

问题上下文：{question_context}
用户回复：{user_response}

请根据问题上下文和用户回复，提取相关信息。如果用户明确拒绝回答（如说"不想说"、"不告诉你"等），则不提取任何信息。

支持的信息类型和格式：
- name: 用户姓名（字符串）
- age: 年龄（整数，5-120范围）
- gender: 性别（"男"或"女"）
- location: 所在城市/地区（字符串）
- height: 身高（如"175cm"）
- weight: 体重（如"65kg"）
- occupation: 职业（字符串）
- education: 学历（字符串）
- hobbies: 爱好（字符串）
- favorite_food: 喜欢的食物（字符串）
- favorite_movie: 喜欢的电影（字符串）
- mbti: MBTI人格类型（字符串）
- zodiac: 星座（字符串）

请以JSON格式返回提取的信息，只包含能确定提取到的字段。如果没有提取到任何信息，返回空的JSON对象。

示例：
用户回复："我叫张三，今年25岁"
返回：{{"name": "张三", "age": 25}}

用户回复："不想说"
返回：{{}}

请返回JSON格式：
"""
            
            # 使用LLM提取JSON信息
            extracted = llm.extract_json(
                user_input=user_response,
                extraction_prompt=extraction_prompt,
                fallback_value={}
            )
            
            # 如果LLM提取失败，使用规则匹配作为备选
            if not extracted:
                extracted = self._extract_info_fallback(user_response, question_context)
            
            # 验证和清理提取的数据
            return self._validate_extracted_info(extracted)
            
        except Exception as e:
            print(f"⚠️  大模型信息提取失败: {e}，使用规则匹配")
            return self._extract_info_fallback(user_response, question_context)
    
    def _extract_info_fallback(self, user_response: str, question_context: str = "") -> Dict[str, Any]:
        """备用的规则匹配信息提取方法"""
        extracted = {}
        user_response_lower = user_response.lower()
        
        # 检查是否拒绝回答
        if any(word in user_response_lower for word in ["不", "没", "不想", "不说", "不知道", "不清楚"]):
            return {}
        
        # 姓名提取
        if any(keyword in question_context for keyword in ["姓名", "名字", "称呼"]):
            name_patterns = [
                r"我叫([^\s，。！？,!?]+)",
                r"我是([^\s，。！？,!?]+)",
                r"叫我([^\s，。！？,!?]+)",
                r"名字[是叫]([^\s，。！？,!?]+)",
                r"^([^\s，。！？,!?]+)$"
            ]
            for pattern in name_patterns:
                match = re.search(pattern, user_response)
                if match:
                    extracted["name"] = match.group(1).strip()
                    break
        
        # 年龄提取
        elif any(keyword in question_context for keyword in ["年龄", "多大", "几岁"]):
            age_patterns = [r"(\d{1,2})[岁年]", r"我(\d{1,2})", r"今年(\d{1,2})", r"^(\d{1,2})$"]
            for pattern in age_patterns:
                match = re.search(pattern, user_response)
                if match:
                    age = int(match.group(1))
                    if 5 <= age <= 120:
                        extracted["age"] = age
                        break
        
        # 性别提取
        elif any(keyword in question_context for keyword in ["性别", "男生", "女生"]):
            if any(word in user_response_lower for word in ["男", "boy", "man", "先生", "帅哥"]):
                extracted["gender"] = "男"
            elif any(word in user_response_lower for word in ["女", "girl", "woman", "小姐", "美女"]):
                extracted["gender"] = "女"
        
        # 其他简单文本提取
        else:
            if len(user_response.strip()) > 0:
                if "职业" in question_context or "工作" in question_context:
                    extracted["occupation"] = user_response.strip()
                elif "爱好" in question_context:
                    extracted["hobbies"] = user_response.strip()
                elif "食物" in question_context:
                    extracted["favorite_food"] = user_response.strip()
        
        return extracted
    
    def _validate_extracted_info(self, extracted: Dict[str, Any]) -> Dict[str, Any]:
        """验证和清理提取的信息"""
        validated = {}
        
        for key, value in extracted.items():
            if key == "age" and isinstance(value, (int, float)):
                age = int(value)
                if 5 <= age <= 120:
                    validated[key] = age
            elif key == "height" and isinstance(value, str):
                # 确保身高格式正确
                height_match = re.search(r'(\d{2,3})', str(value))
                if height_match:
                    height = int(height_match.group(1))
                    if 100 <= height <= 250:
                        validated[key] = f"{height}cm"
            elif key == "weight" and isinstance(value, str):
                # 确保体重格式正确
                weight_match = re.search(r'(\d{2,3})', str(value))
                if weight_match:
                    weight = int(weight_match.group(1))
                    if 30 <= weight <= 300:
                        validated[key] = f"{weight}kg"
            elif key == "gender" and isinstance(value, str):
                if value.lower() in ["男", "male", "man", "boy"]:
                    validated[key] = "男"
                elif value.lower() in ["女", "female", "woman", "girl"]:
                    validated[key] = "女"
            elif isinstance(value, str) and len(value.strip()) > 0:
                # 其他字符串字段
                validated[key] = value.strip()
        
        return validated
    
    def update_knowledge(self, extracted_info: Dict[str, Any]) -> bool:
        """更新用户知识"""
        updated = False
        
        # 映射提取的信息到知识结构中
        field_mapping = {
            "name": ("basic_info", "name"),
            "age": ("basic_info", "age"),
            "gender": ("basic_info", "gender"),
            "location": ("basic_info", "location"),
            "height": ("physical_info", "height"),
            "weight": ("physical_info", "weight"),
            "hobbies": ("interests", "hobbies"),
            "favorite_food": ("interests", "favorite_food"),
            "favorite_movie": ("interests", "favorite_movie"),
            "occupation": ("work_study", "occupation"),
            "education": ("work_study", "education"),
            "mbti": ("personality", "mbti"),
            "zodiac": ("personality", "zodiac")
        }
        
        for field, value in extracted_info.items():
            if field in field_mapping:
                category, item_key = field_mapping[field]
                if (category in self.user_knowledge and 
                    item_key in self.user_knowledge[category] and
                    self.user_knowledge[category][item_key].get("knowledge") is None):
                    
                    self.user_knowledge[category][item_key]["knowledge"] = value
                    self.user_knowledge[category][item_key]["updated_at"] = datetime.now().isoformat()
                    updated = True
        
        if updated:
            self.save_knowledge()
        
        return updated
    
    def get_known_info_summary(self) -> str:
        """获取已知信息摘要"""
        known_info = []
        for category_name, category in self.user_knowledge.items():
            for item_key, item_data in category.items():
                if isinstance(item_data, dict) and item_data.get("knowledge") is not None:
                    item_name = item_data.get("item", item_key)
                    knowledge = item_data.get("knowledge")
                    known_info.append(f"{item_name}: {knowledge}")
        
        return "\n".join(known_info) if known_info else "暂无已知信息"
    
    def should_ask_question(self) -> bool:
        """判断是否应该主动询问问题"""
        # 统计未知信息数量
        unknown_count = 0
        total_count = 0
        
        for category_name, category in self.user_knowledge.items():
            for item_key, item_data in category.items():
                if isinstance(item_data, dict):
                    total_count += 1
                    if item_data.get("knowledge") is None:
                        unknown_count += 1
        
        # 如果未知信息比例较高，且用户回复较短，可以主动询问
        return unknown_count > 0 and unknown_count / max(total_count, 1) > 0.3
    
    def get_user_context_for_prompt(self) -> str:
        """获取用户信息用于添加到系统提示词中"""
        known_info = []
        for category_name, category in self.user_knowledge.items():
            category_info = []
            for item_key, item_data in category.items():
                if isinstance(item_data, dict) and item_data.get("knowledge") is not None:
                    item_name = item_data.get("item", item_key)
                    knowledge = item_data.get("knowledge")
                    category_info.append(f"{item_name}: {knowledge}")
            
            if category_info:
                known_info.append(f"【{category_name}】\n" + "\n".join(category_info))
        
        if known_info:
            return f"\n\n=== 用户信息 ===\n" + "\n\n".join(known_info) + "\n===============\n\n根据以上用户信息，请更个性化地回复用户。"
        else:
            return ""
