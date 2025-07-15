#!/usr/bin/env python3
"""
异步聊天机器人测试脚本
测试用户可以随时输入，agent也可以随时主动提问的功能
"""

import os
import sys
import time
from unittest.mock import Mock, patch

# 添加项目目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_async_features():
    """测试异步交互功能"""
    print("🧪 开始测试异步聊天功能...")
    
    try:
        from chatbot import ChatBot
        from config import ChatConfig
        
        # 创建机器人实例
        bot = ChatBot()
        
        # 测试配置
        print(f"✅ 主动提问延迟: {bot.config.PROACTIVE_QUESTION_DELAY}秒")
        print(f"✅ 最大空闲时间: {bot.config.MAX_IDLE_TIME}秒")
        print(f"✅ 检查间隔: {bot.config.QUESTION_CHECK_INTERVAL}秒")
        print(f"✅ 启用知识学习: {bot.config.ENABLE_KNOWLEDGE_LEARNING}")
        print(f"✅ 自动询问问题: {bot.config.AUTO_ASK_QUESTIONS}")
        
        # 测试知识管理器
        next_question = bot.knowledge_manager.get_next_question()
        if next_question:
            print(f"✅ 知识管理器正常，下一个问题: {next_question}")
        else:
            print("⚠️  知识管理器没有待询问的问题")
        
        # 测试主动提问逻辑
        should_ask_1 = bot.should_ask_question_now(10)  # 10秒空闲
        should_ask_2 = bot.should_ask_question_now(30)  # 30秒空闲
        should_ask_3 = bot.should_ask_question_now(70)  # 70秒空闲
        
        print(f"✅ 10秒空闲时是否应该提问: {should_ask_1}")
        print(f"✅ 30秒空闲时是否应该提问: {should_ask_2}")
        print(f"✅ 70秒空闲时是否应该提问: {should_ask_3}")
        
        print("\n🎉 异步功能测试完成！")
        print("\n💡 使用说明:")
        print("1. 运行 python chatbot.py 或 python main.py 开始聊天")
        print("2. 你可以随时输入消息")
        print("3. 如果你空闲20-60秒，我会主动询问一些问题")
        print("4. 输入 '退出' 或按 Ctrl+C 可以结束对话")
        
    except ImportError as e:
        print(f"❌ 导入错误: {e}")
        print("请确保所有依赖都已安装: pip install -r requirements.txt")
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")

if __name__ == "__main__":
    test_async_features()
