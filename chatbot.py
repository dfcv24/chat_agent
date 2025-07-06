import json
import os
import random
import threading
import time
import queue
from datetime import datetime
from typing import List, Dict
from openai import OpenAI
from config import ChatConfig
from knowledge_manager import KnowledgeManager
from llm_client import get_llm_client
from prompt_toolkit import prompt
from prompt_toolkit.patch_stdout import patch_stdout
from prompts.system_prompt import CHAT_PROMPT, THINK_PROMPT

class ChatBot:
    def __init__(self):
        self.config = ChatConfig()
        self.chat_history = []
        self.chat_prompt = CHAT_PROMPT
        self.think_prompt = THINK_PROMPT
        self.load_chat_history()
        
        # 初始化LLM客户端
        self.llm_client = get_llm_client(self.config)
        
        # 初始化知识管理器
        self.knowledge_manager = KnowledgeManager(
            self.config.USER_KNOWLEDGE_FILE,
            self.config.KNOWLEDGE_TEMPLATE_FILE
        )
        self.last_question_context = ""  # 记录最后询问的问题上下文
        
        # 异步交互相关
        self.input_queue = queue.Queue()  # 用户输入队列
        self.running = False  # 控制聊天循环运行状态
        self.last_user_activity = time.time()  # 记录用户最后活动时间
        self.question_timer = None  # 主动提问定时器
        
        # 思考功能相关
        self.think_timer = None  # 思考定时器
        self.think_interval = 30  # 思考间隔（秒）
    
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
        # 获取用户信息用于个性化回复
        user_context = self.knowledge_manager.get_user_context_for_prompt()
        chat_prompt_with_context = self.chat_prompt + user_context
        
        messages = [{"role": "system", "content": chat_prompt_with_context}]
        
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
    
    def think(self):
        """AI进行思考并输出思考结果"""
        if not self.running or not self.llm_client.is_available:
            return
        
        try:
            # 构建思考的prompt
            think_content = self.build_think_content()
            
            messages = [
                {"role": "system", "content": self.think_prompt},
                {"role": "user", "content": think_content}
            ]
            
            # 获取思考结果
            thinking_response = self.llm_client.chat_completion(messages)
            
            if thinking_response:
                print(f"\n💭 {self.config.BOT_NAME}（正在思考）: {thinking_response}")
            
        except Exception as e:
            print(f"💭 思考过程中发生错误: {e}")
    
    def build_think_content(self) -> str:
        """构建思考的提示词"""
        # 获取最近的聊天历史
        recent_history = self.chat_history[-3:] if self.chat_history else []
        
        # 获取用户信息
        user_context = self.knowledge_manager.get_user_context_for_prompt()
        
        think_content = "请利用以下信息进行思考：\n\n"
        
        if user_context:
            think_content += f"用户信息：\n{user_context}\n\n"
        
        if recent_history:
            think_content += "最近的对话：\n"
            for item in recent_history:
                think_content += f"用户: {item['user']}\n"
                think_content += f"我: {item['bot']}\n\n"
        else:
            think_content += "还没有聊天记录。\n\n"
        
        return think_content
    
    def schedule_thinking(self):
        """安排定期思考"""
        if not self.running:
            return
        
        # 执行思考
        self.think()
        
        # 安排下次思考
        if self.running:
            self.think_timer = threading.Timer(
                self.think_interval, 
                self.schedule_thinking
            )
            self.think_timer.start()

    def should_ask_question_now(self, time_since_last_activity: float = None) -> bool:
        """判断是否应该主动提问"""
        if not self.config.AUTO_ASK_QUESTIONS:
            return False
        
        # 检查是否还有未知信息需要询问
        if not self.knowledge_manager.should_ask_question():
            return False
        
        # 如果指定了时间间隔，检查是否达到主动提问的时间阈值
        if time_since_last_activity is not None:
            # 用户空闲指定时间后主动提问
            return (self.config.PROACTIVE_QUESTION_DELAY <= 
                   time_since_last_activity <= 
                   self.config.MAX_IDLE_TIME)
        
        # 随机决定是否询问（避免过于频繁）
        return random.random() <= self.config.QUESTION_PROBABILITY
    
    def get_next_question(self) -> str:
        """获取下一个要询问的问题"""
        question = self.knowledge_manager.get_next_question()
        if question:
            self.last_question_context = question
            return question
        return ""
    
    def input_listener(self):
        """用户输入监听线程"""
        with patch_stdout():
            while self.running:
                try:
                    user_input = prompt(f"\n😊 你: ").strip()
                    if user_input:
                        self.input_queue.put(user_input)
                        self.last_user_activity = time.time()
                        # 取消当前的主动提问定时器
                        if self.question_timer:
                            self.question_timer.cancel()
                except (KeyboardInterrupt, EOFError):
                    self.input_queue.put("__EXIT__")
                    break
                except Exception as e:
                    print(f"输入监听错误: {e}")
    
    def schedule_proactive_question(self):
        """安排主动提问"""
        if not self.running:
            return
        
        # 检查用户空闲时间
        time_since_activity = time.time() - self.last_user_activity
        
        if self.should_ask_question_now(time_since_activity):
            # 主动提问
            question = self.get_next_question()
            if question:
                print(f"\n🤔 {self.config.BOT_NAME}（主动提问）: {question}")
                self.last_question_context = question
                
                # 不需要立即获取AI回复，等待用户回应
                return
        
        # 如果没有提问，继续安排下次检查
        if self.running:
            # 定期检查是否需要主动提问
            self.question_timer = threading.Timer(
                self.config.QUESTION_CHECK_INTERVAL, 
                self.schedule_proactive_question
            )
            self.question_timer.start()
    
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
        
        # 处理知识提取
        if self.config.ENABLE_KNOWLEDGE_LEARNING and self.last_question_context:
            extracted_info = self.knowledge_manager.extract_info_from_response(
                user_input, self.last_question_context
            )
            
            if extracted_info:
                updated = self.knowledge_manager.update_knowledge(extracted_info)
                if updated:
                    print(f"✨ 我记住了关于你的新信息～")
        
        # 重置问题上下文
        self.last_question_context = ""
        
        # 重新安排主动提问定时器
        if self.question_timer:
            self.question_timer.cancel()
        
        if self.running:
            self.question_timer = threading.Timer(
                self.config.QUESTION_CHECK_INTERVAL, 
                self.schedule_proactive_question
            )
            self.question_timer.start()
    
    def chat_loop(self):
        """异步聊天循环"""
        print(f"\n{self.config.WELCOME_MESSAGE}")
        print("💡 提示：你可以随时输入消息，我也会在合适的时候主动询问你一些问题哦～")
        print("💭 我还会每30秒进行一次思考，与你分享我的想法～")
        
        self.running = True
        self.last_user_activity = time.time()
        
        # 启动用户输入监听线程
        input_thread = threading.Thread(target=self.input_listener, daemon=True)
        input_thread.start()
        
        # 启动主动提问定时器
        self.question_timer = threading.Timer(
            self.config.QUESTION_CHECK_INTERVAL, 
            self.schedule_proactive_question
        )
        self.question_timer.start()
        
        # 启动思考定时器
        self.think_timer = threading.Timer(
            self.think_interval,
            self.schedule_thinking
        )
        self.think_timer.start()
        
        try:
            while self.running:
                try:
                    # 检查用户输入队列
                    user_input = self.input_queue.get(timeout=1.0)
                    
                    if user_input == "__EXIT__":
                        break
                    
                    if user_input:
                        self.process_message(user_input)
                        
                except queue.Empty:
                    # 队列为空，继续循环
                    continue
                except Exception as e:
                    print(f"\n❌ 处理消息时发生错误: {e}")
                    
        except KeyboardInterrupt:
            print(f"\n\n嘿嘿～那我就不打扰你啦，记得想我哦～👋 {self.config.BOT_NAME}先走啦～")
        finally:
            self.running = False
            if self.question_timer:
                self.question_timer.cancel()
            if self.think_timer:
                self.think_timer.cancel()
            print("\n👋 聊天结束")
    
    def start_chat(self):
        """启动聊天（提供一个更清晰的入口方法）"""
        try:
            self.chat_loop()
        except Exception as e:
            print(f"\n❌ 程序发生错误: {e}")
            self.running = False

if __name__ == "__main__":
    bot = ChatBot()
    bot.start_chat()
