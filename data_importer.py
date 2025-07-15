#!/usr/bin/env python3
"""
数据导入工具 - 支持JSON和CSV文件导入到PostgreSQL数据库
#### 导入JSON文件
```bash
python data_importer.py data/sample.json -t my_table -d
```--de

#### 导入CSV文件
```bash
python data_importer.py data/sample.csv -t my_table -d --delimiter "," --encoding utf-8
```
"""

import asyncio
import asyncpg
import json
import csv
import os
import logging
from typing import Dict, Any, List, Optional, Union, Iterator
from pathlib import Path
import pandas as pd
from datetime import datetime, date
import argparse
import gc
import ijson  # 新增：用于流式JSON解析

# 配置日志
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DataImporter:
    """数据导入器类"""
    
    def __init__(self, db_config: Dict[str, Any]):
        """
        初始化数据导入器
        
        Args:
            db_config: 数据库配置字典
        """
        self.db_config = db_config
        self.connection_pool: Optional[asyncpg.Pool] = None
        self.column_types_mapping: Dict[str, str] = {}
        self.large_file_threshold = 1024 * 1024 * 1024  # 1GB (仅用于CSV)
        self.json_max_size = 10 * 1024 * 1024 * 1024  # 10GB (JSON文件最大限制)
        self.chunk_size = 10000  # 大文件处理时的块大小
    
    def get_file_size(self, file_path: str) -> int:
        """获取文件大小（字节）"""
        return os.path.getsize(file_path)
    
    def is_large_file(self, file_path: str) -> bool:
        """判断是否为大文件（仅用于CSV）"""
        return self.get_file_size(file_path) > self.large_file_threshold
    
    def is_json_too_large(self, file_path: str) -> bool:
        """判断JSON文件是否超过限制大小"""
        return self.get_file_size(file_path) > self.json_max_size
    
    def stream_json_objects(self, file_path: str) -> Iterator[Dict[str, Any]]:
        """
        流式读取JSON文件中的对象
        
        Args:
            file_path: JSON文件路径
            
        Yields:
            JSON对象
        """
        with open(file_path, 'rb') as file:
            # 尝试解析数组格式的JSON
            try:
                parser = ijson.items(file, 'item')
                for obj in parser:
                    yield obj
            except ijson.JSONError:
                # 如果不是数组格式，尝试解析单个对象
                file.seek(0)
                try:
                    parser = ijson.items(file, '')
                    for obj in parser:
                        yield obj
                except ijson.JSONError:
                    # 最后尝试逐行解析
                    file.seek(0)
                    for line_num, line in enumerate(file, 1):
                        line = line.decode('utf-8').strip()
                        if line:
                            try:
                                yield json.loads(line)
                            except json.JSONDecodeError as e:
                                logger.warning(f"跳过第{line_num}行，JSON解析错误: {e}")
    
    def stream_csv_chunks(self, file_path: str, delimiter: str = ',', 
                         encoding: str = 'utf-8', chunk_size: int = None) -> Iterator[List[Dict[str, Any]]]:
        """
        流式读取CSV文件并返回数据块
        
        Args:
            file_path: CSV文件路径
            delimiter: 分隔符
            encoding: 编码
            chunk_size: 每个块的行数
            
        Yields:
            数据块（字典列表）
        """
        if chunk_size is None:
            chunk_size = self.chunk_size
        
        # 尝试不同的CSV解析参数
        csv_params_list = [
            # 标准参数
            {
                'delimiter': delimiter,
                'encoding': encoding,
                'chunksize': chunk_size,
                'na_filter': False,
                'quoting': 1,  # QUOTE_ALL
                'on_bad_lines': 'skip'  # 跳过坏行
            },
            # 更宽松的参数
            {
                'delimiter': delimiter,
                'encoding': encoding,
                'chunksize': chunk_size,
                'na_filter': False,
                'quoting': 3,  # QUOTE_NONE
                'on_bad_lines': 'skip',
                'error_bad_lines': False,
                'warn_bad_lines': True
            },
            # 最宽松的参数
            {
                'delimiter': delimiter,
                'encoding': encoding,
                'chunksize': chunk_size,
                'na_filter': False,
                'quoting': 3,  # QUOTE_NONE
                'on_bad_lines': 'skip',
                'engine': 'python',  # 使用Python引擎，更宽松
                'skipinitialspace': True
            }
        ]
        
        # 尝试不同编码
        encodings_to_try = [encoding, 'utf-8', 'gbk', 'gb2312', 'latin-1', 'cp1252']
        
        for enc in encodings_to_try:
            for params in csv_params_list:
                try:
                    params['encoding'] = enc
                    logger.info(f"尝试使用编码 {enc} 和解析参数: quoting={params.get('quoting')}, engine={params.get('engine', 'c')}")
                    
                    chunk_reader = pd.read_csv(file_path, **params)
                    
                    logger.info(f"成功使用编码 {enc} 读取文件")
                    
                    for chunk_df in chunk_reader:
                        # 清理列名中的特殊字符
                        chunk_df.columns = [str(col).strip() for col in chunk_df.columns]
                        # 将DataFrame转换为字典列表
                        chunk_data = chunk_df.to_dict('records')
                        yield chunk_data
                    return  # 成功读取，退出
                    
                except Exception as e:
                    logger.warning(f"编码 {enc} 参数组合失败: {e}")
                    continue
        
        # 如果所有方法都失败，尝试手动逐行解析
        logger.warning("标准pandas解析失败，尝试手动逐行解析")
        try:
            yield from self._manual_csv_parse(file_path, delimiter, chunk_size)
        except Exception as e:
            raise ValueError(f"无法解析CSV文件，所有方法都失败: {e}")
    
    def _manual_csv_parse(self, file_path: str, delimiter: str = ',', chunk_size: int = 10000) -> Iterator[List[Dict[str, Any]]]:
        """
        手动逐行解析CSV文件（处理格式不规范的情况）
        
        Args:
            file_path: CSV文件路径
            delimiter: 分隔符
            chunk_size: 每个块的行数
            
        Yields:
            数据块（字典列表）
        """
        import csv
        from io import StringIO
        
        # 尝试不同编码
        for encoding in ['utf-8', 'gbk', 'gb2312', 'latin-1', 'cp1252']:
            try:
                with open(file_path, 'r', encoding=encoding, errors='ignore') as file:
                    logger.info(f"手动解析使用编码: {encoding}")
                    
                    # 读取第一行作为头部
                    first_line = file.readline().strip()
                    if not first_line:
                        continue
                    
                    # 解析头部
                    headers = [col.strip().strip('"').strip("'") for col in first_line.split(delimiter)]
                    num_columns = len(headers)
                    logger.info(f"检测到 {num_columns} 列: {headers[:5]}...")  # 只显示前5列
                    
                    chunk_data = []
                    line_num = 1
                    
                    for line in file:
                        line_num += 1
                        line = line.strip()
                        if not line:
                            continue
                        
                        try:
                            # 分割行
                            values = line.split(delimiter)
                            
                            # 处理字段数量不匹配的情况
                            if len(values) != num_columns:
                                # 如果字段太多，截断
                                if len(values) > num_columns:
                                    values = values[:num_columns]
                                    logger.debug(f"第{line_num}行字段过多，已截断")
                                # 如果字段太少，补充空值
                                else:
                                    values.extend([''] * (num_columns - len(values)))
                                    logger.debug(f"第{line_num}行字段不足，已补充空值")
                            
                            # 清理值
                            cleaned_values = []
                            for val in values:
                                val = val.strip().strip('"').strip("'")
                                cleaned_values.append(val if val else None)
                            
                            # 创建行字典
                            row_dict = dict(zip(headers, cleaned_values))
                            chunk_data.append(row_dict)
                            
                            # 当达到块大小时返回数据
                            if len(chunk_data) >= chunk_size:
                                yield chunk_data
                                chunk_data = []
                                
                        except Exception as e:
                            logger.warning(f"跳过第{line_num}行，解析错误: {e}")
                            continue
                    
                    # 返回最后的数据块
                    if chunk_data:
                        yield chunk_data
                    
                    logger.info(f"手动解析完成，共处理 {line_num} 行")
                    return  # 成功解析，退出
                    
            except Exception as e:
                logger.warning(f"编码 {encoding} 手动解析失败: {e}")
                continue
        
        raise ValueError("手动解析也失败了")

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
    
    def infer_column_type_from_sample(self, sample_data: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        从样本数据推断列类型
        
        Args:
            sample_data: 样本数据列表
            
        Returns:
            列类型映射
        """
        if not sample_data:
            return {}
        
        # 获取所有列名
        all_columns = set()
        for row in sample_data:
            all_columns.update(row.keys())
        
        # 分析每列的数据类型
        column_types = {}
        for col in all_columns:
            values = [row.get(col) for row in sample_data]
            column_types[col] = self.infer_column_type(values)
        
        return column_types

    def infer_column_type(self, values: List[Any]) -> str:
        """
        根据数据值推断列类型
        
        Args:
            values: 列的值列表
            
        Returns:
            PostgreSQL列类型
        """
        # 过滤掉None值
        non_null_values = [v for v in values if v is not None and str(v).strip() != '']
        
        if not non_null_values:
            return "TEXT"
        
        # 检查是否为整数
        try:
            int_values = []
            for val in non_null_values:
                int_val = int(val)
                int_values.append(int_val)
            
            # 检查是否在PostgreSQL INTEGER范围内 (-2,147,483,648 到 2,147,483,647)
            min_int32 = -2147483648
            max_int32 = 2147483647
            
            if all(min_int32 <= val <= max_int32 for val in int_values):
                return "INTEGER"
            else:
                # 超出int32范围，检查是否在bigint范围内
                min_int64 = -9223372036854775808
                max_int64 = 9223372036854775807
                if all(min_int64 <= val <= max_int64 for val in int_values):
                    return "BIGINT"
                else:
                    # 超出bigint范围，使用文本类型
                    return "TEXT"
        except (ValueError, TypeError):
            pass
        
        # 检查是否为浮点数
        try:
            for val in non_null_values:
                float(val)
            return "NUMERIC"
        except (ValueError, TypeError):
            pass
        
        # 检查是否为布尔值
        bool_values = {'true', 'false', '1', '0', 'yes', 'no', 't', 'f'}
        if all(str(val).lower() in bool_values for val in non_null_values):
            return "BOOLEAN"
        
        # 检查是否为日期时间
        for val in non_null_values[:5]:  # 只检查前5个值
            try:
                pd.to_datetime(str(val))
                return "TIMESTAMP"
            except:
                continue
        
        # 检查字符串长度
        max_length = max(len(str(val)) for val in non_null_values)
        if max_length <= 255:
            return f"VARCHAR({max_length + 50})"  # 留一些余量
        else:
            return "TEXT"
    
    def sanitize_column_name(self, name: str) -> str:
        """
        清理列名，使其符合PostgreSQL规范
        
        Args:
            name: 原始列名
            
        Returns:
            清理后的列名
        """
        # 替换特殊字符为下划线
        import re
        name = re.sub(r'[^a-zA-Z0-9_]', '_', str(name))
        # 确保以字母或下划线开头
        if name and name[0].isdigit():
            name = f"col_{name}"
        # 转换为小写
        name = name.lower()
        # 处理空字符串
        if not name:
            name = "unnamed_column"
        return name
    
    def convert_value_by_type(self, value: Any, column_type: str) -> Any:
        """
        根据列类型转换值
        
        Args:
            value: 原始值
            column_type: PostgreSQL列类型
            
        Returns:
            转换后的值
        """
        if value is None or str(value).strip() == '':
            return None
        
        try:
            if column_type == "INTEGER":
                return int(value)
            elif column_type == "BIGINT":
                return int(value)
            elif column_type == "NUMERIC":
                return float(value)
            elif column_type == "BOOLEAN":
                str_val = str(value).lower()
                return str_val in {'true', '1', 'yes', 't'}
            elif column_type == "TIMESTAMP":
                if isinstance(value, (datetime, date)):
                    return value
                # 尝试解析字符串为datetime
                return pd.to_datetime(str(value)).to_pydatetime()
            else:
                # VARCHAR, TEXT等字符串类型
                return str(value)
        except Exception as e:
            logger.warning(f"值转换失败 {value} -> {column_type}: {e}")
            return None
    
    async def create_table_from_sample(self, table_name: str, sample_data: List[Dict[str, Any]], 
                                     drop_if_exists: bool = False) -> tuple:
        """
        根据样本数据创建表
        
        Args:
            table_name: 表名
            sample_data: 样本数据
            drop_if_exists: 是否删除已存在的表
            
        Returns:
            (CREATE TABLE语句, 列映射)
        """
        if not sample_data:
            raise ValueError("样本数据为空，无法创建表")
        
        # 获取所有列名
        all_columns = set()
        for row in sample_data:
            all_columns.update(row.keys())
        
        # 清理列名
        column_mapping = {}
        for col in all_columns:
            clean_col = self.sanitize_column_name(col)
            column_mapping[col] = clean_col
        
        # 分析每列的数据类型
        column_types = {}
        for original_col, clean_col in column_mapping.items():
            values = [row.get(original_col) for row in sample_data]
            column_types[clean_col] = self.infer_column_type(values)
        
        # 保存列类型映射
        self.column_types_mapping = column_types
        
        # 构建CREATE TABLE语句
        columns_def = []
        for clean_col, col_type in column_types.items():
            columns_def.append(f'"{clean_col}" {col_type}')
        
        create_sql = f'CREATE TABLE "{table_name}" (\n'
        create_sql += ',\n'.join(f'    {col_def}' for col_def in columns_def)
        create_sql += '\n);'
        
        # 执行创建表语句
        async with self.connection_pool.acquire() as conn:
            if drop_if_exists:
                await conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
                logger.info(f"已删除表 {table_name}（如果存在）")
            
            await conn.execute(create_sql)
            logger.info(f"表 {table_name} 创建成功")
        
        return create_sql, column_mapping

    async def create_table_from_data(self, table_name: str, data: List[Dict[str, Any]], 
                                   drop_if_exists: bool = False) -> str:
        """
        根据数据自动创建表
        
        Args:
            table_name: 表名
            data: 数据列表
            drop_if_exists: 是否删除已存在的表
            
        Returns:
            CREATE TABLE语句
        """
        return await self.create_table_from_sample(table_name, data, drop_if_exists)
    
    async def import_csv_file_large(self, file_path: str, table_name: str, 
                                  drop_if_exists: bool = False, batch_size: int = 1000,
                                  delimiter: str = ',', encoding: str = 'utf-8') -> Dict[str, Any]:
        """
        导入大型CSV文件到PostgreSQL（分块处理）
        
        Args:
            file_path: CSV文件路径
            table_name: 目标表名
            drop_if_exists: 是否删除已存在的表
            batch_size: 批量插入大小
            delimiter: CSV分隔符
            encoding: 文件编码
            
        Returns:
            导入结果统计
        """
        logger.info(f"开始分块导入大型CSV文件: {file_path}")
        
        # 读取第一个块用于创建表结构
        first_chunk = None
        chunk_count = 0
        try:
            for chunk in self.stream_csv_chunks(file_path, delimiter, encoding, 1000):
                first_chunk = chunk
                chunk_count += 1
                logger.info(f"成功读取第一个数据块，包含 {len(chunk)} 行")
                break
        except Exception as e:
            logger.error(f"读取第一个数据块失败: {e}")
            raise ValueError(f"无法读取CSV文件第一个块: {e}")
        
        if not first_chunk:
            raise ValueError("CSV文件为空或无法解析")
        
        # 显示数据样本
        logger.info(f"数据样本 - 列数: {len(first_chunk[0]) if first_chunk else 0}")
        if first_chunk:
            sample_row = first_chunk[0]
            logger.info(f"列名样本: {list(sample_row.keys())[:10]}...")  # 显示前10列
        
        # 根据第一个块创建表
        try:
            create_sql, column_mapping = await self.create_table_from_sample(
                table_name, first_chunk, drop_if_exists
            )
        except Exception as e:
            logger.error(f"创建表失败: {e}")
            raise
        
        # 分块处理并插入数据
        total_rows = 0
        inserted_rows = 0
        
        async with self.connection_pool.acquire() as conn:
            # 准备插入语句
            clean_columns = list(column_mapping.values())
            placeholders = ', '.join(f'${i+1}' for i in range(len(clean_columns)))
            columns_str = ', '.join(f'"{col}"' for col in clean_columns)
            insert_sql = f'INSERT INTO "{table_name}" ({columns_str}) VALUES ({placeholders})'
            
            # 重新开始分块读取所有数据
            for chunk_data in self.stream_csv_chunks(file_path, delimiter, encoding, self.chunk_size):
                chunk_size = len(chunk_data)
                total_rows += chunk_size
                
                # 分批处理当前块
                for i in range(0, chunk_size, batch_size):
                    batch = chunk_data[i:i + batch_size]
                    batch_values = []
                    
                    for row in batch:
                        row_values = []
                        for original_col in column_mapping.keys():
                            clean_col = column_mapping[original_col]
                            value = row.get(original_col)
                            column_type = self.column_types_mapping.get(clean_col, "TEXT")
                            
                            # 处理空值并根据列类型转换
                            if value == '' or pd.isna(value):
                                converted_value = None
                            else:
                                converted_value = self.convert_value_by_type(value, column_type)
                            row_values.append(converted_value)
                        batch_values.append(tuple(row_values))
                    
                    # 执行批量插入
                    await conn.executemany(insert_sql, batch_values)
                    inserted_rows += len(batch)
                
                logger.info(f"已处理 {total_rows} 行，已插入 {inserted_rows} 行")
                gc.collect()  # 手动垃圾回收
        
        result = {
            "file_path": file_path,
            "table_name": table_name,
            "total_rows": total_rows,
            "inserted_rows": inserted_rows,
            "create_sql": create_sql,
            "column_mapping": column_mapping,
            "delimiter": delimiter,
            "encoding": encoding,
            "processing_mode": "large_file_chunked",
            "status": "success"
        }
        
        logger.info(f"大型CSV文件导入完成: {inserted_rows} 行数据")
        return result

    async def import_json_file(self, file_path: str, table_name: str, 
                             drop_if_exists: bool = False, batch_size: int = 1000) -> Dict[str, Any]:
        """
        导入JSON文件到PostgreSQL
        
        Args:
            file_path: JSON文件路径
            table_name: 目标表名
            drop_if_exists: 是否删除已存在的表
            batch_size: 批量插入大小
            
        Returns:
            导入结果统计
        """
        # 检查JSON文件是否超过10GB限制
        if self.is_json_too_large(file_path):
            file_size_gb = self.get_file_size(file_path) / (1024**3)
            raise ValueError(f"JSON文件过大 ({file_size_gb:.2f}GB)，超过10GB限制。JSON文件不支持流式处理，请使用较小的文件。")
        
        # 所有JSON文件都使用完整导入（不分流式处理）
        logger.info(f"开始导入JSON文件: {file_path}")
        
        # 读取JSON文件
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 确保数据是列表格式
        if isinstance(data, dict):
            data = [data]
        elif not isinstance(data, list):
            raise ValueError("JSON文件必须包含对象或对象数组")
        
        if not data:
            raise ValueError("JSON文件为空")
        
        # 创建表
        create_sql, column_mapping = await self.create_table_from_data(
            table_name, data, drop_if_exists
        )
        
        # 批量插入数据
        total_rows = len(data)
        inserted_rows = 0
        
        async with self.connection_pool.acquire() as conn:
            # 准备插入语句
            clean_columns = list(column_mapping.values())
            placeholders = ', '.join(f'${i+1}' for i in range(len(clean_columns)))
            columns_str = ', '.join(f'"{col}"' for col in clean_columns)
            insert_sql = f'INSERT INTO "{table_name}" ({columns_str}) VALUES ({placeholders})'
            
            # 分批插入
            for i in range(0, total_rows, batch_size):
                batch = data[i:i + batch_size]
                batch_values = []
                
                for row in batch:
                    row_values = []
                    for original_col in column_mapping.keys():
                        clean_col = column_mapping[original_col]
                        value = row.get(original_col)
                        column_type = self.column_types_mapping.get(clean_col, "TEXT")
                        
                        # 根据列类型转换值
                        converted_value = self.convert_value_by_type(value, column_type)
                        row_values.append(converted_value)
                    batch_values.append(tuple(row_values))
                
                # 执行批量插入
                await conn.executemany(insert_sql, batch_values)
                inserted_rows += len(batch)
                logger.info(f"已插入 {inserted_rows}/{total_rows} 行")
        
        result = {
            "file_path": file_path,
            "table_name": table_name,
            "total_rows": total_rows,
            "inserted_rows": inserted_rows,
            "create_sql": create_sql,
            "column_mapping": column_mapping,
            "processing_mode": "complete_load",
            "status": "success"
        }
        
        logger.info(f"JSON文件导入完成: {inserted_rows} 行数据")
        return result
    
    async def import_csv_file(self, file_path: str, table_name: str, 
                            drop_if_exists: bool = False, batch_size: int = 1000,
                            delimiter: str = ',', encoding: str = 'utf-8') -> Dict[str, Any]:
        """
        导入CSV文件到PostgreSQL
        
        Args:
            file_path: CSV文件路径
            table_name: 目标表名
            drop_if_exists: 是否删除已存在的表
            batch_size: 批量插入大小
            delimiter: CSV分隔符
            encoding: 文件编码
            
        Returns:
            导入结果统计
        """
        # 检查是否为大文件（仅对CSV文件进行分块处理）
        if self.is_large_file(file_path):
            logger.info(f"检测到大文件 ({self.get_file_size(file_path) / (1024**3):.2f}GB)，使用分块处理")
            return await self.import_csv_file_large(file_path, table_name, drop_if_exists, 
                                                  batch_size, delimiter, encoding)
        
        # 原有的小文件处理逻辑
        logger.info(f"开始导入CSV文件: {file_path}")
        
        # 使用更宽松的参数读取CSV
        df = None
        for params in [
            {'delimiter': delimiter, 'encoding': encoding, 'on_bad_lines': 'skip'},
            {'delimiter': delimiter, 'encoding': encoding, 'quoting': 3, 'on_bad_lines': 'skip', 'engine': 'python'},
        ]:
            try:
                df = pd.read_csv(file_path, **params)
                logger.info("成功读取CSV文件")
                break
            except Exception as e:
                logger.warning(f"CSV读取参数失败: {e}")
                continue
        
        if df is None:
            # 尝试其他编码
            for enc in ['gbk', 'gb2312', 'latin-1', 'cp1252']:
                try:
                    df = pd.read_csv(file_path, delimiter=delimiter, encoding=enc, 
                                   on_bad_lines='skip', engine='python')
                    logger.info(f"使用编码 {enc} 成功读取文件")
                    break
                except:
                    continue
            
            if df is None:
                raise ValueError("无法解析CSV文件，请检查文件格式")
        
        # 将DataFrame转换为字典列表
        data = df.to_dict('records')
        
        # 创建表
        create_sql, column_mapping = await self.create_table_from_data(
            table_name, data, drop_if_exists
        )
        
        # 批量插入数据
        total_rows = len(data)
        inserted_rows = 0
        
        async with self.connection_pool.acquire() as conn:
            # 准备插入语句
            clean_columns = list(column_mapping.values())
            placeholders = ', '.join(f'${i+1}' for i in range(len(clean_columns)))
            columns_str = ', '.join(f'"{col}"' for col in clean_columns)
            insert_sql = f'INSERT INTO "{table_name}" ({columns_str}) VALUES ({placeholders})'
            
            # 分批插入
            for i in range(0, total_rows, batch_size):
                batch = data[i:i + batch_size]
                batch_values = []
                
                for row in batch:
                    row_values = []
                    for original_col in column_mapping.keys():
                        clean_col = column_mapping[original_col]
                        value = row.get(original_col)
                        column_type = self.column_types_mapping.get(clean_col, "TEXT")
                        
                        # 处理pandas的NaN值并根据列类型转换
                        if pd.isna(value):
                            converted_value = None
                        else:
                            converted_value = self.convert_value_by_type(value, column_type)
                        row_values.append(converted_value)
                    batch_values.append(tuple(row_values))
                
                # 执行批量插入
                await conn.executemany(insert_sql, batch_values)
                inserted_rows += len(batch)
                logger.info(f"已插入 {inserted_rows}/{total_rows} 行")
        
        result = {
            "file_path": file_path,
            "table_name": table_name,
            "total_rows": total_rows,
            "inserted_rows": inserted_rows,
            "create_sql": create_sql,
            "column_mapping": column_mapping,
            "delimiter": delimiter,
            "encoding": encoding,
            "status": "success"
        }
        
        logger.info(f"CSV文件导入完成: {inserted_rows} 行数据")
        return result
    
    async def import_file(self, file_path: str, table_name: Optional[str] = None, 
                         drop_if_exists: bool = False, **kwargs) -> Dict[str, Any]:
        """
        根据文件扩展名自动选择导入方法
        
        Args:
            file_path: 文件路径
            table_name: 目标表名（如果不指定，使用文件名）
            drop_if_exists: 是否删除已存在的表
            **kwargs: 其他参数
            
        Returns:
            导入结果统计
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        # 如果未指定表名，使用文件名（去掉扩展名）
        if table_name is None:
            table_name = file_path.stem
        
        # 清理表名
        table_name = self.sanitize_column_name(table_name)
        
        # 根据文件扩展名选择导入方法
        extension = file_path.suffix.lower()
        
        if extension == '.json':
            # JSON文件只需要batch_size参数
            json_kwargs = {
                'batch_size': kwargs.get('batch_size', 1000)
            }
            return await self.import_json_file(str(file_path), table_name, drop_if_exists, **json_kwargs)
        elif extension == '.csv':
            # CSV文件需要delimiter和encoding参数
            csv_kwargs = {
                'batch_size': kwargs.get('batch_size', 1000),
                'delimiter': kwargs.get('delimiter', ','),
                'encoding': kwargs.get('encoding', 'utf-8')
            }
            return await self.import_csv_file(str(file_path), table_name, drop_if_exists, **csv_kwargs)
        else:
            raise ValueError(f"不支持的文件格式: {extension}")

def load_db_config():
    """从环境变量加载数据库配置"""
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "database": os.getenv("POSTGRES_DB", "postgres"),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", "")
    }

