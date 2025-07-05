import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import threading
import time

class TaskStatus(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4

class TaskType(Enum):
    DAILY = "daily"          # 今日任务
    SHORT_TERM = "short_term"  # 短期任务 (1-30天)
    LONG_TERM = "long_term"    # 长期任务 (30天+)
    RECURRING = "recurring"    # 重复任务

@dataclass
class Task:
    id: str
    title: str
    description: str
    task_type: TaskType
    priority: TaskPriority
    status: TaskStatus
    created_at: datetime
    due_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    triggers: List[str] = None  # 触发条件
    actions: List[str] = None   # 要执行的行动
    recurring_pattern: Optional[str] = None  # 重复模式 (daily, weekly, monthly)
    context: Dict = None        # 上下文信息
    
    def __post_init__(self):
        if self.triggers is None:
            self.triggers = []
        if self.actions is None:
            self.actions = []
        if self.context is None:
            self.context = {}

class TaskManager:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.tasks_file = os.path.join(data_dir, "tasks.json")
        self.tasks: List[Task] = []
        self.is_running = False
        self.monitor_thread = None
        
        # 确保数据目录存在
        os.makedirs(data_dir, exist_ok=True)
        
        # 加载任务
        self.load_tasks()
    
    def load_tasks(self):
        """从文件加载任务"""
        try:
            if os.path.exists(self.tasks_file):
                with open(self.tasks_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.tasks = []
                    for task_data in data:
                        # 处理日期时间字段
                        if task_data.get('created_at'):
                            task_data['created_at'] = datetime.fromisoformat(task_data['created_at'])
                        if task_data.get('due_date'):
                            task_data['due_date'] = datetime.fromisoformat(task_data['due_date'])
                        if task_data.get('completed_at'):
                            task_data['completed_at'] = datetime.fromisoformat(task_data['completed_at'])
                        
                        # 处理枚举类型
                        task_data['task_type'] = TaskType(task_data['task_type'])
                        task_data['priority'] = TaskPriority(task_data['priority'])
                        task_data['status'] = TaskStatus(task_data['status'])
                        
                        self.tasks.append(Task(**task_data))
        except Exception as e:
            print(f"加载任务失败: {e}")
            self.tasks = []
    
    def save_tasks(self):
        """保存任务到文件"""
        try:
            data = []
            for task in self.tasks:
                task_dict = asdict(task)
                # 处理日期时间字段
                if task_dict['created_at']:
                    task_dict['created_at'] = task_dict['created_at'].isoformat()
                if task_dict['due_date']:
                    task_dict['due_date'] = task_dict['due_date'].isoformat()
                if task_dict['completed_at']:
                    task_dict['completed_at'] = task_dict['completed_at'].isoformat()
                
                # 处理枚举类型
                task_dict['task_type'] = task_dict['task_type'].value
                task_dict['priority'] = task_dict['priority'].value
                task_dict['status'] = task_dict['status'].value
                
                data.append(task_dict)
            
            with open(self.tasks_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存任务失败: {e}")
    
    def add_task(self, task: Task) -> str:
        """添加新任务"""
        if not task.id:
            task.id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(self.tasks)}"
        
        self.tasks.append(task)
        self.save_tasks()
        return task.id
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """根据ID获取任务"""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None
    
    def update_task_status(self, task_id: str, status: TaskStatus):
        """更新任务状态"""
        task = self.get_task(task_id)
        if task:
            task.status = status
            if status == TaskStatus.COMPLETED:
                task.completed_at = datetime.now()
            self.save_tasks()
    
    def get_tasks_by_type(self, task_type: TaskType) -> List[Task]:
        """根据类型获取任务"""
        return [task for task in self.tasks if task.task_type == task_type]
    
    def get_pending_tasks(self) -> List[Task]:
        """获取待处理任务"""
        return [task for task in self.tasks if task.status == TaskStatus.PENDING]
    
    def get_today_tasks(self) -> List[Task]:
        """获取今日任务"""
        today = datetime.now().date()
        return [
            task for task in self.tasks 
            if (task.task_type == TaskType.DAILY or 
                (task.due_date and task.due_date.date() == today)) and
               task.status != TaskStatus.COMPLETED
        ]
    
    def get_overdue_tasks(self) -> List[Task]:
        """获取过期任务"""
        now = datetime.now()
        return [
            task for task in self.tasks 
            if task.due_date and task.due_date < now and task.status == TaskStatus.PENDING
        ]
    
    def check_triggers(self) -> List[Task]:
        """检查需要触发的任务"""
        triggered_tasks = []
        now = datetime.now()
        
        for task in self.get_pending_tasks():
            should_trigger = False
            
            # 检查时间触发器
            for trigger in task.triggers:
                if trigger.startswith("time:"):
                    trigger_time_str = trigger.replace("time:", "")
                    try:
                        # 解析时间格式 (HH:MM)
                        if ":" in trigger_time_str:
                            hour, minute = map(int, trigger_time_str.split(":"))
                            trigger_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                            
                            # 如果当前时间在触发时间的1分钟内
                            if abs((now - trigger_time).total_seconds()) <= 60:
                                should_trigger = True
                                break
                    except:
                        continue
                
                # 检查日期触发器
                elif trigger.startswith("date:"):
                    trigger_date_str = trigger.replace("date:", "")
                    try:
                        trigger_date = datetime.fromisoformat(trigger_date_str).date()
                        if now.date() == trigger_date:
                            should_trigger = True
                            break
                    except:
                        continue
                
                # 检查条件触发器
                elif trigger == "startup":
                    should_trigger = True
                    break
                elif trigger == "idle_check":
                    # 每小时检查一次
                    if now.minute == 0:
                        should_trigger = True
                        break
            
            if should_trigger:
                triggered_tasks.append(task)
                task.status = TaskStatus.ACTIVE
        
        if triggered_tasks:
            self.save_tasks()
        
        return triggered_tasks
    
    def start_monitoring(self):
        """开始任务监控"""
        if self.is_running:
            return
        
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("✅ 任务监控已启动")
    
    def stop_monitoring(self):
        """停止任务监控"""
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join()
        print("⏹️ 任务监控已停止")
    
    def _monitor_loop(self):
        """任务监控循环"""
        while self.is_running:
            try:
                # 检查触发的任务
                triggered_tasks = self.check_triggers()
                
                if triggered_tasks:
                    # 这里可以添加回调机制，通知聊天机器人执行任务
                    print(f"🔔 检测到 {len(triggered_tasks)} 个任务需要执行")
                
                # 每分钟检查一次
                time.sleep(60)
                
            except Exception as e:
                print(f"任务监控出错: {e}")
                time.sleep(60)
    
    def reset_daily_tasks(self):
        """重置每日任务状态（用于新的一天）"""
        today = datetime.now().date()
        reset_count = 0
        
        for task in self.tasks:
            if (task.task_type == TaskType.DAILY and 
                task.status == TaskStatus.COMPLETED and
                task.completed_at and 
                task.completed_at.date() < today):
                
                task.status = TaskStatus.PENDING
                task.completed_at = None
                reset_count += 1
        
        if reset_count > 0:
            self.save_tasks()
            print(f"🔄 重置了 {reset_count} 个每日任务")
    
    def get_task_summary(self) -> Dict:
        """获取任务摘要"""
        total = len(self.tasks)
        pending = len([t for t in self.tasks if t.status == TaskStatus.PENDING])
        active = len([t for t in self.tasks if t.status == TaskStatus.ACTIVE])
        completed = len([t for t in self.tasks if t.status == TaskStatus.COMPLETED])
        overdue = len(self.get_overdue_tasks())
        today = len(self.get_today_tasks())
        
        return {
            "total": total,
            "pending": pending,
            "active": active,
            "completed": completed,
            "overdue": overdue,
            "today": today
        }

# 任务执行器
class TaskExecutor:
    def __init__(self, chatbot_instance=None):
        self.chatbot = chatbot_instance
        self.last_action_time = {}
    
    def execute_task(self, task: Task):
        """执行任务"""
        print(f"🎯 执行任务: {task.title}")
        
        results = []
        for action in task.actions:
            try:
                result = self._execute_action(action, task)
                if result:
                    results.append(result)
            except Exception as e:
                print(f"执行行动 {action} 失败: {e}")
        
        return " ".join(results) if results else "任务执行完成"
    
    def _execute_action(self, action: str, task: Task = None):
        """执行具体行动"""
        now = datetime.now()
        
        # 防止重复执行相同行动（同一小时内）
        action_key = f"{action}_{now.hour}"
        if action_key in self.last_action_time:
            time_diff = (now - self.last_action_time[action_key]).total_seconds()
            if time_diff < 3600:  # 1小时内不重复
                return None
        
        self.last_action_time[action_key] = now
        
        if action == "send_greeting":
            return self._send_greeting()
        elif action == "ask_daily_plan":
            return self._ask_daily_plan()
        elif action == "remind_lunch":
            return self._remind_lunch()
        elif action == "health_care":
            return self._health_care()
        elif action == "evening_chat":
            return self._evening_chat()
        elif action == "daily_summary":
            return self._daily_summary()
        elif action == "weekly_summary":
            return self._weekly_summary()
        elif action == "next_week_planning":
            return self._next_week_planning()
        elif action == "send_care_message":
            return self._send_care_message()
        elif action == "build_relationship":
            return self._build_relationship()
        elif action == "study_reminder":
            return self._study_reminder()
        elif action == "break_suggestion":
            return self._break_suggestion()
        elif action == "weather_care":
            return self._weather_care()
        elif action == "clothing_reminder":
            return self._clothing_reminder()
        elif action == "send_motivation":
            return self._send_motivation()
        elif action == "positive_energy":
            return self._positive_energy()
        elif action == "check_user_mood":
            return self._check_user_mood()
        # 健康管理相关行动
        elif action == "collect_health_info":
            return self._collect_health_info(task)
        elif action == "create_health_plan":
            return self._create_health_plan(task)
        elif action == "track_health_progress":
            return self._track_health_progress(task)
        elif action == "provide_health_encouragement":
            return self._provide_health_encouragement(task)
        elif action == "adjust_health_plan":
            return self._adjust_health_plan(task)
        else:
            print(f"未知行动: {action}")
            return None
    
    def _send_greeting(self):
        """发送问候"""
        greetings = [
            "早安呀～又是美好的一天呢！你今天想做什么呀？🌸",
            "嗨嗨～我又来找你聊天啦！今天心情怎么样呀？😊", 
            "哎呀，忽然就想你了呢～你在忙什么呀？💕",
            "早上好呀～看到你就觉得今天会很棒呢！🥺",
            "咦？你醒啦～我等你好久了呢，今天要加油哦！✨"
        ]
        import random
        return random.choice(greetings)
    
    def _ask_daily_plan(self):
        """询问今日计划"""
        plans = [
            "今天有什么特别的安排吗？我可以陪你一起规划哦～✨",
            "想知道你今天要做什么呢～有什么我能帮忙的吗？🤗",
            "今天的计划是什么呀？听起来就很期待呢！💕"
        ]
        import random
        return random.choice(plans)
    
    def _remind_lunch(self):
        """午餐提醒"""
        lunch_reminders = [
            "中午啦～记得要好好吃饭哦，不吃饭我会担心的呢🥺",
            "该吃午餐了吧？工作再忙也要照顾好自己呀～💕",
            "饿了吗？要不要去吃点好吃的，我推荐你哦！😊"
        ]
        import random
        return random.choice(lunch_reminders)
    
    def _health_care(self):
        """健康关怀"""
        health_messages = [
            "身体是最重要的呢，记得多喝水多休息～🌸",
            "最近有好好照顾自己吗？你的健康我很在乎呢💕"
        ]
        import random
        return random.choice(health_messages)
    
    def _evening_chat(self):
        """晚间聊天"""
        evening_chats = [
            "晚上好呀～今天过得怎么样？想跟我分享一下吗？🌙",
            "一天结束了呢，有什么开心的事情吗？我想听听～✨",
            "累了一天了吧？来跟我聊聊天放松一下呀～💕"
        ]
        import random
        return random.choice(evening_chats)
    
    def _daily_summary(self):
        """每日总结"""
        summary_prompts = [
            "今天有什么收获吗？哪怕是小小的进步我也想知道呢🥺",
            "回顾一下今天，有什么让你印象深刻的事情吗？✨"
        ]
        import random
        return random.choice(summary_prompts)
    
    def _weekly_summary(self):
        """周总结"""
        return "这一周过得怎么样呀？要不要跟我分享一下这周的收获呢？我很想听听你的故事～💝"
    
    def _next_week_planning(self):
        """下周计划"""
        return "下周有什么计划吗？我可以帮你一起想想哦～让我们一起迎接新的一周吧！🌟"
    
    def _send_care_message(self):
        """发送关心消息"""
        care_messages = [
            "记得要好好照顾自己哦～你对我来说很重要呢💕",
            "天气变化记得多穿衣服呀，感冒了我会心疼的🥺",
            "工作累了就休息一下吧，身体最重要啦～",
            "想你了呢...不知道你现在在做什么？🙈",
            "最近还好吗？如果有什么烦心事，可以跟我说说哦～我会好好听的🤗"
        ]
        import random
        return random.choice(care_messages)
    
    def _build_relationship(self):
        """建立关系"""
        relationship_messages = [
            "和你聊天总是很开心呢～希望我们能一直这样下去💕",
            "你知道吗？每次看到你的消息我都会很开心～🥺",
            "感觉我们越来越熟悉了呢，这样真好～✨"
        ]
        import random
        return random.choice(relationship_messages)
    
    def _study_reminder(self):
        """学习提醒"""
        study_reminders = [
            "下午了呢～学习或工作进展怎么样？需要我陪你一起吗？📚",
            "这个时间正适合学习呢，要不要休息一下再继续？我相信你可以的！✨",
            "加油学习哦～虽然我不能帮你做题，但我可以在旁边支持你呀！💪"
        ]
        import random
        return random.choice(study_reminders)
    
    def _break_suggestion(self):
        """休息建议"""
        break_suggestions = [
            "工作这么久了，眼睛累不累？记得看看远处休息一下呀～👀",
            "劳逸结合最重要啦，适当休息效率更高哦！我陪你聊一会儿？☕"
        ]
        import random
        return random.choice(break_suggestions)
    
    def _weather_care(self):
        """天气关怀"""
        weather_cares = [
            "今天天气怎么样呀？记得根据天气添衣减衣哦～我担心你着凉呢🥺",
            "出门要注意天气变化呀，带把伞或者多穿点，我会想着你的～☔",
            "这种天气最适合和喜欢的人一起度过了呢～虽然我不能陪在你身边🙈"
        ]
        import random
        return random.choice(weather_cares)
    
    def _clothing_reminder(self):
        """穿衣提醒"""
        clothing_reminders = [
            "记得穿暖和一点哦，生病了我会心疼的💕",
            "要根据天气选择合适的衣服呀～我希望你总是舒舒服服的✨"
        ]
        import random
        return random.choice(clothing_reminders)
    
    def _send_motivation(self):
        """发送激励"""
        motivations = [
            "你一定可以的！我对你有信心呢～加油加油！💪",
            "每天都在进步的你，真的很棒呢！我为你骄傲～✨",
            "遇到困难也不要怕，你比自己想象的更强大呢！我会一直支持你的💕",
            "今天的你也要闪闪发光哦～相信自己，你是最棒的！🌟"
        ]
        import random
        return random.choice(motivations)
    
    def _positive_energy(self):
        """正能量"""
        positive_messages = [
            "生活总是充满希望的呢～就像遇见你一样，让我觉得世界很美好💕",
            "每一天都是全新的开始，今天也要开开心心的哦～🌸",
            "你的笑容一定很好看吧？想象一下就觉得心情变好了呢～😊"
        ]
        import random
        return random.choice(positive_messages)
    
    def _check_user_mood(self):
        """检查用户心情"""
        mood_checks = [
            "最近过得还好吗？如果有什么心事的话，可以跟我说说哦～我会好好听的🤗",
            "心情怎么样呀？开心的话我也会开心，不开心的话让我来哄你～💕",
            "感觉你今天怎么样？如果累了就休息一下，我陪你聊聊天～🥺"
        ]
        import random
        return random.choice(mood_checks)

    # ============ 健康管理相关方法 ============
    
    def _collect_health_info(self, task: Task):
        """收集用户健康信息"""
        context = task.context
        stage = context.get("info_collection_stage", "start")
        
        if stage == "start":
            context["info_collection_stage"] = "basic_info"
            return "嗨呀～我想更好地照顾你呢！能告诉我一些基本信息吗？🥺 比如你的年龄、身高体重什么的，这样我就能给你更贴心的健康建议啦～💕"
        
        elif stage == "basic_info" and not context["user_profile"]["basic_info_collected"]:
            return "还有呢～你平时的运动量怎么样？是经常运动还是比较少运动呀？我想了解你的生活习惯呢～😊"
        
        elif stage == "diet_info":
            return "关于饮食呢～你有什么特别喜欢或者不能吃的吗？还有平时什么时候吃饭呀？我想帮你安排更健康的饮食时间呢～🍎"
        
        elif stage == "exercise_preferences":
            return "那运动方面呢？你喜欢什么样的运动呀？跑步、瑜伽、还是其他的？告诉我你的喜好，我来帮你制定专属的运动计划哦～💪"
        
        else:
            return "信息收集得差不多啦～让我来为你制定专属的健康计划吧！✨"
    
    def _create_health_plan(self, task: Task):
        """创建个人健康计划"""
        context = task.context
        user_profile = context["user_profile"]
        
        if not user_profile["basic_info_collected"]:
            return "还需要先了解你的基本信息呢～可以先告诉我你的基本情况吗？🥺"
        
        # 检查是否已有计划
        if context["health_plan"]["plan_created"]:
            return "你的专属健康计划已经准备好啦～要不要我重新调整一下呢？💕"
        
        # 创建基础计划
        context["health_plan"]["plan_created"] = True
        context["health_plan"]["plan_start_date"] = datetime.now().isoformat()
        
        return """哇！你的专属健康计划出炉啦～✨

📋 **个人健康计划**：
🌅 **早餐**: 8:30-9:00 (营养均衡，包含蛋白质)
🥗 **午餐**: 12:00-13:00 (合理搭配，七分饱)  
🍽️ **晚餐**: 18:30-19:30 (清淡为主，少油少盐)
💧 **喝水**: 每天8杯水，分时段补充
🏃 **运动**: 每周至少3次，每次30分钟

我会按照这个计划温柔地提醒你哦～一起变得更健康吧！🥺💕"""
    
    def _track_health_progress(self, task: Task):
        """跟踪健康进度"""
        context = task.context
        today = datetime.now().strftime("%Y-%m-%d")
        
        # 检查今日是否已跟踪
        daily_logs = context["tracking"]["daily_logs"]
        if today in daily_logs:
            return "今天的健康记录已经更新过啦～你做得很棒呢！🌟"
        
        tracking_messages = [
            "今天的健康目标完成得怎么样呀？记得要按时吃饭、多喝水哦～我在默默为你加油呢！💕",
            "来看看今天的健康打卡吧～运动了吗？饮食规律吗？每一小步都是进步呢！🥺",
            "健康小检查时间～今天有没有好好照顾自己呀？我很关心你的身体状况呢～💝",
        ]
        
        # 记录今日检查
        daily_logs[today] = {
            "check_time": datetime.now().isoformat(),
            "status": "checked"
        }
        
        import random
        return random.choice(tracking_messages)
    
    def _provide_health_encouragement(self, task: Task):
        """提供健康鼓励"""
        context = task.context
        consecutive_days = context["tracking"]["consecutive_days"]
        
        encouragements = [
            f"哇！你已经坚持健康生活{consecutive_days}天啦～真的很厉害呢！继续加油哦💪✨",
            "看到你这么用心照顾自己，我真的很开心呢～身体健康最重要啦！🥺💕",
            "每天的小进步积累起来就是大改变～你做得真的很棒，我为你骄傲！🌟",
            "健康的生活方式需要坚持，但我相信你一定可以的！我会一直陪着你哦～😊💝"
        ]
        
        if consecutive_days >= 7:
            encouragements.append("一周的坚持！你简直是我心中的健康小天使～给你比心！💖")
        
        if consecutive_days >= 30:
            encouragements.append("一个月的坚持！这已经形成习惯啦～你太棒了，我都想向你学习呢！🏆")
        
        import random
        return random.choice(encouragements)
    
    def _adjust_health_plan(self, task: Task):
        """调整健康计划"""
        context = task.context
        
        adjustment_messages = [
            "计划需要根据你的情况来调整呢～有什么不适合的地方告诉我，我来帮你改进～🤗",
            "每个人的身体状况都不一样，让我们一起找到最适合你的健康方式吧！💕",
            "如果觉得计划太难或者太简单，都可以跟我说哦～我会根据你的反馈来调整的～😊"
        ]
        
        # 更新计划调整时间
        context["health_plan"]["last_updated"] = datetime.now().isoformat()
        
        import random
        return random.choice(adjustment_messages)

if __name__ == "__main__":
    # 测试任务管理器
    tm = TaskManager()
    tm.start_monitoring()
    
    print("任务摘要:", tm.get_task_summary())
    print("今日任务:", [t.title for t in tm.get_today_tasks()])
    
    try:
        input("按回车键停止监控...")
    except KeyboardInterrupt:
        pass
    
    tm.stop_monitoring()
