# 数据库查询工具使用说明

## 概述

这个工具包含两个主要模块：
1. `db_query_manager.py` - 数据库查询管理器类，提供各种查询功能
2. `db_query_tool.py` - 命令行工具，方便快速执行查询操作

## 功能特性

### 基本查询功能
- 查询表的所有数据或指定列
- 根据条件查询数据
- 根据ID查询单条记录
- 文本搜索和数值范围搜索

### 统计分析功能
- 统计记录数量
- 获取列的统计信息（最值、平均值、标准差等）
- 分组聚合分析
- 数据质量检查
- 查找重复记录

### 元数据查询
- 列出所有表
- 获取表的详细信息（列信息、大小、行数等）
- 获取数据库基本信息

### 数据导出功能
- 导出到CSV文件
- 导出到JSON文件
- 支持条件过滤和列选择

## 命令行工具使用示例

### 1. 基本信息查询

```bash
# 查看数据库信息
python db_query_tool.py --db-info

# 列出所有表
python db_query_tool.py --list-tables

# 查看指定表的详细信息
python db_query_tool.py --table-info employees
```

### 2. 数据查询

```bash
# 查询表的前10条记录
python db_query_tool.py --select employees --limit 10

# 查询指定列
python db_query_tool.py --select employees --columns "name,age,department" --limit 5

# 根据条件查询
python db_query_tool.py --select employees --where '{"department": "IT"}' --limit 20

# 文本搜索
python db_query_tool.py --search "employees,张三"

# 统计记录数
python db_query_tool.py --count employees
python db_query_tool.py --count employees --where '{"department": "IT"}'
```

### 3. 统计分析

```bash
# 获取列统计信息
python db_query_tool.py --stats "employees,age"

# 分组统计
python db_query_tool.py --group-by "employees,department" --limit 10
python db_query_tool.py --group-by "employees,department,salary,AVG" --limit 5

# 数据质量检查
python db_query_tool.py --quality-check employees

# 查找重复记录
python db_query_tool.py --find-duplicates "employees,name,email"
```

### 4. 数据导出

```bash
# 导出整个表到CSV
python db_query_tool.py --export-csv "employees,employees.csv"

# 导出指定列到JSON
python db_query_tool.py --export-json "employees,employees.json" --columns "name,age,department"

# 根据条件导出
python db_query_tool.py --export-csv "employees,it_employees.csv" --where '{"department": "IT"}'
```

### 5. 自定义SQL查询

```bash
# 执行自定义查询
python db_query_tool.py --sql "SELECT department, COUNT(*) FROM employees GROUP BY department"

# 执行更新操作
python db_query_tool.py --sql "UPDATE employees SET salary = salary * 1.1 WHERE department = 'IT'"
```

## 编程接口使用示例

### 基本使用

```python
import asyncio
from db_query_manager import DatabaseQueryManager, load_db_config

async def example():
    # 加载数据库配置
    db_config = load_db_config()
    
    # 创建查询管理器
    query_manager = DatabaseQueryManager(db_config)
    
    try:
        # 初始化连接池
        await query_manager.init_connection_pool()
        
        # 查询所有表
        tables = await query_manager.list_tables()
        print("所有表:", [t['table_name'] for t in tables])
        
        # 查询数据
        data = await query_manager.select_all("employees", limit=5)
        print("员工数据:", data)
        
        # 根据条件查询
        it_employees = await query_manager.select_by_condition(
            "employees", 
            {"department": "IT"}, 
            limit=10
        )
        print("IT部门员工:", len(it_employees))
        
        # 统计分析
        stats = await query_manager.get_column_stats("employees", "age")
        print("年龄统计:", stats)
        
        # 分组分析
        dept_stats = await query_manager.group_by_analysis(
            "employees", 
            "department", 
            "salary", 
            "AVG"
        )
        print("各部门平均薪资:", dept_stats)
        
        # 数据质量检查
        quality = await query_manager.check_data_quality("employees")
        print("数据质量报告:", quality)
        
        # 导出数据
        result = await query_manager.export_to_csv(
            "employees", 
            "output/employees.csv",
            conditions={"department": "IT"}
        )
        print("导出结果:", result)
        
    finally:
        await query_manager.close_connection_pool()

# 运行示例
asyncio.run(example())
```

### 高级查询示例

```python
async def advanced_queries(query_manager):
    # 文本搜索
    search_results = await query_manager.search_text(
        "employees", 
        "张", 
        search_columns=["name", "email"]
    )
    
    # 数值范围搜索
    age_range = await query_manager.search_numeric_range(
        "employees", 
        "age", 
        min_value=25, 
        max_value=35
    )
    
    # 查找重复记录
    duplicates = await query_manager.find_duplicates(
        "employees", 
        ["name", "email"]
    )
    
    # 自定义查询
    custom_result = await query_manager.execute_query(
        "SELECT department, AVG(salary) as avg_salary FROM employees GROUP BY department"
    )
    
    return {
        "search_results": search_results,
        "age_range": age_range,
        "duplicates": duplicates,
        "custom_result": custom_result
    }
```

## 环境配置

确保设置以下环境变量或在 `.env` 文件中配置：

```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=your_database
POSTGRES_USER=your_username
POSTGRES_PASSWORD=your_password
```

## 依赖包

确保安装以下Python包：

```bash
pip install asyncpg pandas python-dotenv
```

## 注意事项

1. **连接池管理**: 所有操作都使用连接池，记得在使用完毕后关闭连接池
2. **大数据处理**: 对于大表查询，建议使用 `limit` 参数限制返回结果
3. **SQL注入防护**: 所有查询都使用参数化查询，防止SQL注入
4. **错误处理**: 所有方法都有适当的错误处理和日志记录
5. **性能优化**: 查询结果会自动转换为字典格式，便于使用

## 扩展功能

可以根据需要扩展以下功能：
- 添加更多聚合函数支持
- 实现数据可视化接口
- 添加数据备份和恢复功能
- 集成更多数据格式的导出
- 实现查询结果缓存
