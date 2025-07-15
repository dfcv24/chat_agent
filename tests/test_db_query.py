#!/usr/bin/env python3
"""
数据库查询工具测试脚本
"""

import asyncio
import sys
import os
from pathlib import Path
from db_query_manager import DatabaseQueryManager, load_db_config

async def test_database_connection():
    """测试数据库连接"""
    print("=" * 60)
    print("测试数据库连接...")
    
    try:
        db_config = load_db_config()
        query_manager = DatabaseQueryManager(db_config)
        await query_manager.init_connection_pool()
        
        # 测试连接
        db_info = await query_manager.get_database_info()
        print("✅ 数据库连接成功!")
        print(f"   数据库版本: {db_info.get('version', 'Unknown')}")
        print(f"   数据库大小: {db_info.get('database_size', 'Unknown')}")
        print(f"   活动连接数: {db_info.get('active_connections', 'Unknown')}")
        print(f"   表数量: {db_info.get('tables_count', 'Unknown')}")
        
        await query_manager.close_connection_pool()
        return True
        
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False

async def test_basic_queries():
    """测试基本查询功能"""
    print("\n" + "=" * 60)
    print("测试基本查询功能...")
    
    try:
        db_config = load_db_config()
        query_manager = DatabaseQueryManager(db_config)
        await query_manager.init_connection_pool()
        
        # 列出所有表
        tables = await query_manager.list_tables()
        print(f"✅ 成功获取表列表，共 {len(tables)} 个表")
        
        if tables:
            # 测试第一个表的查询
            table_name = tables[0]['table_name']
            print(f"   测试表: {table_name}")
            
            # 获取表信息
            table_info = await query_manager.get_table_info(table_name)
            print(f"   - 行数: {table_info.get('row_count', 0)}")
            print(f"   - 列数: {len(table_info.get('columns', []))}")
            
            # 查询数据
            if table_info.get('row_count', 0) > 0:
                data = await query_manager.select_all(table_name, limit=3)
                print(f"   - 成功查询到 {len(data)} 条记录")
                
                # 统计功能
                count = await query_manager.count_records(table_name)
                print(f"   - 记录总数: {count}")
                
                # 数据质量检查（仅对小表进行）
                if count < 100000:  # 只对小于10万行的表做质量检查
                    quality = await query_manager.check_data_quality(table_name)
                    print(f"   - 数据质量检查完成，分析了 {len(quality['columns_analysis'])} 列")
        else:
            print("   没有找到表，可能需要先导入数据")
        
        await query_manager.close_connection_pool()
        return True
        
    except Exception as e:
        print(f"❌ 基本查询测试失败: {e}")
        return False

async def test_export_functionality():
    """测试导出功能"""
    print("\n" + "=" * 60)
    print("测试导出功能...")
    
    try:
        db_config = load_db_config()
        query_manager = DatabaseQueryManager(db_config)
        await query_manager.init_connection_pool()
        
        tables = await query_manager.list_tables()
        if not tables:
            print("   跳过导出测试：没有可用的表")
            await query_manager.close_connection_pool()
            return True
        
        table_name = tables[0]['table_name']
        
        # 测试CSV导出
        csv_file = f"test_export_{table_name}.csv"
        result = await query_manager.export_to_csv(table_name, csv_file)
        if result['status'] == 'success':
            print(f"✅ CSV导出成功: {result['rows_exported']} 行")
            # 清理测试文件
            if os.path.exists(csv_file):
                os.remove(csv_file)
        else:
            print(f"⚠️ CSV导出: {result['message']}")
        
        # 测试JSON导出
        json_file = f"test_export_{table_name}.json"
        result = await query_manager.export_to_json(table_name, json_file)
        if result['status'] == 'success':
            print(f"✅ JSON导出成功: {result['rows_exported']} 行")
            # 清理测试文件
            if os.path.exists(json_file):
                os.remove(json_file)
        else:
            print(f"⚠️ JSON导出: {result['message']}")
        
        await query_manager.close_connection_pool()
        return True
        
    except Exception as e:
        print(f"❌ 导出功能测试失败: {e}")
        return False

async def main():
    """主测试函数"""
    print("🔍 数据库查询工具测试")
    print("时间:", asyncio.get_event_loop().time())
    
    # 检查环境变量
    required_vars = ['POSTGRES_HOST', 'POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ 缺少环境变量: {missing_vars}")
        print("   请确保在 .env 文件中配置数据库连接信息")
        return 1
    
    # 运行测试
    tests = [
        ("数据库连接", test_database_connection),
        ("基本查询", test_basic_queries),
        ("导出功能", test_export_functionality),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ 测试 '{test_name}' 出现异常: {e}")
            results.append((test_name, False))
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结:")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {test_name}: {status}")
    
    print(f"\n总计: {passed}/{total} 个测试通过")
    
    if passed == total:
        print("🎉 所有测试通过！数据库查询工具可以正常使用。")
        return 0
    else:
        print("⚠️ 部分测试失败，请检查配置和数据库状态。")
        return 1

if __name__ == "__main__":
    # 加载环境变量
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("警告: 未安装python-dotenv，将使用系统环境变量")
    
    sys.exit(asyncio.run(main()))
