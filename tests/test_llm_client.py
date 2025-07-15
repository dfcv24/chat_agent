#!/usr/bin/env python3
"""
LLM客户端测试脚本
测试新的大模型客户端功能和信息提取能力
"""

import os
import sys

# 添加项目目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_llm_client():
    """测试LLM客户端基础功能"""
    print("🧪 开始测试LLM客户端...")
    
    try:
        from llm_client import get_llm_client, LLMClient
        from config import ChatConfig
        
        # 测试配置加载
        config = ChatConfig()
        print(f"✅ 配置加载成功")
        print(f"   - API可用: {'是' if config.API_KEY else '否'}")
        print(f"   - 模型: {config.CHAT_MODEL_NAME}")
        print(f"   - API地址: {config.API_BASE_URL}")
        
        # 测试LLM客户端初始化
        llm_client = get_llm_client()
        print(f"✅ LLM客户端初始化成功")
        print(f"   - 可用状态: {'是' if llm_client.is_available else '否'}")
        
        if not llm_client.is_available:
            print("⚠️  LLM不可用，将测试fallback功能")
        
        # 测试简单聊天功能
        print("\n🔧 测试简单聊天功能...")
        if llm_client.is_available:
            response = llm_client.simple_chat(
                "你好，请简单介绍一下自己",
                system_prompt="你是一个友好的AI助手"
            )
            if response:
                print(f"✅ 聊天测试成功: {response[:100]}...")
            else:
                print("❌ 聊天测试失败")
        else:
            print("⚠️  跳过聊天测试（LLM不可用）")
        
        # 测试JSON提取功能
        print("\n🔧 测试JSON信息提取...")
        test_cases = [
            {
                "input": "我叫张三，今年25岁",
                "prompt": "从用户输入中提取姓名和年龄信息，以JSON格式返回：{\"name\": \"姓名\", \"age\": 年龄}"
            },
            {
                "input": "不想说",
                "prompt": "从用户输入中提取个人信息，如果用户拒绝则返回空JSON对象"
            }
        ]
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"   测试用例 {i}: {test_case['input']}")
            result = llm_client.extract_json(
                test_case["input"],
                test_case["prompt"],
                fallback_value={}
            )
            print(f"   结果: {result}")
        
        print("\n🎉 LLM客户端测试完成！")
        
    except ImportError as e:
        print(f"❌ 导入错误: {e}")
        print("请确保所有依赖都已安装")
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")

def test_knowledge_extraction():
    """测试知识提取功能"""
    print("\n🧪 开始测试知识提取功能...")
    
    try:
        from knowledge_manager import KnowledgeManager
        
        # 创建知识管理器
        km = KnowledgeManager()
        print("✅ 知识管理器初始化成功")
        
        # 测试信息提取
        test_cases = [
            ("我叫李四，今年30岁，是个程序员", "请告诉我你的基本信息"),
            ("我喜欢看电影和读书", "你有什么爱好？"),
            ("不想说", "你叫什么名字？"),
            ("我住在北京", "你在哪个城市？"),
            ("175cm", "你的身高是多少？")
        ]
        
        for user_response, question in test_cases:
            print(f"\n   问题: {question}")
            print(f"   回答: {user_response}")
            
            extracted = km.extract_info_from_response(user_response, question)
            print(f"   提取结果: {extracted}")
            
            if extracted:
                updated = km.update_knowledge(extracted)
                print(f"   更新状态: {'成功' if updated else '无需更新'}")
        
        print("\n🎉 知识提取测试完成！")
        
    except Exception as e:
        print(f"❌ 知识提取测试失败: {e}")

def test_chatbot_integration():
    """测试聊天机器人集成"""
    print("\n🧪 开始测试聊天机器人集成...")
    
    try:
        from chatbot import ChatBot
        
        # 创建聊天机器人
        bot = ChatBot()
        print("✅ 聊天机器人初始化成功")
        print(f"   - LLM可用: {'是' if bot.llm_client.is_available else '否'}")
        print(f"   - 知识管理: {'启用' if bot.config.ENABLE_KNOWLEDGE_LEARNING else '禁用'}")
        print(f"   - 主动提问: {'启用' if bot.config.AUTO_ASK_QUESTIONS else '禁用'}")
        
        # 测试基础回复功能
        if bot.llm_client.is_available:
            print("\n   测试基础对话...")
            test_response = bot.get_response("你好")
            if test_response and not test_response.startswith("❌"):
                print(f"✅ 对话测试成功: {test_response[:50]}...")
            else:
                print(f"❌ 对话测试失败: {test_response}")
        else:
            print("⚠️  跳过对话测试（LLM不可用）")
        
        print("\n🎉 聊天机器人集成测试完成！")
        
    except Exception as e:
        print(f"❌ 聊天机器人测试失败: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 开始LLM客户端和信息提取功能测试")
    print("=" * 60)
    
    test_llm_client()
    test_knowledge_extraction()
    test_chatbot_integration()
    
    print("\n" + "=" * 60)
    print("✨ 所有测试完成！")
    print("=" * 60)
    print("\n💡 使用说明:")
    print("1. 新的LLM客户端支持多种调用方式")
    print("2. 信息提取现在使用大模型进行意图识别")
    print("3. 在任何文件中都可以通过 get_llm_client() 获取LLM实例")
    print("4. 自动fallback到规则匹配（当LLM不可用时）")
