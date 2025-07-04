#!/usr/bin/env python3
"""
聊天机器人启动脚本
运行这个文件来启动聊天机器人
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from chatbot import ChatBot

def main():
    """主函数"""
    print("🚀 正在启动聊天机器人...")
    
    try:
        bot = ChatBot()
        bot.chat_loop()
    except ImportError as e:
        print(f"❌ 导入错误: {e}")
        print("📝 请确保已安装所需依赖:")
        print("   pip install -r requirements.txt")
    except Exception as e:
        print(f"❌ 启动失败: {e}")

if __name__ == "__main__":
    main()
