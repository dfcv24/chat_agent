import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from abc import ABC, abstractmethod
import requests

class AIProvider(ABC):
    """AI服务提供商抽象基类"""
    
    @abstractmethod
    def get_response(self, messages: List[Dict], **kwargs) -> str:
        pass

class OpenAIProvider(AIProvider):
    """OpenAI API提供商"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", model: str = "gpt-3.5-turbo"):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
    
    def get_response(self, messages: List[Dict], max_tokens: int = 2000, temperature: float = 0.7) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return f"❌ 请求失败: {str(e)}"

class MockProvider(AIProvider):
    """模拟AI提供商（用于测试）"""
    
    def get_response(self, messages: List[Dict], **kwargs) -> str:
        user_message = messages[-1]["content"] if messages else ""
        
        # 简单的回复逻辑
        if "你好" in user_message or "hello" in user_message.lower():
            return "你好！很高兴见到你！有什么可以帮助你的吗？😊"
        elif "再见" in user_message or "bye" in user_message.lower():
            return "再见！希望我们的对话对你有帮助！👋"
        elif "谢谢" in user_message or "thank" in user_message.lower():
            return "不客气！我很乐意帮助你！如果还有其他问题，请随时告诉我。😄"
        elif "?" in user_message or "？" in user_message:
            return "这是个很好的问题！虽然我是模拟AI，但我会尽力提供有用的信息。你可以尝试配置真实的AI服务来获得更好的回复。🤔"
        else:
            return f"我听到你说：'{user_message}'。由于我是模拟AI，我的回复可能比较简单。请配置真实的AI服务以获得更智能的对话体验！💡"

class ChatBot:
    def __init__(self):
        from config import ChatConfig
        self.config = ChatConfig()
        self.chat_history = []
        self.system_prompt = self.load_system_prompt()
        self.ai_provider = self.setup_ai_provider()
        self.load_chat_history()
        
    def setup_ai_provider(self) -> AIProvider:
        """设置AI提供商"""
        # 尝试使用OpenAI
        if self.config.API_KEY:
            print("🔗 使用OpenAI API服务")
            return OpenAIProvider(
                api_key=self.config.API_KEY,
                base_url=self.config.API_BASE_URL,
                model=self.config.MODEL_NAME
            )
        else:
            print("⚠️  未配置API密钥，使用模拟AI服务")
            print("💡 要使用真实AI服务，请：")
            print("   1. 复制 .env.example 为 .env")
            print("   2. 在 .env 文件中填入你的API密钥")
            print("   3. 重新启动程序")
            return MockProvider()
    
    def load_system_prompt(self) -> str:
        """加载系统提示词"""
        try:
            with open(self.config.PROMPT_FILE, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except FileNotFoundError:
            print(f"⚠️  警告: 未找到提示词文件 {self.config.PROMPT_FILE}")
            return "你是一个有用的AI助手。"
    
    def load_chat_history(self):
        """加载聊天历史"""
        try:
            if os.path.exists(self.config.CHAT_HISTORY_FILE):
                with open(self.config.CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    self.chat_history = json.load(f)
        except Exception as e:
            print(f"⚠️  加载聊天历史失败: {e}")
            self.chat_history = []
    
    def save_chat_history(self):
        """保存聊天历史"""
        try:
            os.makedirs(os.path.dirname(self.config.CHAT_HISTORY_FILE), exist_ok=True)
            with open(self.config.CHAT_HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.chat_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️  保存聊天历史失败: {e}")
    
    def add_to_history(self, user_message: str, bot_response: str):
        """添加对话到历史记录"""
        self.chat_history.append({
            "timestamp": datetime.now().isoformat(),
            "user": user_message,
            "bot": bot_response
        })
        
        # 限制历史记录长度
        if len(self.chat_history) > self.config.MAX_HISTORY_LENGTH:
            self.chat_history = self.chat_history[-self.config.MAX_HISTORY_LENGTH:]
    
    def get_chat_messages(self, user_input: str) -> List[Dict]:
        """构建发送给AI的消息列表"""
        messages = [{"role": "system", "content": self.system_prompt}]
        
        # 添加历史对话（最近几轮）
        recent_history = self.chat_history[-5:]  # 只取最近5轮对话
        for item in recent_history:
            messages.append({"role": "user", "content": item["user"]})
            messages.append({"role": "assistant", "content": item["bot"]})
        
        # 添加当前用户输入
        messages.append({"role": "user", "content": user_input})
        
        return messages
    
    def get_response(self, user_input: str) -> str:
        """获取机器人回复"""
        try:
            messages = self.get_chat_messages(user_input)
            return self.ai_provider.get_response(
                messages=messages,
                max_tokens=self.config.MAX_TOKENS,
                temperature=self.config.TEMPERATURE
            )
        except Exception as e:
            return f"❌ 抱歉，我遇到了一些问题: {str(e)}"
    
    def clear_history(self):
        """清除聊天历史"""
        self.chat_history = []
        if os.path.exists(self.config.CHAT_HISTORY_FILE):
            os.remove(self.config.CHAT_HISTORY_FILE)
        print("✅ 聊天历史已清除")
    
    def show_help(self):
        """显示帮助信息"""
        help_text = f"""
🤖 {self.config.BOT_NAME} 帮助信息

📝 基本使用:
   直接输入你的问题或想说的话

🔧 特殊命令:
   退出/再见/bye/exit/quit - 退出程序
   清除历史/清空/clear - 清除聊天历史
   帮助/help/命令 - 显示此帮助信息

💡 提示:
   - 我会记住最近的对话内容
   - 你可以随时询问任何问题
   - 输入要清楚明确，我会尽力帮助你

版本: {self.config.VERSION}
        """
        print(help_text)
    
    def chat_loop(self):
        """主聊天循环"""
        print(f"\n{self.config.WELCOME_MESSAGE}")
        print("💡 输入 '帮助' 查看可用命令\n")
        
        try:
            while True:
                user_input = input(f"\n😊 你: ").strip()
                
                if not user_input:
                    continue
                
                # 检查特殊命令
                if user_input.lower() in self.config.EXIT_COMMANDS:
                    print(f"\n👋 {self.config.BOT_NAME}: 再见！很高兴与你聊天！")
                    break
                
                if user_input.lower() in self.config.CLEAR_COMMANDS:
                    self.clear_history()
                    continue
                
                if user_input.lower() in self.config.HELP_COMMANDS:
                    self.show_help()
                    continue
                
                # 获取回复
                print(f"\n🤖 {self.config.BOT_NAME}: ", end="", flush=True)
                response = self.get_response(user_input)
                print(response)
                
                # 保存到历史记录
                self.add_to_history(user_input, response)
                self.save_chat_history()
                
        except KeyboardInterrupt:
            print(f"\n\n👋 {self.config.BOT_NAME}: 再见！很高兴与你聊天！")
        except Exception as e:
            print(f"\n❌ 程序发生错误: {e}")

if __name__ == "__main__":
    bot = ChatBot()
    bot.chat_loop()
