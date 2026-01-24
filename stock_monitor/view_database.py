#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库查看工具
用于查看 stock_cache.db 数据库的内容
"""

import sqlite3
import json
import os
from datetime import datetime
import sys


def connect_database(db_path):
    """连接到数据库"""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # 使结果可以通过列名访问
        return conn
    except Exception as e:
        print(f"连接数据库失败: {e}")
        return None


def get_table_info(conn):
    """获取数据库表信息"""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    return [table[0] for table in tables]


def get_table_count(conn, table_name):
    """获取表的记录数"""
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    return count


def get_table_schema(conn, table_name):
    """获取表结构"""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    return columns


def display_table_data(conn, table_name, limit=10):
    """显示表数据"""
    cursor = conn.cursor()
    
    # 尝试获取所有记录，限制数量以避免输出过多
    # 首先检查表结构，判断是否包含cache_time列
    schema = get_table_schema(conn, table_name)
    column_names = [col[1] for col in schema]  # 获取列名列表

    # 如果表包含cache_time列，则按此列排序，否则按第一列排序
    if 'cache_time' in column_names:
        cursor.execute(f"SELECT * FROM {table_name} ORDER BY cache_time DESC LIMIT {limit}")
    else:
        # 如果没有cache_time列，按第一列排序（如果存在的话）
        if column_names:
            cursor.execute(f"SELECT * FROM {table_name} ORDER BY {column_names[0]} DESC LIMIT {limit}")
        else:
            cursor.execute(f"SELECT * FROM {table_name} LIMIT {limit}")
    
    rows = cursor.fetchall()
    
    print(f"\n表 {table_name} 的内容 (最多显示 {limit} 条记录):")
    print("-" * 100)
    
    if not rows:
        print("表中没有数据")
        return
    
    # 获取列名
    header_names = [description[0] for description in cursor.description]
    header = " | ".join([f"{col_name[:15]:<15}" for col_name in header_names])  # 限制列名长度
    print(header)
    print("-" * 100)
    
    for row in rows:
        values = []
        for i, col_name in enumerate(header_names):
            value = row[i]
            
            # 如果是数据列，尝试格式化JSON
            if col_name == 'data':
                try:
                    data_obj = json.loads(value)
                    # 如果数据是字典，提取关键信息
                    if isinstance(data_obj, dict):
                        # 只显示部分关键字段
                        if 'price' in data_obj or 'change_pct' in data_obj or 'name' in data_obj:
                            formatted_data = []
                            for key, val in list(data_obj.items())[:3]:  # 只显示前3个键值对
                                key_str = str(key)[:8] # 限制键名长度
                                val_str = str(val)[:20] # 限制值长度
                                formatted_data.append(f"{key_str}:{val_str}")
                            value = "{" + ", ".join(formatted_data) + "}"
                        else:
                            value = f"JSON({len(str(data_obj))} chars)"
                    else:
                        value = str(data_obj)
                except json.JSONDecodeError:
                    value = f"JSON格式错误: {str(value)[:30]}..."
                except Exception as e:
                    value = f"解析错误: {str(e)[:30]}"
            
            # 如果是时间列，格式化时间
            elif col_name == 'cache_time':
                try:
                    # 处理不同的时间格式
                    value = value.replace('Z', '+00:00')  # 替换Z后缀
                    if '+' in value or value.count('-') > 2:  # 包含时区信息
                        cache_time = datetime.fromisoformat(value)
                    else:
                        cache_time = datetime.fromisoformat(value)
                    value = cache_time.strftime('%Y-%m-%d %H:%M:%S')
                except ValueError:
                    pass # 保持原始值
            
            # 限制值的长度以避免输出过长
            str_value = str(value)
            if len(str_value) > 30:
                str_value = str_value[:30] + "..."
            
            values.append(f"{str_value:<15}")
        
        print(" | ".join(values))


def display_cache_statistics(conn):
    """显示缓存统计信息或通用表统计信息"""
    cursor = conn.cursor()
    
    print("\n数据库统计信息:")
    print("-" * 60)
    
    tables = get_table_info(conn)
    for table_name in tables:
        # 获取表记录数
        cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"{table_name} 表记录数: {count}")
        


def search_cache_data(conn, search_term, table_name):
    """搜索数据 - 适应不同的表结构"""
    cursor = conn.cursor()
    
    print(f"\n在 {table_name} 表中搜索 '{search_term}':")
    print("-" * 100)
    
    # 首先检查表结构，确定可用的列
    schema = get_table_schema(conn, table_name)
    column_names = [col[1] for col in schema]  # 获取列名列表

    # 构建查询语句，只在存在相关列时才搜索
    where_conditions = []
    params = []
    
    for col_name in column_names:
        # 对于文本类型的列进行搜索
        where_conditions.append(f"{col_name} LIKE ?")
        params.append(f'%{search_term}%')
    
    if where_conditions:
        where_clause = " OR ".join(where_conditions)
        # 如果表包含cache_time列，则按此列排序，否则按第一列排序
        if 'cache_time' in column_names:
            query = f"SELECT * FROM {table_name} WHERE {where_clause} ORDER BY cache_time DESC"
        else:
            if column_names:
                query = f"SELECT * FROM {table_name} WHERE {where_clause} ORDER BY {column_names[0]} DESC"
            else:
                query = f"SELECT * FROM {table_name} WHERE {where_clause}"
        cursor.execute(query, params)
    else:
        # 如果没有列，直接查询所有数据
        cursor.execute(f"SELECT * FROM {table_name}")
    
    rows = cursor.fetchall()
    
    if not rows:
        print("未找到匹配的记录")
        return
    
    # 获取列名
    header_names = [description[0] for description in cursor.description]
    header = " | ".join([f"{col_name[:15]:<15}" for col_name in header_names])  # 限制列名长度
    print(header)
    print("-" * 100)
    
    for row in rows:
        values = []
        for i, col_name in enumerate(header_names):
            value = row[i]
            
            # 如果是数据列，尝试格式化JSON
            if col_name == 'data':
                try:
                    data_obj = json.loads(value)
                    # 如果数据是字典，提取关键信息
                    if isinstance(data_obj, dict):
                        # 只显示部分关键字段
                        if 'price' in data_obj or 'change_pct' in data_obj or 'name' in data_obj:
                            formatted_data = []
                            for key, val in list(data_obj.items())[:3]:  # 只显示前3个键值对
                                key_str = str(key)[:8] # 限制键名长度
                                val_str = str(val)[:20] # 限制值长度
                                formatted_data.append(f"{key_str}:{val_str}")
                            value = "{" + ", ".join(formatted_data) + "}"
                        else:
                            value = f"JSON({len(str(data_obj))} chars)"
                    else:
                        value = str(data_obj)
                except json.JSONDecodeError:
                    value = f"JSON格式错误: {str(value)[:30]}..."
                except Exception as e:
                    value = f"解析错误: {str(e)[:30]}"
            
            # 如果是时间列，格式化时间
            elif col_name == 'cache_time':
                try:
                    # 处理不同的时间格式
                    value = value.replace('Z', '+00:00')  # 替换Z后缀
                    if '+' in value or value.count('-') > 2:  # 包含时区信息
                        cache_time = datetime.fromisoformat(value)
                    else:
                        cache_time = datetime.fromisoformat(value)
                    value = cache_time.strftime('%Y-%m-%d %H:%M:%S')
                except ValueError:
                    pass # 保持原始值
            
            # 限制值的长度以避免输出过长
            str_value = str(value)
            if len(str_value) > 30:
                str_value = str_value[:30] + "..."
            
            values.append(f"{str_value:<15}")
        
        print(" | ".join(values))


def query_by_cache_key(conn, cache_key, table_name):
    """根据键查询数据 - 适应不同的表结构"""
    cursor = conn.cursor()
    
    # 检查表结构，确定是否有cache_key列
    schema = get_table_schema(conn, table_name)
    column_names = [col[1] for col in schema]  # 获取列名列表

    if 'cache_key' in column_names:
        print(f"\n查询 {table_name} 表中缓存键为 '{cache_key}' 的记录:")
        print("-" * 100)
        cursor.execute(f"SELECT * FROM {table_name} WHERE cache_key = ?", (cache_key,))
    else:
        # 如果没有cache_key列，尝试其他可能的键列
        key_columns = ['id', 'key', 'name', 'code']  # 可能作为键的列
        found_key_column = None
        for col in key_columns:
            if col in column_names:
                found_key_column = col
                break
        
        if found_key_column:
            print(f"\n查询 {table_name} 表中{found_key_column}为 '{cache_key}' 的记录:")
            print("-" * 100)
            cursor.execute(f"SELECT * FROM {table_name} WHERE {found_key_column} = ?", (cache_key,))
        else:
            # 如果没有找到合适的键列，提示用户
            print(f"\n表 {table_name} 中没有找到常见的键列 (cache_key, id, key, name, code)")
            print("-" * 100)
            return

    row = cursor.fetchone()
    
    if not row:
        print("未找到匹配的记录")
        return
    
    # 获取列名
    header_names = [description[0] for description in cursor.description]
    header = " | ".join([f"{col_name[:15]:<15}" for col_name in header_names])  # 限制列名长度
    print(header)
    print("-" * 100)
    
    values = []
    for i, col_name in enumerate(header_names):
        value = row[i]
        
        # 如果是数据列，尝试格式化JSON
        if col_name == 'data':
            try:
                data_obj = json.loads(value)
                # 以更易读的格式打印完整数据
                print(f"\n完整数据内容:\n{json.dumps(data_obj, ensure_ascii=False, indent=2)}")
                value = f"JSON({len(str(data_obj))} chars)"
            except json.JSONDecodeError:
                value = f"JSON格式错误: {str(value)[:30]}..."
            except Exception as e:
                value = f"解析错误: {str(e)[:30]}"
        
        # 如果是时间列，格式化时间
        elif col_name == 'cache_time':
            try:
                # 处理不同的时间格式
                value = value.replace('Z', '+00:00')  # 替换Z后缀
                if '+' in value or value.count('-') > 2:  # 包含时区信息
                    cache_time = datetime.fromisoformat(value)
                else:
                    cache_time = datetime.fromisoformat(value)
                value = cache_time.strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass # 保持原始值
        
        # 限制值的长度以避免输出过长
        str_value = str(value)
        if len(str_value) > 30:
            str_value = str_value[:30] + "..."
        
        values.append(f"{str_value:<15}")
    
    print(" | ".join(values))


def clear_table_data(conn, table_name):
    """清空指定表的数据"""
    cursor = conn.cursor()
    
    # 先显示表中的记录数
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    
    if count == 0:
        print(f"\n表 {table_name} 中没有数据，无需清空")
        return False
    
    print(f"\n表 {table_name} 中有 {count} 条记录")
    confirm = input(f"确定要清空表 {table_name} 的所有数据吗？(输入 'yes' 确认): ").strip().lower()
    
    if confirm == 'yes':
        cursor.execute(f"DELETE FROM {table_name}")
        conn.commit()
        print(f"已清空表 {table_name}，删除了 {count} 条记录")
        return True
    else:
        print("操作已取消")
        return False


from logger_config import gconfig

def main():
    # 检查是否有命令行参数传入数据库路径
    if len(sys.argv) > 1:
        db_path = sys.argv[1]  # 使用第一个命令行参数作为数据库路径
        print(f"使用命令行参数指定的数据库路径: {db_path}")
    else:
        # 数据库路径
        db_dir = gconfig.get('database_dir', "../run/stock_monitor/database/")
        db_path = os.path.join(db_dir, "cache.db")
    
    # 检查数据库文件是否存在
    if not os.path.exists(db_path):
        print(f"数据库文件不存在: {db_path}")
        # 尝试其他可能的路径
        possible_paths = [
            os.path.join(os.path.dirname(__file__), "../run/stock_monitor/database/cache.db"),
            os.path.abspath("../run/stock_monitor/database/cache.db"),
            "cache.db"
        ]
        
        found = False
        for path in possible_paths:
            if os.path.exists(path):
                db_path = path
                found = True
                print(f"找到数据库文件: {db_path}")
                break
        
        if not found:
            print("未找到数据库文件，请检查路径")
            return
    
    print(f"正在连接数据库: {db_path}")
    
    # 连接数据库
    conn = connect_database(db_path)
    if not conn:
        return
    
    try:
        while True:
            print("\n" + "="*60)
            print("股票监控数据库查看工具")
            print("="*60)
            print("1. 查看所有表结构和统计信息")
            print("2. 查看表数据")
            print("3. 按键值查询")
            print("4. 搜索数据")
            print("5. 清空指定表")
            print("6. 退出")
            
            choice = input("\n请选择操作 (1-6): ").strip()
            
            if choice == '1':
                # 获取表信息
                tables = get_table_info(conn)
                print(f"\n数据库包含以下表: {', '.join(tables)}")
                
                # 显示缓存统计信息
                display_cache_statistics(conn)
                
                # 显示每个表的结构
                for table_name in tables:
                    print(f"\n表结构 {table_name}:")
                    schema = get_table_schema(conn, table_name)
                    for col in schema:
                        print(f"  {col[1]} ({col[2]}) - {['NOT NULL', 'NULL'][col[3]]}")
            
            elif choice == '2':
                # 查看表数据
                tables = get_table_info(conn)
                print(f"\n可用表: {', '.join(tables)}")
                
                table_choice = input("请输入要查看的表名: ").strip()
                
                if table_choice in tables:
                    try:
                        limit = int(input("请输入要显示的记录数 (默认10): ") or "10")
                    except ValueError:
                        limit = 10
                    
                    count = get_table_count(conn, table_choice)
                    print(f"\n{table_choice} 表共有 {count} 条记录")
                    
                    if count > 0:
                        # 根据记录数量决定显示多少条
                        display_limit = min(limit, count, 50)  # 最多显示50条
                        display_table_data(conn, table_choice, display_limit)
                    else:
                        print("表中没有数据")
                else:
                    print("表不存在")
            
            elif choice == '3':
                # 按键查询
                tables = get_table_info(conn)
                print(f"\n可用表: {', '.join(tables)}")
                
                table_choice = input("请输入表名: ").strip()
                
                if table_choice in tables:
                    key_value = input("请输入键值: ").strip()
                    if key_value:
                        query_by_cache_key(conn, key_value, table_choice)
                    else:
                        print("键值不能为空")
                else:
                    print("表不存在")
            
            elif choice == '4':
                # 搜索数据
                tables = get_table_info(conn)
                print(f"\n可用表: {', '.join(tables)}")
                
                table_choice = input("请输入表名 或输入 'all' 查询所有表: ").strip()
                
                if table_choice == 'all':
                    search_term = input("请输入搜索词: ").strip()
                    if search_term:
                        for table in tables:
                            search_cache_data(conn, search_term, table)
                    else:
                        print("搜索词不能为空")
                elif table_choice in tables:
                    search_term = input("请输入搜索词: ").strip()
                    if search_term:
                        search_cache_data(conn, search_term, table_choice)
                    else:
                        print("搜索词不能为空")
                else:
                    print("表不存在")
            
            elif choice == '5':
                # 清空指定表
                tables = get_table_info(conn)
                print(f"\n可用表: {', '.join(tables)}")
                
                table_choice = input("请输入要清空的表名: ").strip()
                
                if table_choice in tables:
                    clear_table_data(conn, table_choice)
                else:
                    print("表不存在")
            
            elif choice == '6':
                print("退出程序")
                break
            
            else:
                print("无效选择，请重新输入")
    
    except Exception as e:
        print(f"查询数据库时出错: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
