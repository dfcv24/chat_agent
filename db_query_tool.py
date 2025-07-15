#!/usr/bin/env python3
"""
数据库查询命令行工具
"""

import asyncio
import argparse
import json
import sys
from pathlib import Path
from db_query_manager import DatabaseQueryManager, load_db_config

async def main():
    """主函数 - 命令行接口"""
    parser = argparse.ArgumentParser(description="数据库查询工具")
    
    # 基本操作
    parser.add_argument("--list-tables", action="store_true", help="列出所有表")
    parser.add_argument("--table-info", help="获取指定表的详细信息")
    parser.add_argument("--db-info", action="store_true", help="获取数据库信息")
    
    # 查询操作
    parser.add_argument("--select", help="查询表数据，格式: table_name")
    parser.add_argument("--limit", type=int, default=10, help="限制返回行数")
    parser.add_argument("--columns", help="指定查询列，用逗号分隔")
    parser.add_argument("--where", help="查询条件，JSON格式，如: '{\"column\": \"value\"}'")
    parser.add_argument("--search", help="文本搜索，格式: table_name,search_term")
    
    # 统计分析
    parser.add_argument("--count", help="统计表行数")
    parser.add_argument("--stats", help="获取列统计信息，格式: table_name,column_name")
    parser.add_argument("--group-by", help="分组统计，格式: table_name,group_column[,agg_column,agg_func]")
    parser.add_argument("--quality-check", help="数据质量检查")
    parser.add_argument("--find-duplicates", help="查找重复记录，格式: table_name,column1[,column2,...]")
    
    # 导出功能
    parser.add_argument("--export-csv", help="导出到CSV，格式: table_name,file_path")
    parser.add_argument("--export-json", help="导出到JSON，格式: table_name,file_path")
    
    # 自定义查询
    parser.add_argument("--sql", help="执行自定义SQL查询")
    
    args = parser.parse_args()
    
    # 加载数据库配置
    db_config = load_db_config()
    
    # 创建查询管理器
    query_manager = DatabaseQueryManager(db_config)
    
    try:
        # 初始化连接池
        await query_manager.init_connection_pool()
        
        # 执行相应操作
        if args.list_tables:
            await handle_list_tables(query_manager)
        
        elif args.table_info:
            await handle_table_info(query_manager, args.table_info)
        
        elif args.db_info:
            await handle_db_info(query_manager)
        
        elif args.select:
            conditions = json.loads(args.where) if args.where else None
            columns = args.columns.split(',') if args.columns else None
            await handle_select(query_manager, args.select, columns, conditions, args.limit)
        
        elif args.search:
            parts = args.search.split(',', 1)
            if len(parts) != 2:
                print("错误: search参数格式应为 table_name,search_term")
                return 1
            await handle_search(query_manager, parts[0], parts[1], args.limit)
        
        elif args.count:
            conditions = json.loads(args.where) if args.where else None
            await handle_count(query_manager, args.count, conditions)
        
        elif args.stats:
            parts = args.stats.split(',')
            if len(parts) != 2:
                print("错误: stats参数格式应为 table_name,column_name")
                return 1
            await handle_stats(query_manager, parts[0], parts[1])
        
        elif args.group_by:
            await handle_group_by(query_manager, args.group_by, args.limit)
        
        elif args.quality_check:
            await handle_quality_check(query_manager, args.quality_check)
        
        elif args.find_duplicates:
            parts = args.find_duplicates.split(',')
            if len(parts) < 2:
                print("错误: find-duplicates参数格式应为 table_name,column1[,column2,...]")
                return 1
            await handle_find_duplicates(query_manager, parts[0], parts[1:])
        
        elif args.export_csv:
            parts = args.export_csv.split(',', 1)
            if len(parts) != 2:
                print("错误: export-csv参数格式应为 table_name,file_path")
                return 1
            conditions = json.loads(args.where) if args.where else None
            columns = args.columns.split(',') if args.columns else None
            await handle_export_csv(query_manager, parts[0], parts[1], conditions, columns)
        
        elif args.export_json:
            parts = args.export_json.split(',', 1)
            if len(parts) != 2:
                print("错误: export-json参数格式应为 table_name,file_path")
                return 1
            conditions = json.loads(args.where) if args.where else None
            columns = args.columns.split(',') if args.columns else None
            await handle_export_json(query_manager, parts[0], parts[1], conditions, columns)
        
        elif args.sql:
            await handle_custom_sql(query_manager, args.sql)
        
        else:
            parser.print_help()
    
    except Exception as e:
        print(f"错误: {e}")
        return 1
    
    finally:
        # 关闭连接池
        await query_manager.close_connection_pool()
    
    return 0


async def handle_list_tables(query_manager):
    """处理列出表的命令"""
    tables = await query_manager.list_tables()
    print(f"找到 {len(tables)} 个表:")
    for table in tables:
        print(f"  - {table['table_name']} ({table['table_type']})")


async def handle_table_info(query_manager, table_name):
    """处理获取表信息的命令"""
    info = await query_manager.get_table_info(table_name)
    if not info:
        print(f"表 '{table_name}' 不存在")
        return
    
    print(f"表 '{table_name}' 信息:")
    print(f"  类型: {info['table_type']}")
    print(f"  行数: {info['row_count']}")
    print(f"  大小: {info['size_info']['total_size']}")
    print(f"  列数: {len(info['columns'])}")
    print("\n列信息:")
    for col in info['columns']:
        nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
        print(f"  - {col['column_name']}: {col['data_type']} {nullable}")


