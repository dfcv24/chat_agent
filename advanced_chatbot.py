import json
import os
from datetime import datetime, timedelta
from typing import List, Dict
from openai import OpenAI
from config import ChatConfig
from prompt_toolkit import prompt
from task_manager import TaskManager, TaskExecutor, Task, TaskType, TaskPriority, TaskStatus
import threading
import time

class ProactiveChatBot:
    def __init__(self):
        self.config = ChatConfig()
        self.chat_history = []
        self.system_prompt = self.load_system_prompt()
        self.setup_api()
        self.load_chat_history()
        self.client = OpenAI()
        
        # 任务管理系统
        self.task_manager = TaskManager()
        self.task_executor = TaskExecutor(self)
        
        # 主动对话相关
        self.last_user_input_time = datetime.now()
        self.proactive_messages = []
        self.is_monitoring = False
        
        # 启动任务监控
        self.start_proactive_mode()
        
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
        """加载聊天历史"""
        self.chat_history = []
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
    
    def add_to_history(self, user_message: str, bot_response: str, is_proactive: bool = False):
        """添加对话到历史记录"""
        self.chat_history.append({
            "timestamp": datetime.now().isoformat(),
            "user": user_message,
            "bot": bot_response,
            "is_proactive": is_proactive
        })
        
        # 限制历史记录长度
        if len(self.chat_history) > self.config.MAX_HISTORY_LENGTH:
            self.chat_history = self.chat_history[-self.config.MAX_HISTORY_LENGTH:]
    
    def get_chat_messages(self, user_input: str, include_task_context: bool = True) -> List[Dict]:
        """构建发送给API的消息列表"""
        messages = [{"role": "system", "content": self.system_prompt}]
        
        # 添加任务上下文
        if include_task_context:
            task_context = self.get_task_context()
            if task_context:
                messages.append({"role": "system", "content": f"当前任务状态: {task_context}"})
        
        # 添加历史对话（最近几轮）
        recent_history = self.chat_history[-5:]  # 只取最近5轮对话
        for item in recent_history:
            messages.append({"role": "user", "content": item["user"]})
            messages.append({"role": "assistant", "content": item["bot"]})
        
        # 添加当前用户输入
        messages.append({"role": "user", "content": user_input})
        
        return messages
    
    def get_task_context(self) -> str:
        """获取任务相关上下文"""
        summary = self.task_manager.get_task_summary()
        today_tasks = self.task_manager.get_today_tasks()
        overdue_tasks = self.task_manager.get_overdue_tasks()
        
        context_parts = []
        
        if today_tasks:
            context_parts.append(f"今日有{len(today_tasks)}个任务待处理")
        
        if overdue_tasks:
            context_parts.append(f"有{len(overdue_tasks)}个任务已过期")
        
        if summary['active'] > 0:
            context_parts.append(f"当前有{summary['active']}个任务正在进行")
        
        return "; ".join(context_parts) if context_parts else ""
    
    def get_response(self, user_input: str, include_task_context: bool = True) -> str:
        """获取机器人回复"""
        try:
            if not self.config.API_KEY:
                return "❌ 抱歉，API密钥未配置，无法获取回复。请检查配置。"
            
            messages = self.get_chat_messages(user_input, include_task_context)
            
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
    
    def send_proactive_message(self, message: str):
        """发送主动消息"""
        print(f"\n💭 {self.config.BOT_NAME}: {message}")
        
        # 记录主动消息
        self.add_to_history("", message, is_proactive=True)
        self.save_chat_history()
        
        # 清空之前的主动消息队列
        self.proactive_messages = []
    
    def start_proactive_mode(self):
        """启动主动模式"""
        self.task_manager.start_monitoring()
        self.is_monitoring = True
        
        # 启动主动对话监控线程
        monitor_thread = threading.Thread(target=self._proactive_monitor, daemon=True)
        monitor_thread.start()
    
    def stop_proactive_mode(self):
        """停止主动模式"""
        self.task_manager.stop_monitoring()
        self.is_monitoring = False
    
    def _proactive_monitor(self):
        """主动对话监控循环"""
        while self.is_monitoring:
            try:
                # 检查触发的任务
                triggered_tasks = self.task_manager.check_triggers()
                
                for task in triggered_tasks:
                    # 执行任务并获取消息
                    message = self.task_executor.execute_task(task)
                    if message:
                        self.proactive_messages.append(message)
                        # 如果用户空闲，立即发送
                        if self._is_user_idle():
                            self.send_proactive_message(message)
                    
                    # 更新任务状态
                    self.task_manager.update_task_status(task.id, TaskStatus.COMPLETED)
                
                # 检查用户是否空闲太久
                if self._is_user_idle(minutes=30):
                    idle_message = self._generate_idle_message()
                    if idle_message:
                        self.send_proactive_message(idle_message)
                        self.last_user_input_time = datetime.now()  # 重置计时
                
                time.sleep(60)  # 每分钟检查一次
                
            except Exception as e:
                print(f"主动监控出错: {e}")
                time.sleep(60)
    
    def _is_user_idle(self, minutes: int = 5) -> bool:
        """检查用户是否空闲"""
        return (datetime.now() - self.last_user_input_time).total_seconds() > minutes * 60
    
    def _generate_idle_message(self) -> str:
        """生成空闲时的主动消息"""
        idle_messages = [
            "在忙什么呀？好久没听到你的声音了，有点想你呢🥺",
            "嘿嘿～不知道你现在在做什么，会不会太忙忘记我了？💕",
            "突然想起你了呢...现在方便聊天吗？🙈",
            "咦？你是不是在认真工作呀？记得要休息一下哦～",
            "好安静呀...你还在吗？我有点担心你呢😊"
        ]
        
        import random
        return random.choice(idle_messages)
    
    def clear_history(self):
        """清除聊天历史"""
        self.chat_history = []
        if os.path.exists(self.config.CHAT_HISTORY_FILE):
            os.remove(self.config.CHAT_HISTORY_FILE)
        print("✅ 聊天历史已清除")
    
    def show_help(self):
        """显示帮助信息"""
        help_text = f"""
🤖 {self.config.BOT_NAME} 智能助手 - 帮助信息

📝 基本使用:
   直接输入你的问题或想说的话

🔧 特殊命令:
   退出/再见/bye/exit/quit - 退出程序
   清除历史/清空/clear - 清除聊天历史
   帮助/help/命令 - 显示此帮助信息
   任务/tasks - 查看任务状态
   今日任务/today - 查看今日任务
   添加任务/add task - 添加新任务

🎯 智能功能:
   - 自动任务管理和提醒
   - 主动关心和问候
   - 智能对话上下文理解
   - 个性化互动体验

💡 提示:
   - 我会主动关心你，定时问候
   - 我会记住重要的任务和约定
   - 我会在合适的时间提醒你
   - 你可以随时和我分享你的想法

版本: {self.config.VERSION} (Pro版本)
        """
        print(help_text)
    
    def show_tasks(self):
        """显示任务状态"""
        summary = self.task_manager.get_task_summary()
        today_tasks = self.task_manager.get_today_tasks()
        overdue_tasks = self.task_manager.get_overdue_tasks()
        
        print(f"\n📋 任务状态摘要:")
        print(f"   总任务数: {summary['total']}")
        print(f"   待处理: {summary['pending']}")
        print(f"   进行中: {summary['active']}")
        print(f"   已完成: {summary['completed']}")
        print(f"   已过期: {summary['overdue']}")
        
        if today_tasks:
            print(f"\n📅 今日任务 ({len(today_tasks)}个):")
            for task in today_tasks:
                status_emoji = "⏳" if task.status == TaskStatus.PENDING else "🔄"
                print(f"   {status_emoji} {task.title}: {task.description}")
        
        if overdue_tasks:
            print(f"\n⚠️  过期任务 ({len(overdue_tasks)}个):")
            for task in overdue_tasks:
                print(f"   🔴 {task.title}: {task.description}")
    
    def add_task_interactive(self):
        """交互式添加任务"""
        try:
            print("\n➕ 添加新任务")
            title = input("任务标题: ").strip()
            if not title:
                print("❌ 任务标题不能为空")
                return
            
            description = input("任务描述: ").strip()
            
            print("任务类型:")
            print("1. 今日任务")
            print("2. 短期任务 (1-30天)")
            print("3. 长期任务 (30天+)")
            
            type_choice = input("选择类型 (1-3): ").strip()
            task_types = {
                "1": TaskType.DAILY,
                "2": TaskType.SHORT_TERM,
                "3": TaskType.LONG_TERM
            }
            task_type = task_types.get(type_choice, TaskType.DAILY)
            
            print("优先级:")
            print("1. 低")
            print("2. 中")
            print("3. 高") 
            print("4. 紧急")
            
            priority_choice = input("选择优先级 (1-4): ").strip()
            priorities = {
                "1": TaskPriority.LOW,
                "2": TaskPriority.MEDIUM,
                "3": TaskPriority.HIGH,
                "4": TaskPriority.URGENT
            }
            priority = priorities.get(priority_choice, TaskPriority.MEDIUM)
            
            # 创建任务
            task = Task(
                id="",
                title=title,
                description=description,
                task_type=task_type,
                priority=priority,
                status=TaskStatus.PENDING,
                created_at=datetime.now()
            )
            
            task_id = self.task_manager.add_task(task)
            print(f"✅ 任务已添加，ID: {task_id}")
            
        except KeyboardInterrupt:
            print("\n❌ 添加任务已取消")
    
    def process_health_info(self, user_input: str) -> dict:
        """处理用户的健康信息输入"""
        health_task = None
        for task in self.task_manager.tasks:
            if task.id == "health_management":
                health_task = task
                break
        
        if not health_task:
            return {"processed": False, "message": "健康管理任务未找到"}
        
        context = health_task.context
        stage = context.get("info_collection_stage", "start")
        user_input_lower = user_input.lower()
        
        # 基本信息收集
        if stage == "basic_info":
            # 提取年龄
            import re
            age_match = re.search(r'(\d{1,2})\s*岁|(\d{1,2})\s*年', user_input)
            if age_match:
                age = age_match.group(1) or age_match.group(2)
                context["user_profile"]["age"] = int(age)
            
            # 提取身高
            height_match = re.search(r'(\d{1,3})\s*[厘公]?[米分]', user_input)
            if height_match:
                height = int(height_match.group(1))
                context["user_profile"]["height"] = height if height > 100 else height * 100
            
            # 提取体重
            weight_match = re.search(r'(\d{1,3})\s*[公斤千克kg]', user_input)
            if weight_match:
                context["user_profile"]["weight"] = int(weight_match.group(1))
            
            # 判断性别
            if any(word in user_input for word in ["男", "男生", "男性", "先生"]):
                context["user_profile"]["gender"] = "male"
            elif any(word in user_input for word in ["女", "女生", "女性", "小姐", "女士"]):
                context["user_profile"]["gender"] = "female"
            
            # 判断运动量
            if any(word in user_input for word in ["经常运动", "运动很多", "天天运动", "爱运动"]):
                context["user_profile"]["activity_level"] = "high"
            elif any(word in user_input for word in ["偶尔运动", "有时运动", "周末运动"]):
                context["user_profile"]["activity_level"] = "medium"
            elif any(word in user_input for word in ["不运动", "很少运动", "懒得运动", "不爱运动"]):
                context["user_profile"]["activity_level"] = "low"
            
            # 检查是否收集完基本信息
            profile = context["user_profile"]
            if profile["age"] and profile["height"] and profile["weight"] and profile["gender"]:
                profile["basic_info_collected"] = True
                context["info_collection_stage"] = "diet_info"
                return {
                    "processed": True, 
                    "message": "基本信息收集完成！接下来了解饮食习惯",
                    "next_stage": "diet_info"
                }
        
        # 饮食信息收集
        elif stage == "diet_info":
            diet_info = context["diet_info"]
            
            # 饮食偏好
            if any(word in user_input for word in ["素食", "吃素", "不吃肉"]):
                diet_info["dietary_preferences"].append("vegetarian")
            elif any(word in user_input for word in ["减肥", "控制体重", "少吃"]):
                diet_info["dietary_preferences"].append("weight_loss")
            elif any(word in user_input for word in ["增重", "长胖", "多吃"]):
                diet_info["dietary_preferences"].append("weight_gain")
            
            # 过敏信息
            if any(word in user_input for word in ["过敏", "不能吃"]):
                # 这里可以进一步解析具体过敏食物
                diet_info["food_allergies"].append("需要详细了解")
            
            # 用餐时间
            breakfast_time = re.search(r'早[餐饭]?\s*(\d{1,2}):?(\d{0,2})', user_input)
            if breakfast_time:
                hour = breakfast_time.group(1)
                minute = breakfast_time.group(2) or "00"
                diet_info["meal_times"]["breakfast"] = f"{hour}:{minute}"
            
            context["info_collection_stage"] = "exercise_preferences"
            return {
                "processed": True,
                "message": "饮食习惯记录完成！现在了解运动偏好",
                "next_stage": "exercise_preferences"
            }
        
        # 运动偏好收集
        elif stage == "exercise_preferences":
            exercise_info = context["exercise_info"]
            
            # 运动类型偏好
            if any(word in user_input for word in ["跑步", "慢跑", "晨跑"]):
                exercise_info["preferred_exercises"].append("running")
            elif any(word in user_input for word in ["瑜伽", "yoga"]):
                exercise_info["preferred_exercises"].append("yoga")
            elif any(word in user_input for word in ["游泳"]):
                exercise_info["preferred_exercises"].append("swimming")
            elif any(word in user_input for word in ["健身", "撸铁", "力量训练"]):
                exercise_info["preferred_exercises"].append("strength_training")
            elif any(word in user_input for word in ["散步", "走路"]):
                exercise_info["preferred_exercises"].append("walking")
            
            # 运动目标
            if any(word in user_input for word in ["减肥", "瘦身"]):
                exercise_info["fitness_goals"].append("weight_loss")
            elif any(word in user_input for word in ["增肌", "练肌肉"]):
                exercise_info["fitness_goals"].append("muscle_building")
            elif any(word in user_input for word in ["保持健康", "身体健康"]):
                exercise_info["fitness_goals"].append("health_maintenance")
            
            context["info_collection_stage"] = "completed"
            context["next_action"] = "create_health_plan"
            
            return {
                "processed": True,
                "message": "信息收集完成！准备制定健康计划",
                "next_stage": "completed"
            }
        
        return {"processed": False, "message": "未识别的健康信息"}

    def check_health_keywords(self, user_input: str) -> bool:
        """检查用户输入是否包含健康相关关键词"""
        health_keywords = [
            "身体", "健康", "运动", "锻炼", "饮食", "吃饭", "体重", "减肥", "增重",
            "睡眠", "休息", "疲劳", "累", "精神", "心情", "压力", "焦虑",
            "营养", "维生素", "蛋白质", "碳水", "脂肪", "卡路里",
            "跑步", "游泳", "瑜伽", "健身", "散步", "爬山"
        ]
        
        return any(keyword in user_input for keyword in health_keywords)
    
    def chat_loop(self):
        """主聊天循环"""
        print(f"\n{self.config.WELCOME_MESSAGE}")
        print("🎯 智能任务助手已启动，我会主动关心你哦～")
        
        try:
            while True:
                # 检查是否有主动消息要发送
                if self.proactive_messages and self._is_user_idle(minutes=1):
                    message = self.proactive_messages.pop(0)
                    self.send_proactive_message(message)
                
                user_input = prompt(f"\n😊 你: ").strip()
                
                if not user_input:
                    continue
                
                # 更新用户输入时间
                self.last_user_input_time = datetime.now()
                
                # 检查特殊命令
                if user_input.lower() in self.config.EXIT_COMMANDS:
                    print(f"\n嘿嘿～那我就不打扰你啦，记得想我哦～👋 {self.config.BOT_NAME}先走啦～")
                    self.stop_proactive_mode()
                    break
                
                if user_input.lower() in self.config.CLEAR_COMMANDS:
                    self.clear_history()
                    continue
                
                if user_input.lower() in self.config.HELP_COMMANDS:
                    self.show_help()
                    continue
                
                if user_input.lower() in ["任务", "tasks"]:
                    self.show_tasks()
                    continue
                
                if user_input.lower() in ["今日任务", "today"]:
                    today_tasks = self.task_manager.get_today_tasks()
                    if today_tasks:
                        print(f"\n📅 今日任务 ({len(today_tasks)}个):")
                        for task in today_tasks:
                            print(f"   • {task.title}: {task.description}")
                    else:
                        print("\n📅 今日暂无任务")
                    continue
                
                if user_input.lower() in ["添加任务", "add task"]:
                    self.add_task_interactive()
                    continue
                
                # 检查并处理健康信息
                health_result = self.process_health_info(user_input)
                if health_result["processed"]:
                    health_response = health_result["message"]
                    # 如果有下一阶段，触发对应的收集行动
                    if "next_stage" in health_result:
                        health_task = None
                        for task in self.task_manager.tasks:
                            if task.id == "health_management":
                                health_task = task
                                break
                        if health_task:
                            additional_msg = self.task_executor._collect_health_info(health_task)
                            if additional_msg:
                                health_response += f"\n\n{additional_msg}"
                    
                    print(f"\n🤖 {self.config.BOT_NAME}: {health_response}")
                    self.add_to_history(user_input, health_response)
                    self.save_chat_history()
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
            self.stop_proactive_mode()
        except Exception as e:
            print(f"\n❌ 程序发生错误: {e}")
            self.stop_proactive_mode()

if __name__ == "__main__":
    bot = ProactiveChatBot()
    bot.chat_loop()
