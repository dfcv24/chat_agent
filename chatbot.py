import json
import os
import threading
import time
from datetime import datetime, timedelta
from typing import List, Dict
from config import ChatConfig
from llm_client import get_llm_client
from prompts.system_prompt import CHAT_PROMPT
from vector_db_manager import VectorDBManager

class ChatBot:
    def __init__(self):
        self.config = ChatConfig()
        self.chat_history = []
        self.chat_prompt = CHAT_PROMPT
        self.load_chat_history()
        
        # 初始化LLM客户端
        self.llm_client = get_llm_client(self.config)
        
        # 初始化向量数据库管理器
        self.vector_db = VectorDBManager(self.config)
        
        # 聊天运行状态
        self.running = False
        
        # 归档相关
        self.archive_thread = None
        self.archive_running = False
        
        # 启动自动归档任务
        if getattr(self.config, 'AUTO_ARCHIVE_ENABLED', True):
            self.start_archive_task()
    
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
    
    def add_to_history(self, role: str, message: str):
        """添加对话到历史记录"""
        self.chat_history.append({
            "timestamp": datetime.now().isoformat(),
            role: message,
        })
        
        # 限制历史记录长度
        if len(self.chat_history) > self.config.MAX_HISTORY_LENGTH:
            self.chat_history = self.chat_history[-self.config.MAX_HISTORY_LENGTH:]
    
    def get_chat_messages(self, user_input: str) -> List[Dict]:
        """构建发送给API的消息列表"""
        messages = [{"role": "system", "content": self.chat_prompt}]
        
        # 搜索相关的历史聊天记录（如果启用）
        related_history = []
        if getattr(self.config, 'ENABLE_HISTORY_SEARCH', True):
            try:
                if self.vector_db and self.vector_db.is_available:
                    search_limit = getattr(self.config, 'HISTORY_SEARCH_LIMIT', 3)
                    related_history = self.vector_db.search_related_chat_history(user_input, limit=search_limit)
            except Exception as e:
                print(f"⚠️  搜索历史记录失败: {e}")
        
        # 如果找到相关的历史记录，添加到上下文中
        if related_history:
            context_content = "📚 参考相关的历史对话:\n"
            for i, record in enumerate(related_history, 1):
                topic = record.get('topic', '未知主题')
                summary = record.get('summary', '')
                content_short = record.get('raw_content', '')[:400] + "..." if len(record.get('raw_content', '')) > 400 else record.get('raw_content', '')
                similarity = record.get('score', 0)
                
                context_content += f"\n{i}. 主题: {topic} (相似度: {similarity:.2f}):\n"
                context_content += f"   总结: {summary}\n"
                context_content += f"   内容: {content_short}\n"
            
            context_content += "\n💡 请结合这些历史对话的上下文来理解用户的意图，并提供更准确和连贯的回答。\n"
            
            # 添加历史上下文作为系统消息
            print("搜索到的相关历史上下文", context_content)
            messages.append({"role": "system", "content": context_content})
        
        # 添加当前会话的历史对话（最近几轮）- 修正为单一消息格式
        recent_history = self.chat_history[-10:]  # 取最近10条消息
        for item in recent_history:
            # 检查消息是否包含 user 或 assistant 字段
            if "user" in item:
                messages.append({"role": "user", "content": item["user"]})
            elif "assistant" in item:
                content = item.get("assistant", item.get("assistant", ""))
                messages.append({"role": "assistant", "content": content})
        
        # 添加当前用户输入
        messages.append({"role": "user", "content": user_input})
        
        return messages
    
    def get_response(self, user_input: str) -> str:
        """获取机器人回复"""
        try:
            if not self.llm_client.is_available:
                return "❌ 抱歉，AI服务暂时不可用，请检查配置。"
            
            self.add_to_history("user", user_input)
            self.save_chat_history()

            messages = self.get_chat_messages(user_input)            
            response = self.llm_client.chat_completion(messages)
            
            self.add_to_history("assistant", response)
            self.save_chat_history()
            
            if response:
                return response
            else:
                return "❌ 抱歉，我暂时无法回复。"
            
        except Exception as e:
            return f"❌ 抱歉，我遇到了一些问题: {str(e)}"
    
    def clear_history(self, archive_first: bool = False):
        """清除聊天历史"""
        if archive_first and self.chat_history:
            print("🗂️  正在归档现有聊天历史...")
            if self.archive_chat_history():
                print("✅ 聊天历史已归档并清除")
                return
        
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
   归档/archive - 手动归档聊天历史到向量数据库
   调试/debug - 调试历史搜索功能
   帮助/help/命令 - 显示此帮助信息

💡 提示:
   - 我会记住最近的对话内容
   - 我还会搜索相关的历史记录来提供更准确的回答
   - 你可以随时询问任何问题
   - 输入要清楚明确，我会尽力帮助你

