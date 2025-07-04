import json
import os
from datetime import datetime
from typing import List, Dict
from openai import OpenAI
from config import ChatConfig
from prompt_toolkit import prompt

class ChatBot:
    def __init__(self):
        self.config = ChatConfig()
        self.chat_history = []
        self.system_prompt = self.load_system_prompt()
        self.setup_api()
        self.load_chat_history()
        self.client = OpenAI()
        
    def setup_api(self):
        """设置API客户端"""
        if not self.config.API_KEY:
            print("⚠️  警告: 未找到API密钥，请设置环境变量 OPENAI_API_KEY")
            print("或者使用其他AI服务，请修改此方法中的API设置")
            return
    
    def load_system_prompt(self) -> str:
        """加载系统提示词"""
        try:
            with open(self.config.PROMPT_FILE, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except FileNotFoundError:
            print(f"⚠️  警告: 未找到提示词文件 {self.config.PROMPT_FILE}")
            return "你是一个有用的AI助手。"
    
    def load_chat_history(self):
        self.chat_history = []
        return 
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
            if not self.config.API_KEY:
                return "❌ 抱歉，API密钥未配置，无法获取回复。请检查配置。"
            
            messages = self.get_chat_messages(user_input)
            
            response = self.client.chat.completions.create(
                model=self.config.MODEL_NAME,
                messages=messages,
                max_tokens=self.config.MAX_TOKENS,
                temperature=self.config.TEMPERATURE,
                top_p=self.config.TOP_P
            )
            
            return response.choices[0].message.content.strip()
            
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
        
        try:
            while True:
                user_input = prompt(f"\n😊 你: ").strip()
                
                if not user_input:
                    continue
                
                # 检查特殊命令
                if user_input.lower() in self.config.EXIT_COMMANDS:
                    print(f"\n嘿嘿～那我就不打扰你啦，记得想我哦～👋 {self.config.BOT_NAME}先走啦～")
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
            print(f"\n\n嘿嘿～那我就不打扰你啦，记得想我哦～👋 {self.config.BOT_NAME}先走啦～")
        except Exception as e:
            print(f"\n❌ 程序发生错误: {e}")

if __name__ == "__main__":
    bot = ChatBot()
    bot.chat_loop()
