"""
向量数据库管理器测试文件
测试Milvus向量数据库的初始化、数据保存和搜索功能
"""

import sys
import os
import time
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from vector_db_manager import VectorDBManager, get_vector_db_manager
from config import ChatConfig


def test_vector_db_basic():
    """测试向量数据库基本功能"""
    print("🔧 开始测试向量数据库基本功能...")
    
    # 初始化
    config = ChatConfig()
    vector_db = VectorDBManager(config)
    
    print(f"📊 向量数据库可用性: {vector_db.is_available}")
    
    if not vector_db.is_available:
        print("⚠️  向量数据库不可用，请检查Milvus服务是否启动")
        return False
    
    # 获取统计信息
    stats = vector_db.get_collection_stats()
    print(f"📈 集合统计信息: {stats}")
    
    return True


def test_embedding():
    """测试文本嵌入功能"""
    print("\n🔧 开始测试文本嵌入功能...")
    
    vector_db = get_vector_db_manager()
    
    test_texts = [
        "你好，我是张三",
        "我喜欢编程和人工智能",
        "今天天气真好",
        "Python是一门很棒的编程语言",
        "向量数据库可以帮助我们进行语义搜索"
    ]
    
    for i, text in enumerate(test_texts):
        embedding = vector_db.get_embedding(text)
        if embedding:
            print(f"✅ 文本 {i+1} 嵌入成功，维度: {len(embedding)}")
            print(f"   原文: {text}")
            print(f"   向量前5维: {embedding[:5]}")
        else:
            print(f"❌ 文本 {i+1} 嵌入失败")
    
    return True


def test_save_and_search():
    """测试数据保存和搜索功能"""
    print("\n🔧 开始测试数据保存和搜索功能...")
    
    vector_db = get_vector_db_manager()
    
    if not vector_db.is_available:
        print("⚠️  向量数据库不可用，跳过保存和搜索测试")
        return False
    
    # 测试数据
    test_data = [
        {
            "content": "用户张三，25岁，是一名软件工程师，喜欢Python编程",
            "content_type": "user_info",
            "metadata": {"user_name": "张三", "age": 25, "profession": "软件工程师"}
        },
        {
            "content": "用户李四询问了关于机器学习的问题，他对深度学习很感兴趣",
            "content_type": "conversation",
            "metadata": {"user_name": "李四", "topic": "机器学习"}
        },
        {
            "content": "Python是一门解释型编程语言，广泛应用于数据科学和AI领域",
            "content_type": "knowledge",
            "metadata": {"topic": "编程", "language": "Python"}
        },
        {
            "content": "向量数据库可以存储高维向量并支持相似性搜索",
            "content_type": "knowledge",
            "metadata": {"topic": "数据库", "type": "向量数据库"}
        },
        {
            "content": "深度学习是机器学习的一个分支，使用神经网络进行学习",
            "content_type": "knowledge",
            "metadata": {"topic": "AI", "type": "深度学习"}
        }
    ]
    
    # 保存数据
    saved_ids = []
    print("💾 开始保存测试数据...")
    for i, data in enumerate(test_data):
        data_id = vector_db.save_data(
            content=data["content"],
            content_type=data["content_type"],
            metadata=data["metadata"]
        )
        if data_id:
            saved_ids.append(data_id)
            print(f"✅ 数据 {i+1} 保存成功: {data_id}")
        else:
            print(f"❌ 数据 {i+1} 保存失败")
    
    # 等待数据写入完成
    time.sleep(2)
    
    # 测试搜索
    print("\n🔍 开始测试相似性搜索...")
    test_queries = [
        "有谁是程序员？",
        "告诉我关于Python的信息",
        "什么是深度学习？",
        "向量数据库的作用是什么？",
        "有人问过机器学习的问题吗？"
    ]
    
    for query in test_queries:
        print(f"\n查询: {query}")
        results = vector_db.search_similar(query, limit=3, similarity_threshold=0.5)
        
        if results:
            for j, result in enumerate(results):
                print(f"  结果 {j+1}: (相似度: {result['similarity']:.3f})")
                print(f"    内容: {result['content'][:50]}...")
                print(f"    类型: {result['content_type']}")
                print(f"    元数据: {result['metadata']}")
        else:
            print("  未找到相关结果")
    
    # 测试按类型搜索
    print("\n🔍 开始测试按类型搜索...")
    content_types = ["user_info", "knowledge", "conversation"]
    
    for content_type in content_types:
        results = vector_db.search_by_content_type(content_type, limit=5)
        print(f"\n类型 '{content_type}' 的结果数量: {len(results)}")
        for result in results:
            print(f"  - {result['content'][:50]}...")
    
    return True


def test_global_instance():
    """测试全局实例功能"""
    print("\n🔧 开始测试全局实例功能...")
    
    # 获取全局实例
    db1 = get_vector_db_manager()
    db2 = get_vector_db_manager()
    
    # 验证是同一个实例
    if db1 is db2:
        print("✅ 全局实例功能正常")
        return True
    else:
        print("❌ 全局实例功能异常")
        return False


def main():
    """主测试函数"""
    print("🚀 开始向量数据库管理器测试\n")
    
    test_results = []
    
    # 执行各项测试
    tests = [
        ("基本功能测试", test_vector_db_basic),
        ("文本嵌入测试", test_embedding),
        ("保存和搜索测试", test_save_and_search),
        ("全局实例测试", test_global_instance)
    ]
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"🧪 {test_name}")
        print('='*50)
        
        try:
            result = test_func()
            test_results.append((test_name, result))
            
            if result:
                print(f"✅ {test_name} 通过")
            else:
                print(f"❌ {test_name} 失败")
                
        except Exception as e:
            print(f"❌ {test_name} 异常: {e}")
            test_results.append((test_name, False))
    
    # 输出测试总结
    print(f"\n{'='*50}")
    print("📊 测试总结")
    print('='*50)
    
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
    
    print(f"\n总计: {passed}/{total} 项测试通过")
    
    if passed == total:
        print("🎉 所有测试都通过了！")
    else:
        print("⚠️  部分测试未通过，请检查配置和服务状态")


if __name__ == "__main__":
    main()