async def main():
    """主函数 - 命令行接口"""
    parser = argparse.ArgumentParser(description="数据导入工具 - 支持JSON和CSV导入到PostgreSQL")
    parser.add_argument("file_path", help="要导入的文件路径")
    parser.add_argument("-t", "--table", help="目标表名（默认使用文件名）")
    parser.add_argument("-d", "--drop", action="store_true", help="删除已存在的表")
    parser.add_argument("-b", "--batch-size", type=int, default=1000, help="批量插入大小")
    parser.add_argument("--delimiter", default=",", help="CSV分隔符（默认为逗号）")
    parser.add_argument("--encoding", default="utf-8", help="文件编码（默认为utf-8）")
    parser.add_argument("--chunk-size", type=int, default=10000, help="大文件处理时的块大小")
    parser.add_argument("--force-manual", action="store_true", help="强制使用手动解析模式")
    
    args = parser.parse_args()
    
    # 加载数据库配置
    db_config = load_db_config()
    
    # 创建导入器
    importer = DataImporter(db_config)
    if args.chunk_size:
        importer.chunk_size = args.chunk_size
    
    try:
        # 检查文件大小并显示信息
        file_size_gb = importer.get_file_size(args.file_path) / (1024**3)
        file_extension = Path(args.file_path).suffix.lower()
        
        if file_extension == '.json':
            if file_size_gb > 10:
                print(f"错误: JSON文件过大 ({file_size_gb:.2f}GB)，超过10GB限制")
                return 1
            elif file_size_gb > 1:
                print(f"注意: JSON文件较大 ({file_size_gb:.2f}GB)，将完整加载到内存")
        elif file_extension == '.csv' and file_size_gb > 1:
            print(f"检测到大文件: {file_size_gb:.2f}GB，将使用优化的流式处理")
        
        # 初始化连接池
        await importer.init_connection_pool()
        
        # 根据文件类型准备参数
        import_kwargs = {
            'batch_size': args.batch_size
        }
        
        # 只有CSV文件才添加delimiter和encoding参数
        file_extension = Path(args.file_path).suffix.lower()
        if file_extension == '.csv':
            import_kwargs['delimiter'] = args.delimiter
            import_kwargs['encoding'] = args.encoding
        
        # 执行导入
        result = await importer.import_file(
            args.file_path,
            args.table,
            args.drop,
            **import_kwargs
        )
        
        # 打印结果
        print("\n导入完成！")
        print(f"文件: {result['file_path']}")
        print(f"表名: {result['table_name']}")
        print(f"导入行数: {result['inserted_rows']}")
        print(f"处理模式: {result.get('processing_mode', 'normal')}")
        print(f"状态: {result['status']}")
        
        if 'column_mapping' in result:
            print("\n列映射:")
            for original, clean in result['column_mapping'].items():
                print(f"  {original} -> {clean}")
    
    except Exception as e:
        logger.error(f"导入失败: {e}")
        print(f"\n错误: {e}")
        return 1
    
    finally:
        # 关闭连接池
        await importer.close_connection_pool()
    
    return 0

if __name__ == "__main__":
    import sys
    try:
        # 加载环境变量
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        logger.warning("未安装python-dotenv，将使用系统环境变量")
    
    sys.exit(asyncio.run(main()))