async def handle_db_info(query_manager):
    """处理获取数据库信息的命令"""
    info = await query_manager.get_database_info()
    print("数据库信息:")
    for key, value in info.items():
        print(f"  {key}: {value}")


async def handle_select(query_manager, table_name, columns, conditions, limit):
    """处理查询数据的命令"""
    if columns:
        data = await query_manager.select_columns(table_name, columns, limit=limit, conditions=conditions)
    else:
        data = await query_manager.select_by_condition(table_name, conditions or {}, limit=limit)
    
    print(f"查询结果 ({len(data)} 行):")
    if data:
        # 打印表头
        headers = list(data[0].keys())
        print("  " + " | ".join(f"{h:<15}" for h in headers))
        print("  " + "-" * (len(headers) * 17))
        
        # 打印数据
        for row in data:
            values = [str(row.get(h, ''))[:15] for h in headers]
            print("  " + " | ".join(f"{v:<15}" for v in values))
    else:
        print("  没有找到数据")


async def handle_search(query_manager, table_name, search_term, limit):
    """处理文本搜索的命令"""
    data = await query_manager.search_text(table_name, search_term, limit=limit)
    print(f"搜索 '{search_term}' 的结果 ({len(data)} 行):")
    if data:
        # 打印前几条结果
        for i, row in enumerate(data[:5]):
            print(f"  {i+1}. {dict(row)}")
        if len(data) > 5:
            print(f"  ... 还有 {len(data) - 5} 条结果")
    else:
        print("  没有找到匹配的数据")


async def handle_count(query_manager, table_name, conditions):
    """处理统计行数的命令"""
    count = await query_manager.count_records(table_name, conditions=conditions)
    condition_str = f" (条件: {conditions})" if conditions else ""
    print(f"表 '{table_name}' 的行数{condition_str}: {count}")


async def handle_stats(query_manager, table_name, column_name):
    """处理获取列统计的命令"""
    stats = await query_manager.get_column_stats(table_name, column_name)
    print(f"列 '{column_name}' 的统计信息:")
    for key, value in stats.items():
        print(f"  {key}: {value}")


async def handle_group_by(query_manager, group_by_str, limit):
    """处理分组统计的命令"""
    parts = group_by_str.split(',')
    table_name = parts[0]
    group_column = parts[1]
    agg_column = parts[2] if len(parts) > 2 else None
    agg_func = parts[3] if len(parts) > 3 else 'COUNT'
    
    data = await query_manager.group_by_analysis(
        table_name, group_column, agg_column, agg_func, limit=limit
    )
    
    print(f"分组统计结果 ({len(data)} 组):")
    for row in data:
        print(f"  {dict(row)}")


async def handle_quality_check(query_manager, table_name):
    """处理数据质量检查的命令"""
    report = await query_manager.check_data_quality(table_name)
    print(f"表 '{table_name}' 数据质量报告:")
    print(f"  总行数: {report['total_rows']}")
    print("\n列分析:")
    
    for col in report['columns_analysis']:
        print(f"  {col['column_name']} ({col['data_type']}):")
        print(f"    - 空值率: {col['null_percentage']}%")
        print(f"    - 唯一值率: {col['unique_percentage']}%")
        print(f"    - 不同值数量: {col['distinct_values']}")
        if col['avg_value'] is not None:
            print(f"    - 平均值: {col['avg_value']}")


async def handle_find_duplicates(query_manager, table_name, columns):
    """处理查找重复记录的命令"""
    data = await query_manager.find_duplicates(table_name, columns)
    print(f"重复记录 ({len(data)} 组):")
    for row in data:
        print(f"  {dict(row)}")


async def handle_export_csv(query_manager, table_name, file_path, conditions, columns):
    """处理导出CSV的命令"""
    result = await query_manager.export_to_csv(table_name, file_path, conditions=conditions, columns=columns)
    print(f"导出结果: {result['message']}")
    print(f"导出行数: {result['rows_exported']}")


async def handle_export_json(query_manager, table_name, file_path, conditions, columns):
    """处理导出JSON的命令"""
    result = await query_manager.export_to_json(table_name, file_path, conditions=conditions, columns=columns)
    print(f"导出结果: {result['message']}")
    print(f"导出行数: {result['rows_exported']}")


async def handle_custom_sql(query_manager, sql):
    """处理自定义SQL查询的命令"""
    try:
        if sql.strip().upper().startswith('SELECT'):
            data = await query_manager.execute_query(sql)
            print(f"查询结果 ({len(data)} 行):")
            for row in data[:10]:  # 只显示前10行
                print(f"  {dict(row)}")
            if len(data) > 10:
                print(f"  ... 还有 {len(data) - 10} 行")
        else:
            result = await query_manager.execute_command(sql)
            print(f"命令执行结果: {result}")
    except Exception as e:
        print(f"SQL执行失败: {e}")


if __name__ == "__main__":
    # 加载环境变量
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("警告: 未安装python-dotenv，将使用系统环境变量")
    
    sys.exit(asyncio.run(main()))
