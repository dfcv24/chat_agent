#!/usr/bin/env python3
"""
Web聊天应用启动脚本
使用FastAPI提供Web界面
"""

import os
import sys
import uvicorn
from web_app import app

def main():
    """启动Web应用"""
    print("🚀 启动智能聊天助手Web应用...")
    print("📱 界面地址: http://localhost:8000")
    print("📚 API文档: http://localhost:8000/docs")
    print("🛑 按 Ctrl+C 停止服务")
    print("-" * 50)
    
    try:
        # 确保必要的目录存在
        os.makedirs("static", exist_ok=True)
        os.makedirs("templates", exist_ok=True)
        os.makedirs("data", exist_ok=True)
        
        # 启动服务
        uvicorn.run(
            app, 
            host="0.0.0.0", 
            port=8000, 
            reload=True,
            log_level="info"
        )
        
    except KeyboardInterrupt:
        print("\n👋 服务已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
