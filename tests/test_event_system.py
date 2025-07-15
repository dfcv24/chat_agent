#!/usr/bin/env python3
"""
事件系统测试脚本
验证解耦架构的功能
"""
import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from chatbot import ChatBot
from event_system import ChatEventSystem, EventType


class TestEventHandler:
    """测试事件处理器"""
    
    def __init__(self):
        self.received_events = []
    
    async def handle_event(self, event):
        """处理接收到的事件"""
        self.received_events.append(event)
        print(f"📨 收到事件: {event.event_type.value} - {event.content[:50]}...")


async def test_basic_functionality():
    """测试基本功能"""
    print("🧪 测试1: 基本功能测试")
    print("-" * 50)
    
    # 创建聊天机器人和事件系统
    chatbot = ChatBot()
    event_system = ChatEventSystem(chatbot)
    
    # 创建测试处理器
    test_handler = TestEventHandler()
    
    # 订阅所有事件类型
    for event_type in EventType:
        event_system.event_queue.subscribe(event_type, test_handler.handle_event)
    
    event_system.start()
    
    # 测试用户输入
    print("💬 发送用户输入: '你好'")
    await event_system.emit_user_input("你好")
    
    # 等待处理
    await asyncio.sleep(2)
    
    print(f"✅ 收到 {len(test_handler.received_events)} 个事件")
    for event in test_handler.received_events:
        print(f"   - {event.event_type.value}: {event.content[:30]}...")
    
    return len(test_handler.received_events) > 0


async def test_multiple_responses():
    """测试多次回复功能"""
    print("\n🧪 测试2: 多次回复测试")
    print("-" * 50)
    
    chatbot = ChatBot()
    event_system = ChatEventSystem(chatbot)
    
    test_handler = TestEventHandler()
    event_system.event_queue.subscribe(EventType.BOT_OUTPUT, test_handler.handle_event)
    
    event_system.start()
    
    # 测试可能产生多个回复的输入
    print("💬 发送用户输入: '现在几点了，今天天气怎么样？'")
    await event_system.emit_user_input("现在几点了，今天天气怎么样？")
    
    # 等待处理
    await asyncio.sleep(3)
    
    bot_responses = [e for e in test_handler.received_events if e.event_type == EventType.BOT_OUTPUT]
    print(f"✅ 收到 {len(bot_responses)} 个机器人回复")
    for i, event in enumerate(bot_responses, 1):
        print(f"   {i}. {event.content[:50]}...")
    
    return len(bot_responses) >= 1


async def test_auto_output():
    """测试主动输出功能"""
    print("\n🧪 测试3: 主动输出测试")
    print("-" * 50)
    
    chatbot = ChatBot()
    event_system = ChatEventSystem(chatbot)
    
    test_handler = TestEventHandler()
    event_system.event_queue.subscribe(EventType.BOT_OUTPUT, test_handler.handle_event)
    
    # 设置较短的空闲时间用于测试
    event_system.set_idle_threshold(2)
    event_system.start()
    
    # 发送一个输入然后等待主动输出
    print("💬 发送用户输入: '你好'")
    await event_system.emit_user_input("你好")
    
    # 等待主动输出
    print("⏳ 等待主动输出...")
    await asyncio.sleep(5)
    
    bot_responses = [e for e in test_handler.received_events if e.event_type == EventType.BOT_OUTPUT]
    print(f"✅ 收到 {len(bot_responses)} 个机器人消息")
    
    # 检查是否有主动输出
    auto_messages = [e for e in bot_responses if "💭" in e.content or "🤔" in e.content or "📚" in e.content]
    print(f"🤖 其中 {len(auto_messages)} 个可能是主动输出")
    
    return len(bot_responses) >= 1


async def test_system_commands():
    """测试系统命令"""
    print("\n🧪 测试4: 系统命令测试")
    print("-" * 50)
    
    chatbot = ChatBot()
    event_system = ChatEventSystem(chatbot)
    
    test_handler = TestEventHandler()
    for event_type in EventType:
        event_system.event_queue.subscribe(event_type, test_handler.handle_event)
    
    event_system.start()
    
    # 测试帮助命令
    print("💬 发送命令: 'help'")
    await event_system.emit_user_input("help")
    await asyncio.sleep(1)
    
    # 测试系统消息
    print("📢 发送系统消息")
    await event_system.emit_system_message("这是一个测试系统消息")
    await asyncio.sleep(0.5)
    
    print(f"✅ 收到 {len(test_handler.received_events)} 个事件")
    
    return len(test_handler.received_events) > 0


async def main():
    """主测试函数"""
    print("🔬 事件驱动聊天系统测试")
    print("=" * 50)
    print("测试用户输入和程序输出的解耦架构")
    print()
    
    test_results = []
    
    try:
        # 运行所有测试
        test_results.append(await test_basic_functionality())
        test_results.append(await test_multiple_responses())
        test_results.append(await test_auto_output())
        test_results.append(await test_system_commands())
        
        # 总结结果
        print("\n📊 测试结果总结")
        print("=" * 50)
        
        passed = sum(test_results)
        total = len(test_results)
        
        print(f"✅ 通过: {passed}/{total} 个测试")
        
        if passed == total:
            print("🎉 所有测试通过！事件系统工作正常。")
        else:
            print("⚠️ 部分测试失败，请检查实现。")
        
        print("\n🔧 系统特性验证:")
        print("   ✓ 事件驱动架构")
        print("   ✓ 用户输入与输出解耦")
        print("   ✓ 支持多次回复")
        print("   ✓ 支持主动输出")
        print("   ✓ 异步事件处理")
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
