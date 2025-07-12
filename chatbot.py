import json
import os
from datetime import datetime
from typing import List, Dict
from config import ChatConfig
from llm_client import get_llm_client
from prompts.system_prompt import CHAT_PROMPT

class ChatBot:
    def __init__(self):
        self.config = ChatConfig()
        self.chat_history = []
        self.chat_prompt = CHAT_PROMPT
        self.load_chat_history()
        
        # 初始化LLM客户端
        self.llm_client = get_llm_client(self.config)
        
        # 聊天运行状态
        self.running = False
    
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
        """构建发送给API的消息列表"""
        messages = [{"role": "system", "content": self.chat_prompt}]
        
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
            if not self.llm_client.is_available:
                return "❌ 抱歉，AI服务暂时不可用，请检查配置。"
            
            messages = self.get_chat_messages(user_input)
            
            response = self.llm_client.chat_completion(messages)
            
            if response:
                return response
            else:
                return "❌ 抱歉，我暂时无法回复。"
            
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
    
    def simple_chat(self):
        """简单的同步聊天模式"""
        print(f"\n{self.config.WELCOME_MESSAGE}")
        print("� 提示：直接输入你的问题或想说的话，输入 '退出' 结束聊天")
        
        self.running = True
        
        try:
            while self.running:
                try:
                    # 获取用户输入
                    user_input = input(f"\n😊 你: ").strip()
                    
                    if not user_input:
                        continue
                    
                    # 处理用户消息
                    self.process_message(user_input)
                        
                except KeyboardInterrupt:
                    print(f"\n\n嘿嘿～那我就不打扰你啦，记得想我哦～👋 {self.config.BOT_NAME}先走啦～")
                    break
                except Exception as e:
                    print(f"\n❌ 处理消息时发生错误: {e}")
                    
        except Exception as e:
            print(f"\n❌ 程序发生错误: {e}")
        finally:
            self.running = False
            print("\n👋 聊天结束")
    
    def process_message(self, user_input: str):
        """处理用户消息"""
        # 检查特殊命令
        if user_input.lower() in self.config.EXIT_COMMANDS:
            print(f"\n嘿嘿～那我就不打扰你啦，记得想我哦～👋 {self.config.BOT_NAME}先走啦～")
            self.running = False
            return
        
        if user_input.lower() in self.config.CLEAR_COMMANDS:
            self.clear_history()
            return
        
        if user_input.lower() in self.config.HELP_COMMANDS:
            self.show_help()
            return
        
        # 获取AI回复
        print(f"\n🤖 {self.config.BOT_NAME}: ", end="", flush=True)
        response = self.get_response(user_input)
        print(response)
        
        # 保存到历史记录
        self.add_to_history(user_input, response)
        self.save_chat_history()
    
    def start_chat(self):
        """启动聊天（提供一个更清晰的入口方法）"""
        try:
            self.simple_chat()
        except Exception as e:
            print(f"\n❌ 程序发生错误: {e}")
            self.running = False

if __name__ == "__main__":
    bot = ChatBot()
    bot.start_chat()