版本: {self.config.VERSION}
        """
        print(help_text)
        return help_text
    
    def process_message(self, user_input: str):
        """处理用户消息"""
        # 检查特殊命令
        if user_input.lower() in self.config.EXIT_COMMANDS:
            print(f"\n嘿嘿～那我就不打扰你啦，记得想我哦～👋 {self.config.BOT_NAME}先走啦～")
            self.running = False
            return "再见！感谢使用聊天助手～👋"
        
        if user_input.lower() in self.config.CLEAR_COMMANDS:
            self.clear_history()
            return "✅ 聊天历史已清除"
        
        if user_input.lower() in getattr(self.config, 'ARCHIVE_COMMANDS', []):
            if self.chat_history:
                self.archive_chat_history()
            else:
                print("📝 当前没有聊天历史需要归档")
            return "✅ 聊天历史已归档到向量数据库"
        
        if user_input.lower() in self.config.HELP_COMMANDS:
            help_text = self.show_help()
            return help_text
        
        # 获取AI回复
        response = self.get_response(user_input)        
        return response
    
    def get_last_chat_time(self) -> datetime:
        """获取最后一次聊天的时间"""
        if not self.chat_history:
            return datetime.min
        
        try:
            last_item = self.chat_history[-1]
            timestamp_str = last_item.get("timestamp", "")
            if timestamp_str:
                return datetime.fromisoformat(timestamp_str)
        except Exception as e:
            print(f"⚠️  解析时间戳失败: {e}")
        
        return datetime.min
    
    def should_archive_history(self) -> bool:
        """检查是否应该归档聊天历史"""
        if not self.chat_history:
            return False
        
        last_chat_time = self.get_last_chat_time()
        if last_chat_time == datetime.min:
            return False
        
        # 检查是否超过归档间隔
        archive_interval = getattr(self.config, 'ARCHIVE_INTERVAL_HOURS', 6)
        time_diff = datetime.now() - last_chat_time
        
        return time_diff.total_seconds() >= archive_interval * 3600
    
    def backup_chat_history_to_file(self) -> str:
        """将聊天历史备份到文件"""
        try:
            backup_dir = getattr(self.config, 'ARCHIVE_BACKUP_DIR', 'data/archive')
            os.makedirs(backup_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(backup_dir, f"chat_history_{timestamp}.json")
            
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(self.chat_history, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 聊天历史已备份到: {backup_file}")
            return backup_file
            
        except Exception as e:
            print(f"⚠️  备份聊天历史失败: {e}")
            return ""
    
    def archive_chat_history(self) -> bool:
        """归档聊天历史到向量数据库并清理"""
        if not self.chat_history:
            return True
        
        try:
            print("🗂️  开始归档聊天历史...")
            
            # 1. 备份到文件
            backup_file = self.backup_chat_history_to_file()
            
            # 2. 保存到向量数据库
            archive_timestamp = datetime.now().isoformat()
            success = self.vector_db.save_chat_history_archive(
                self.chat_history, 
                archive_timestamp
            )
            
            if success:
                # 3. 清理聊天历史
                history_count = len(self.chat_history)
                self.chat_history = []
                self.save_chat_history()
                
                print(f"✅ 成功归档并清理了 {history_count} 条聊天记录")
                if backup_file:
                    print(f"📁 备份文件: {backup_file}")
                
                return True
            else:
                print("❌ 向量数据库归档失败，保留聊天历史")
                return False
                
        except Exception as e:
            print(f"❌ 归档聊天历史失败: {e}")
            return False
    
    def start_archive_task(self):
        """启动后台归档任务"""
        if self.archive_thread and self.archive_thread.is_alive():
            return
        
        self.archive_running = True
        self.archive_thread = threading.Thread(target=self._archive_worker, daemon=True)
        self.archive_thread.start()
        print("🗂️  自动归档任务已启动")
    
    def stop_archive_task(self):
        """停止后台归档任务"""
        self.archive_running = False
        if self.archive_thread and self.archive_thread.is_alive():
            self.archive_thread.join(timeout=1)
        print("🗂️  自动归档任务已停止")
    
    def _archive_worker(self):
        """后台归档工作线程"""
        check_interval = 3600  # 每小时检查一次
        
        while self.archive_running:
            try:
                if self.should_archive_history():
                    print("⏰ 检测到聊天历史需要归档...")
                    self.archive_chat_history()
                
                # 等待下次检查
                for _ in range(check_interval):
                    if not self.archive_running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                print(f"❌ 归档任务出错: {e}")
                time.sleep(60)  # 出错后等待1分钟再继续
    
    def start_chat(self):
        """启动聊天（提供一个更清晰的入口方法）"""
        try:
            self.simple_chat()
        except Exception as e:
            print(f"\n❌ 程序发生错误: {e}")
        finally:
            self.running = False
            self.stop_archive_task()  # 停止归档任务
    
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
            self.stop_archive_task()  # 停止归档任务
            print("\n👋 聊天结束")

if __name__ == "__main__":
    bot = ChatBot()
    bot.start_chat()
