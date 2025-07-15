#!/usr/bin/env python3
"""
数据库查询管理器 - 提供各种常用的PostgreSQL查询功能
"""

import asyncio
import asyncpg
import json
import logging
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime, date
import pandas as pd
from pathlib import Path
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DatabaseQueryManager:
    """数据库查询管理器"""
    
    def __init__(self, db_config: Dict[str, Any]):
        """
        初始化数据库查询管理器
        
        Args:
            db_config: 数据库配置字典
        """
        self.db_config = db_config
        self.connection_pool: Optional[asyncpg.Pool] = None
    
    async def init_connection_pool(self):
        """初始化数据库连接池"""
        try:
            self.connection_pool = await asyncpg.create_pool(
                **self.db_config,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            logger.info("数据库连接池初始化成功")
        except Exception as e:
            logger.error(f"初始化数据库连接池失败: {e}")
            raise
    
    async def close_connection_pool(self):
        """关闭数据库连接池"""
        if self.connection_pool:
            await self.connection_pool.close()
            logger.info("数据库连接池已关闭")
    
    # ========== 基本查询功能 ==========
    
    async def execute_query(self, sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """
        执行查询并返回结果
        
        Args:
            sql: SQL查询语句
            params: 查询参数
            
        Returns:
            查询结果列表
        """
        async with self.connection_pool.acquire() as conn:
            if params:
                rows = await conn.fetch(sql, *params)
            else:
                rows = await conn.fetch(sql)
            return [dict(row) for row in rows]
    
    async def execute_single_query(self, sql: str, params: Optional[tuple] = None) -> Optional[Dict[str, Any]]:
        """
        执行查询并返回单条结果
        
        Args:
            sql: SQL查询语句
            params: 查询参数
            
        Returns:
            单条查询结果或None
        """
        async with self.connection_pool.acquire() as conn:
            if params:
                row = await conn.fetchrow(sql, *params)
            else:
                row = await conn.fetchrow(sql)
            return dict(row) if row else None
    
    async def execute_scalar(self, sql: str, params: Optional[tuple] = None) -> Any:
        """
        执行查询并返回标量值
        
        Args:
            sql: SQL查询语句
            params: 查询参数
            
        Returns:
            标量值
        """
        async with self.connection_pool.acquire() as conn:
            if params:
                return await conn.fetchval(sql, *params)
            else:
                return await conn.fetchval(sql)
    
    async def execute_command(self, sql: str, params: Optional[tuple] = None) -> str:
        """
        执行命令（INSERT, UPDATE, DELETE等）
        
        Args:
            sql: SQL命令语句
            params: 命令参数
            
        Returns:
            命令执行状态
        """
        async with self.connection_pool.acquire() as conn:
            if params:
                result = await conn.execute(sql, *params)
            else:
                result = await conn.execute(sql)
            return result
    
    # ========== 表和数据库元信息查询 ==========
    
    async def list_tables(self, schema: str = 'public') -> List[Dict[str, Any]]:
        """
        列出指定模式下的所有表
        
        Args:
            schema: 模式名称
            
        Returns:
            表信息列表
        """
        sql = """
        SELECT 
            table_name,
            table_type,
            is_insertable_into,
            is_typed
        FROM information_schema.tables 
        WHERE table_schema = $1
        ORDER BY table_name
        """
        return await self.execute_query(sql, (schema,))
    
    async def get_table_info(self, table_name: str, schema: str = 'public') -> Dict[str, Any]:
        """
        获取表的详细信息
        
        Args:
            table_name: 表名
            schema: 模式名称
            
        Returns:
            表信息字典
        """
        # 获取表基本信息
        table_sql = """
        SELECT 
            table_name,
            table_type,
            is_insertable_into
        FROM information_schema.tables 
        WHERE table_schema = $1 AND table_name = $2
        """
        table_info = await self.execute_single_query(table_sql, (schema, table_name))
        
        if not table_info:
            return {}
        
        # 获取列信息
        columns_info = await self.get_table_columns(table_name, schema)
        
        # 获取表大小
        size_info = await self.get_table_size(table_name, schema)
        
        # 获取行数
        row_count = await self.get_table_row_count(table_name, schema)
        
        return {
            **table_info,
            'columns': columns_info,
            'size_info': size_info,
            'row_count': row_count
        }
    
    async def get_table_columns(self, table_name: str, schema: str = 'public') -> List[Dict[str, Any]]:
        """
        获取表的列信息
        
        Args:
            table_name: 表名
            schema: 模式名称
            
        Returns:
            列信息列表
        """
        sql = """
        SELECT 
            column_name,
            data_type,
            character_maximum_length,
            is_nullable,
            column_default,
            ordinal_position
        FROM information_schema.columns 
        WHERE table_schema = $1 AND table_name = $2
        ORDER BY ordinal_position
        """
        return await self.execute_query(sql, (schema, table_name))
    
    async def get_table_size(self, table_name: str, schema: str = 'public') -> Dict[str, Any]:
        """
        获取表的大小信息
        
        Args:
            table_name: 表名
            schema: 模式名称
            
        Returns:
            表大小信息
        """
        sql = """
        SELECT 
            pg_size_pretty(pg_total_relation_size($1)) as total_size,
            pg_size_pretty(pg_relation_size($1)) as table_size,
            pg_size_pretty(pg_total_relation_size($1) - pg_relation_size($1)) as index_size
        """
        full_table_name = f'"{schema}"."{table_name}"'
        return await self.execute_single_query(sql, (full_table_name,))
    
    async def get_table_row_count(self, table_name: str, schema: str = 'public') -> int:
        """
        获取表的行数
        
        Args:
            table_name: 表名
            schema: 模式名称
            
        Returns:
            行数
        """
        sql = f'SELECT COUNT(*) FROM "{schema}"."{table_name}"'
        return await self.execute_scalar(sql)
    
    # ========== 数据查询功能 ==========
    
    async def select_all(self, table_name: str, schema: str = 'public', 
                        limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        查询表的所有数据
        
        Args:
            table_name: 表名
            schema: 模式名称
            limit: 限制返回行数
            
        Returns:
            查询结果
        """
        sql = f'SELECT * FROM "{schema}"."{table_name}"'
        if limit:
            sql += f' LIMIT {limit}'
        return await self.execute_query(sql)
    
    async def select_by_id(self, table_name: str, id_value: Any, 
                          id_column: str = 'id', schema: str = 'public') -> Optional[Dict[str, Any]]:
        """
        根据ID查询单条记录
        
        Args:
            table_name: 表名
            id_value: ID值
            id_column: ID列名
            schema: 模式名称
            
        Returns:
            查询结果或None
        """
        sql = f'SELECT * FROM "{schema}"."{table_name}" WHERE "{id_column}" = $1'
        return await self.execute_single_query(sql, (id_value,))
    
    async def select_by_condition(self, table_name: str, conditions: Dict[str, Any],
                                 schema: str = 'public', limit: Optional[int] = None,
                                 order_by: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        根据条件查询数据
        
        Args:
            table_name: 表名
            conditions: 查询条件字典
            schema: 模式名称
            limit: 限制返回行数
            order_by: 排序字段
            
        Returns:
            查询结果
        """
        if not conditions:
            return await self.select_all(table_name, schema, limit)
        
        where_clauses = []
        params = []
        param_index = 1
        
        for column, value in conditions.items():
            where_clauses.append(f'"{column}" = ${param_index}')
            params.append(value)
            param_index += 1
        
        sql = f'SELECT * FROM "{schema}"."{table_name}" WHERE {" AND ".join(where_clauses)}'
        
        if order_by:
            sql += f' ORDER BY "{order_by}"'
        
        if limit:
            sql += f' LIMIT {limit}'
        
        return await self.execute_query(sql, tuple(params))
    
    async def select_columns(self, table_name: str, columns: List[str],
                           schema: str = 'public', limit: Optional[int] = None,
                           conditions: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        查询指定列的数据
        
        Args:
            table_name: 表名
            columns: 要查询的列名列表
            schema: 模式名称
            limit: 限制返回行数
            conditions: 查询条件
            
        Returns:
            查询结果
        """
        columns_str = ', '.join(f'"{col}"' for col in columns)
        sql = f'SELECT {columns_str} FROM "{schema}"."{table_name}"'
        
        params = []
        if conditions:
            where_clauses = []
            param_index = 1
            
            for column, value in conditions.items():
                where_clauses.append(f'"{column}" = ${param_index}')
                params.append(value)
                param_index += 1
            
            sql += f' WHERE {" AND ".join(where_clauses)}'
        
        if limit:
            sql += f' LIMIT {limit}'
        
        return await self.execute_query(sql, tuple(params) if params else None)
    
    # ========== 聚合查询功能 ==========
    
    async def count_records(self, table_name: str, schema: str = 'public',
                           conditions: Optional[Dict[str, Any]] = None) -> int:
        """
        统计记录数
        
        Args:
            table_name: 表名
            schema: 模式名称
            conditions: 查询条件
            
        Returns:
            记录数
        """
        sql = f'SELECT COUNT(*) FROM "{schema}"."{table_name}"'
        
        params = []
        if conditions:
            where_clauses = []
            param_index = 1
            
            for column, value in conditions.items():
                where_clauses.append(f'"{column}" = ${param_index}')
                params.append(value)
                param_index += 1
            
            sql += f' WHERE {" AND ".join(where_clauses)}'
        
        return await self.execute_scalar(sql, tuple(params) if params else None)
    
    async def get_column_stats(self, table_name: str, column_name: str,
                              schema: str = 'public') -> Dict[str, Any]:
        """
        获取列的统计信息
        
        Args:
            table_name: 表名
            column_name: 列名
            schema: 模式名称
            
        Returns:
            列统计信息
        """
        sql = f"""
        SELECT 
            COUNT(*) as total_count,
            COUNT("{column_name}") as non_null_count,
            COUNT(*) - COUNT("{column_name}") as null_count,
            COUNT(DISTINCT "{column_name}") as distinct_count,
            MIN("{column_name}") as min_value,
            MAX("{column_name}") as max_value
        FROM "{schema}"."{table_name}"
        """
        
        stats = await self.execute_single_query(sql)
        
        # 尝试获取数值统计（如果是数值类型）
        try:
            numeric_sql = f"""
            SELECT 
                AVG("{column_name}"::numeric) as avg_value,
                STDDEV("{column_name}"::numeric) as stddev_value
            FROM "{schema}"."{table_name}"
            WHERE "{column_name}" IS NOT NULL
            """
            numeric_stats = await self.execute_single_query(numeric_sql)
            stats.update(numeric_stats)
        except:
            # 不是数值类型，跳过数值统计
            pass
        
        return stats
    
    async def group_by_analysis(self, table_name: str, group_column: str,
                               agg_column: Optional[str] = None, agg_func: str = 'COUNT',
                               schema: str = 'public', limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        分组聚合分析
        
        Args:
            table_name: 表名
            group_column: 分组列
            agg_column: 聚合列（如果不指定，对所有记录进行计数）
            agg_func: 聚合函数（COUNT, SUM, AVG, MIN, MAX）
            schema: 模式名称
            limit: 限制返回行数
            
        Returns:
            分组聚合结果
        """
        if agg_column:
            sql = f"""
            SELECT 
                "{group_column}",
                {agg_func}("{agg_column}") as {agg_func.lower()}_value
            FROM "{schema}"."{table_name}"
            GROUP BY "{group_column}"
            ORDER BY {agg_func.lower()}_value DESC
            """
        else:
            sql = f"""
            SELECT 
                "{group_column}",
                COUNT(*) as count_value
            FROM "{schema}"."{table_name}"
            GROUP BY "{group_column}"
            ORDER BY count_value DESC
            """
        
        if limit:
            sql += f' LIMIT {limit}'
        
        return await self.execute_query(sql)
    
    # ========== 搜索功能 ==========
    
    async def search_text(self, table_name: str, search_term: str,
                         search_columns: Optional[List[str]] = None,
                         schema: str = 'public', limit: Optional[int] = 100) -> List[Dict[str, Any]]:
        """
        在表中搜索文本
        
        Args:
            table_name: 表名
            search_term: 搜索关键词
            search_columns: 要搜索的列（如果不指定，搜索所有文本列）
            schema: 模式名称
            limit: 限制返回行数
            
        Returns:
            搜索结果
        """
        if not search_columns:
            # 获取所有文本类型的列
            columns_info = await self.get_table_columns(table_name, schema)
            search_columns = [
                col['column_name'] for col in columns_info
                if col['data_type'] in ['text', 'character varying', 'character', 'varchar']
            ]
        
        if not search_columns:
            return []
        
        # 构建搜索条件
        search_conditions = []
        for col in search_columns:
            search_conditions.append(f'"{col}"::text ILIKE $1')
        
        sql = f"""
        SELECT * FROM "{schema}"."{table_name}"
        WHERE {" OR ".join(search_conditions)}
        """
        
        if limit:
            sql += f' LIMIT {limit}'
        
        search_pattern = f'%{search_term}%'
        return await self.execute_query(sql, (search_pattern,))
    
    async def search_numeric_range(self, table_name: str, column_name: str,
                                  min_value: Optional[float] = None,
                                  max_value: Optional[float] = None,
                                  schema: str = 'public',
                                  limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        在数值范围内搜索
        
        Args:
            table_name: 表名
            column_name: 数值列名
            min_value: 最小值
            max_value: 最大值
            schema: 模式名称
            limit: 限制返回行数
            
        Returns:
            搜索结果
        """
        conditions = []
        params = []
        param_index = 1
        
        if min_value is not None:
            conditions.append(f'"{column_name}" >= ${param_index}')
            params.append(min_value)
            param_index += 1
        
        if max_value is not None:
            conditions.append(f'"{column_name}" <= ${param_index}')
            params.append(max_value)
            param_index += 1
        
        if not conditions:
            return await self.select_all(table_name, schema, limit)
        
        sql = f'SELECT * FROM "{schema}"."{table_name}" WHERE {" AND ".join(conditions)}'
        
        if limit:
            sql += f' LIMIT {limit}'
        
        return await self.execute_query(sql, tuple(params))
    
    # ========== 数据导出功能 ==========
    
    async def export_to_csv(self, table_name: str, file_path: str,
                           schema: str = 'public', conditions: Optional[Dict[str, Any]] = None,
                           columns: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        导出数据到CSV文件
        
        Args:
            table_name: 表名
            file_path: 输出文件路径
            schema: 模式名称
            conditions: 查询条件
            columns: 要导出的列
            
        Returns:
            导出结果信息
        """
        if columns:
            data = await self.select_columns(table_name, columns, schema, conditions=conditions)
        else:
            data = await self.select_by_condition(table_name, conditions or {}, schema)
        
        if not data:
            return {"status": "warning", "message": "没有数据可导出", "rows_exported": 0}
        
        # 转换为DataFrame并导出
        df = pd.DataFrame(data)
        df.to_csv(file_path, index=False, encoding='utf-8')
        
        return {
            "status": "success",
            "message": f"数据已导出到 {file_path}",
            "rows_exported": len(data),
            "file_path": file_path
        }
    
    async def export_to_json(self, table_name: str, file_path: str,
                            schema: str = 'public', conditions: Optional[Dict[str, Any]] = None,
                            columns: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        导出数据到JSON文件
        
        Args:
            table_name: 表名
            file_path: 输出文件路径
            schema: 模式名称
            conditions: 查询条件
            columns: 要导出的列
            
        Returns:
            导出结果信息
        """
        if columns:
            data = await self.select_columns(table_name, columns, schema, conditions=conditions)
        else:
            data = await self.select_by_condition(table_name, conditions or {}, schema)
        
        if not data:
            return {"status": "warning", "message": "没有数据可导出", "rows_exported": 0}
        
        # 处理日期时间类型
        def json_serializer(obj):
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=json_serializer)
        
        return {
            "status": "success",
            "message": f"数据已导出到 {file_path}",
            "rows_exported": len(data),
            "file_path": file_path
        }
    
    # ========== 数据质量检查 ==========
    
    async def check_data_quality(self, table_name: str, schema: str = 'public') -> Dict[str, Any]:
        """
        检查数据质量
        
        Args:
            table_name: 表名
            schema: 模式名称
            
        Returns:
            数据质量报告
        """
        columns_info = await self.get_table_columns(table_name, schema)
        total_rows = await self.get_table_row_count(table_name, schema)
        
        quality_report = {
            "table_name": table_name,
            "total_rows": total_rows,
            "columns_analysis": []
        }
        
        for col_info in columns_info:
            col_name = col_info['column_name']
            col_stats = await self.get_column_stats(table_name, col_name, schema)
            
            null_percentage = (col_stats['null_count'] / total_rows * 100) if total_rows > 0 else 0
            unique_percentage = (col_stats['distinct_count'] / col_stats['non_null_count'] * 100) if col_stats['non_null_count'] > 0 else 0
            
            col_analysis = {
                "column_name": col_name,
                "data_type": col_info['data_type'],
                "total_values": col_stats['total_count'],
                "non_null_values": col_stats['non_null_count'],
                "null_values": col_stats['null_count'],
                "null_percentage": round(null_percentage, 2),
                "distinct_values": col_stats['distinct_count'],
                "unique_percentage": round(unique_percentage, 2),
                "min_value": col_stats.get('min_value'),
                "max_value": col_stats.get('max_value'),
                "avg_value": col_stats.get('avg_value'),
                "stddev_value": col_stats.get('stddev_value')
            }
            
            quality_report["columns_analysis"].append(col_analysis)
        
        return quality_report
    
    async def find_duplicates(self, table_name: str, columns: List[str],
                             schema: str = 'public') -> List[Dict[str, Any]]:
        """
        查找重复记录
        
        Args:
            table_name: 表名
            columns: 用于判断重复的列
            schema: 模式名称
            
        Returns:
            重复记录
        """
        columns_str = ', '.join(f'"{col}"' for col in columns)
        
        sql = f"""
        SELECT {columns_str}, COUNT(*) as duplicate_count
        FROM "{schema}"."{table_name}"
        GROUP BY {columns_str}
        HAVING COUNT(*) > 1
        ORDER BY duplicate_count DESC
        """
        
        return await self.execute_query(sql)
    
    # ========== 实用工具方法 ==========
    
    async def get_database_info(self) -> Dict[str, Any]:
        """
        获取数据库基本信息
        
        Returns:
            数据库信息
        """
        info = {}
        
        # 数据库版本
        version_sql = "SELECT version()"
        info['version'] = await self.execute_scalar(version_sql)
        
        # 数据库大小
        size_sql = "SELECT pg_size_pretty(pg_database_size(current_database()))"
        info['database_size'] = await self.execute_scalar(size_sql)
        
        # 连接数
        connections_sql = "SELECT count(*) FROM pg_stat_activity"
        info['active_connections'] = await self.execute_scalar(connections_sql)
        
        # 表数量
        tables_count_sql = """
        SELECT count(*) FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        """
        info['tables_count'] = await self.execute_scalar(tables_count_sql)
        
        return info


def load_db_config():
    """从环境变量加载数据库配置"""
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "database": os.getenv("POSTGRES_DB", "postgres"),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", "")
    }


# ========== 使用示例和测试函数 ==========

async def example_usage():
    """使用示例"""
    # 加载数据库配置
    db_config = load_db_config()
    
    # 创建查询管理器
    query_manager = DatabaseQueryManager(db_config)
    
    try:
        # 初始化连接池
        await query_manager.init_connection_pool()
        
        # 获取数据库信息
        db_info = await query_manager.get_database_info()
        print("数据库信息:", db_info)
        
        # 列出所有表
        tables = await query_manager.list_tables()
        print("数据库表:", [table['table_name'] for table in tables])
        
        if tables:
            table_name = tables[0]['table_name']
            
            # 获取表信息
            table_info = await query_manager.get_table_info(table_name)
            print(f"表 {table_name} 信息:", table_info)
            
            # 查询前10条记录
            data = await query_manager.select_all(table_name, limit=10)
            print(f"前10条记录: {len(data)} 条")
            
            # 数据质量检查
            quality_report = await query_manager.check_data_quality(table_name)
            print("数据质量报告:", quality_report)
    
    except Exception as e:
        logger.error(f"示例执行失败: {e}")
    
    finally:
        # 关闭连接池
        await query_manager.close_connection_pool()


if __name__ == "__main__":
    # 加载环境变量
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        logger.warning("未安装python-dotenv，将使用系统环境变量")
    
    # 运行示例
    asyncio.run(example_usage())
