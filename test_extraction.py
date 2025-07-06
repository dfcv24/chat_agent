#!/usr/bin/env python3
"""测试大模型信息提取功能"""

from knowledge_manager import KnowledgeManager
import json

def test_extraction():
    """测试信息提取功能"""
    km = KnowledgeManager()
    
    # 测试用例
    test_cases = [
        {
            "question": "请告诉我你的姓名？",
            "response": "我叫张三",
            "expected": {"name": "张三"}
        },
        {
            "question": "你今年多大了？",
            "response": "我今年25岁",
            "expected": {"age": 25}
        },
        {
            "question": "你是男生还是女生？",
            "response": "我是男生",
            "expected": {"gender": "男"}
        },
        {
            "question": "你在哪个城市工作？",
            "response": "我在北京工作",
            "expected": {"location": "北京"}
        },
        {
            "question": "你的职业是什么？",
            "response": "我是软件工程师",
            "expected": {"occupation": "软件工程师"}
        },
        {
            "question": "你有什么爱好？",
            "response": "我喜欢看书和打篮球",
            "expected": {"hobbies": "我喜欢看书和打篮球"}
        },
        {
            "question": "你多高？",
            "response": "175cm",
            "expected": {"height": "175cm"}
        },
        {
            "question": "你的体重是多少？",
            "response": "65公斤",
            "expected": {"weight": "65kg"}
        },
        {
            "question": "你的姓名是什么？",
            "response": "不想说",
            "expected": {}
        },
        {
            "question": "你今年几岁？",
            "response": "不告诉你",
            "expected": {}
        }
    ]
    
    print("🧪 开始测试信息提取功能...\n")
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"测试 {i}:")
        print(f"  问题: {test_case['question']}")
        print(f"  回复: {test_case['response']}")
        
        extracted = km.extract_info_from_response(
            test_case['response'], 
            test_case['question']
        )
        
        print(f"  提取结果: {json.dumps(extracted, ensure_ascii=False)}")
        print(f"  期望结果: {json.dumps(test_case['expected'], ensure_ascii=False)}")
        
        # 简单验证
        success = True
        for key, value in test_case['expected'].items():
            if key not in extracted or extracted[key] != value:
                success = False
                break
        
        print(f"  结果: {'✅ 通过' if success else '❌ 失败'}\n")

if __name__ == "__main__":
    test_extraction()
