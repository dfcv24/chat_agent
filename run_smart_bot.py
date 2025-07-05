#!/usr/bin/env python3
"""
智能任务聊天机器人启动脚本
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    """主函数"""
    print("🤖 启动智能任务聊天机器人...")
    print("=" * 50)
    
    try:
        # 检查依赖
        check_dependencies()
        
        # 启动机器人
        from advanced_chatbot import ProactiveChatBot
        bot = ProactiveChatBot()
        bot.chat_loop()
        
    except KeyboardInterrupt:
        print("\n👋 程序被用户中断，再见！")
    except ImportError as e:
        print(f"❌ 导入错误: {e}")
        print("💡 请确保已安装所需依赖: pip install -r requirements.txt")
    except Exception as e:
        print(f"❌ 程序运行出错: {e}")
        print("💡 请检查配置和环境设置")

def check_dependencies():
    """检查必要的依赖"""
    required_modules = [
        'openai',
        'python_dotenv', 
        'prompt_toolkit'
    ]
    
    missing_modules = []
    
    for module in required_modules:
        try:
            if module == 'python_dotenv':
                import dotenv
            elif module == 'prompt_toolkit':
                import prompt_toolkit
            else:
                __import__(module)
        except ImportError:
            missing_modules.append(module)
    
    if missing_modules:
        print(f"❌ 缺少依赖模块: {', '.join(missing_modules)}")
        print("💡 请运行: pip install -r requirements.txt")
        sys.exit(1)
    else:
        print("✅ 依赖检查通过")

if __name__ == "__main__":
    main()
