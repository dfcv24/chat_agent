"""
事件驱动的聊天系统
实现用户输入和程序输出的解耦
"""
import asyncio
import json
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
import uuid


class EventType(Enum):
    """事件类型枚举"""
    USER_INPUT = "user_input"
    BOT_OUTPUT = "bot_output"
    SYSTEM_MESSAGE = "system_message"
    BOT_THINKING = "bot_thinking"
    BOT_ACTION = "bot_action"
    ERROR = "error"


@dataclass
class ChatEvent:
    """聊天事件数据结构"""
    event_id: str
    event_type: EventType
    content: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None
    audio_url: Optional[str] = None


class EventQueue:
    """事件队列管理器"""
    
    def __init__(self):
        self._queue = asyncio.Queue()
        self._subscribers = {}
    
    async def publish(self, event: ChatEvent):
        """发布事件"""
        await self._queue.put(event)
        
        # 通知订阅者
        for subscriber in self._subscribers.get(event.event_type, []):
            try:
                await subscriber(event)
            except Exception as e:
                print(f"事件处理器错误: {e}")
    
    def subscribe(self, event_type: EventType, handler: Callable):
        """订阅事件"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
    
    async def get_event(self):
        """获取下一个事件"""
        return await self._queue.get()
    
    def empty(self):
        """检查队列是否为空"""
        return self._queue.empty()


class ChatEventSystem:
    """聊天事件系统核心"""
    
    def __init__(self, chatbot):
        self.chatbot = chatbot
        self.event_queue = EventQueue()
        self.running = False
        self.tasks = []
        
        # 主动输出相关
        self.auto_output_enabled = True
        self.last_user_input_time = None
        self.idle_threshold = 30  # 30秒无输入后可以主动输出
        
        # 设置事件处理器
        self._setup_handlers()
        
        # 启动后台任务
        self._start_background_tasks()
    
    def _setup_handlers(self):
        """设置事件处理器"""
        # 用户输入处理器
        self.event_queue.subscribe(EventType.USER_INPUT, self._handle_user_input)
        
        # 机器人输出处理器
        self.event_queue.subscribe(EventType.BOT_OUTPUT, self._handle_bot_output)
        
        # 系统消息处理器
        self.event_queue.subscribe(EventType.SYSTEM_MESSAGE, self._handle_system_message)
    
    async def _handle_user_input(self, event: ChatEvent):
        """处理用户输入事件"""
        self.last_user_input_time = datetime.now()
        user_input = event.content.strip()
        
        # 检查特殊命令
        if user_input.lower() in ['/help', 'help', '帮助']:
            await self.emit_bot_output("这里是帮助信息...")
            return
        
        if user_input.lower() in ['/clear', 'clear', '清除']:
            self.chatbot.clear_history()
            await self.emit_bot_output("聊天历史已清除")
            return
        
        # 发出思考事件
        await self.emit_thinking("正在思考中...")
        
        # 处理普通对话
        try:
            # 可能产生多个回复
            responses = await self._process_user_message(user_input)
            
            for response in responses:
                await self.emit_bot_output(response)
                # 在多个回复之间添加延迟
                await asyncio.sleep(0.5)
                
        except Exception as e:
            await self.emit_error(f"处理消息时发生错误: {str(e)}")
    
    async def _process_user_message(self, user_input: str) -> List[str]:
        """处理用户消息，可能返回多个回复"""
        responses = []
        
        # 基础回复
        main_response = await asyncio.to_thread(self.chatbot.get_response, user_input)
        responses.append(main_response)
        
        # 根据内容可能产生额外回复
        if "天气" in user_input:
            responses.append("💡 提示：我可以为您查询更详细的天气信息，请告诉我具体的城市。")
        
        if "时间" in user_input or "几点" in user_input:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            responses.append(f"🕐 当前时间：{current_time}")
        
        # 如果是问候语，可能有友好的额外回复
        if any(word in user_input.lower() for word in ["你好", "hello", "hi", "嗨"]):
            responses.append("😊 很高兴和您聊天！有什么我可以帮助您的吗？")
        
        return responses
    
    async def _handle_bot_output(self, event: ChatEvent):
        """处理机器人输出事件"""
        # 这里可以添加输出后的处理逻辑
        # 比如保存到历史、语音合成等
        print(f"🤖 机器人输出: {event.content}")
    
    async def _handle_system_message(self, event: ChatEvent):
        """处理系统消息事件"""
        # 系统消息的特殊处理
        print(f"📢 系统消息: {event.content}")
    
    def _start_background_tasks(self):
        """启动后台任务"""
        # 主动输出任务
        asyncio.create_task(self._auto_output_task())
        
        # 定期清理任务
        asyncio.create_task(self._cleanup_task())
    
    async def _auto_output_task(self):
        """主动输出任务"""
        while True:
            await asyncio.sleep(3600)  # 每3600秒检查一次
            
            if not self.auto_output_enabled:
                continue
            
            # 检查是否应该主动输出
            if await self._should_auto_output():
                message = await self._generate_auto_message()
                if message:
                    await self.emit_bot_output(message)
    
    async def _should_auto_output(self) -> bool:
        """判断是否应该主动输出"""
        if self.last_user_input_time is None:
            return False
        
        # 计算距离上次用户输入的时间
        time_since_last_input = (datetime.now() - self.last_user_input_time).total_seconds()
        
        # 如果超过阈值且队列为空，可以主动输出
        return (time_since_last_input > self.idle_threshold)
    
    async def _generate_auto_message(self) -> Optional[str]:
        """生成主动输出的消息"""
        auto_messages = [
            "💭 有什么我可以帮助您的吗？",
            "🤔 我在这里等您的问题...",
            "📚 您可以问我任何问题，我会尽力帮助您！",
            "⭐ 今天过得怎么样？",
            "🎯 有什么想聊的话题吗？"
        ]
        
        import random
        return random.choice(auto_messages)
    
    async def _cleanup_task(self):
        """定期清理任务"""
        while True:
            await asyncio.sleep(3600)  # 每小时清理一次
            # 这里可以添加清理逻辑
            print("🧹 执行定期清理...")
    
    # 事件发射方法
    async def emit_user_input(self, content: str, metadata: Dict = None):
        """发射用户输入事件"""
        event = ChatEvent(
            event_id=str(uuid.uuid4()),
            event_type=EventType.USER_INPUT,
            content=content,
            timestamp=datetime.now(),
            metadata=metadata
        )
        await self.event_queue.publish(event)
    
    async def emit_bot_output(self, content: str, audio_url: str = None, metadata: Dict = None):
        """发射机器人输出事件"""
        event = ChatEvent(
            event_id=str(uuid.uuid4()),
            event_type=EventType.BOT_OUTPUT,
            content=content,
            timestamp=datetime.now(),
            metadata=metadata,
            audio_url=audio_url
        )
        await self.event_queue.publish(event)
    
    async def emit_thinking(self, content: str = "思考中..."):
        """发射思考事件"""
        event = ChatEvent(
            event_id=str(uuid.uuid4()),
            event_type=EventType.BOT_THINKING,
            content=content,
            timestamp=datetime.now()
        )
        await self.event_queue.publish(event)
    
    async def emit_error(self, content: str):
        """发射错误事件"""
        event = ChatEvent(
            event_id=str(uuid.uuid4()),
            event_type=EventType.ERROR,
            content=content,
            timestamp=datetime.now()
        )
        await self.event_queue.publish(event)
    
    async def emit_system_message(self, content: str):
        """发射系统消息事件"""
        event = ChatEvent(
            event_id=str(uuid.uuid4()),
            event_type=EventType.SYSTEM_MESSAGE,
            content=content,
            timestamp=datetime.now()
        )
        await self.event_queue.publish(event)
    
    def start(self):
        """启动事件系统"""
        self.running = True
    
    def stop(self):
        """停止事件系统"""
        self.running = False
        for task in self.tasks:
            task.cancel()
    
    def set_auto_output(self, enabled: bool):
        """设置是否启用主动输出"""
        self.auto_output_enabled = enabled
    
    def set_idle_threshold(self, seconds: int):
        """设置空闲阈值（秒）"""
        self.idle_threshold = seconds
